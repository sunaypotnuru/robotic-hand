"""
LUNA Voice Command Module
Whisper AI + local Ollama GPU LLM Parser with Gemini Fallback & Wake Word Guards
"""

import threading
import queue
import json
import os
import io
import tempfile
from dotenv import load_dotenv
import logging
from web_interface.ai_modules import ollama_interface

logger = logging.getLogger("LUNA.Voice")
load_dotenv()


class VoiceCommandProcessor:
    """
    Voice command processor using GPU accelerated Ollama/Gemini and audio transcription models.
    """
    
    def __init__(self, model='base', language='en', use_whisper=True):
        """
        Initialize Voice Processor
        """
        self.model_name = model
        self.language = language
        self.use_whisper = use_whisper
        self.whisper_model = None
        self.speech_recognizer = None
        self.microphone = None
        self.is_listening = False
        
        # Guard Queue overflow (B4 - maximum size 10, drop oldest if full)
        self.command_queue = queue.Queue(maxsize=10)
        self.lock = threading.Lock()
        self.listen_thread = None
        
        # --- GEMINI SETUP ---
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = None
        
        try:
            if self.api_key:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                
                model_options = [
                    'gemini-2.0-flash',
                    'gemini-2.0-flash-lite',
                    'gemini-flash-latest',
                    'models/gemini-2.0-flash',
                    'gemini-1.5-flash'
                ]
                
                logger.info("Verify Gemini backup models...")
                for model_name in model_options:
                    try:
                        temp_model = genai.GenerativeModel(model_name)
                        response = temp_model.generate_content("test")
                        if response:
                            self.gemini_model = temp_model
                            logger.info(f"✅ Active Backup Model: {model_name}")
                            break
                    except Exception:
                        continue
            else:
                logger.warning("⚠️ Gemini API Key missing. Local Ollama & basic parsing will run.")
        except Exception as e:
            logger.error(f"⚠️ Gemini initialization error: {e}")

        # --- TTS SETUP ---
        self.tts_engine = None
        self.tts_lock = threading.Lock()
        self.init_tts()
        
        # --- WHISPER / SR SETUP (GPU Accelerated Fallbacks - Part 2.4) ---
        if use_whisper:
            try:
                # Attempt CUDA/GPU acceleration using faster-whisper or standard whisper
                try:
                    from faster_whisper import WhisperModel
                    # Load on GPU with float16 precision for blazing fast inference
                    self.whisper_model = WhisperModel(model, device="cuda", compute_type="float16")
                    logger.info(f"🚀 Faster-Whisper GPU Accelerated model loaded on CUDA: {model}")
                    self.use_faster_whisper = True
                except ImportError:
                    import whisper
                    import torch
                    dev = "cuda" if torch.cuda.is_available() else "cpu"
                    self.whisper_model = whisper.load_model(model, device=dev)
                    self.use_faster_whisper = False
                    logger.info(f"✅ Standard Whisper model loaded: {model} (device: {dev})")
            except Exception as e:
                logger.error(f"⚠️ Whisper initialization error: {e}. Falling back to Google Speech Recognition")
                self.use_whisper = False
        
        if not self.use_whisper:
            try:
                import speech_recognition as sr
                self.speech_recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.speech_recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("✅ Speech Recognition initialized (Google API)")
            except Exception as e:
                logger.error(f"⚠️ Speech Recognition initialization error: {e}")

    def init_tts(self):
        """Initialize Text-to-Speech engine"""
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            voices = self.tts_engine.getProperty('voices')
            if voices:
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.8)
            logger.info("✅ Text-to-Speech engine initialized")
        except Exception as e:
            logger.error(f"⚠️ TTS initialization error: {e}")

    def speak(self, text, callback=None):
        """Speak text using TTS (non-blocking)"""
        if self.tts_engine is None:
            if callback: callback(text)
            return
        
        def speak_thread():
            try:
                with self.tts_lock:
                    self.tts_engine.setProperty('rate', 150)
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                if callback: callback(text)
            except Exception as e:
                print(f"⚠️  TTS error: {e}")
                if callback: callback(text)
        
        threading.Thread(target=speak_thread, daemon=True).start()
        logger.debug(f"🔊 Speaking: '{text}'")

    def process_ai_command(self, user_text):
        """
        Send text to Ollama (first) or Gemini (fallback) and get structured commands.
        """
        # Security Sanitization V2 (Rejects exec, eval, __import__)
        for bad_key in ["exec", "eval", "__import__"]:
            if bad_key in user_text:
                logger.critical(f"🛑 Prompt injection threat block: '{bad_key}' detected in user voice payload!")
                return {"type": "error", "response_text": "Security warning: Malicious instruction rejected."}

        # Wake Word Filter V1 ("Hey Luna" / "Luna" check with exact boundary - 2.3)
        import re
        lower_text = user_text.lower()
        if not re.search(r'\bluna\b', lower_text):
            logger.info("Wake word 'Luna' not detected. Ignoring command.")
            return None

        # Macro Sequence detection (Feature 3)
        is_macro = any(kw in lower_text for kw in ["then", "sequence", "macro", "after that", "first", "and then"])
        if is_macro:
            logger.info(f"🔮 Complex multi-step macro detected in voice command: '{user_text}'")
            try:
                macro_data = ollama_interface.parse_macro_command(user_text)
                if macro_data and 'actions' in macro_data:
                    macro_data['type'] = 'macro_sequence'
                    macro_data['response_text'] = "Initializing multi-step macro sequence now."
                    return macro_data
            except Exception as e:
                logger.error(f"⚠️ Failed to parse complex macro command via local Ollama: {e}")

        # 1. Query Local Ollama LLM first (Part 2.3)
        try:
            prompt = f"""
            You are LUNA, a robotic arm. User command: '{user_text}'.
            My Hardware: 4 Motors (IDs: 2=Elbow, 3=Wrist Pitch, 4=Wrist Roll, 5-9=Fingers).
            
            Analyze the request and return valid JSON ONLY.
            Format:
            {{
                "action": "short_action_name",
                "motor_values": {{ "2": int_angle_0_to_180, "3": int_angle_0_to_180, ... }},
                "response_text": "Short spoken response for the user"
            }}
            Rules:
            - 'home' -> All 90 (Fingers 0)
            - 'open hand' -> Fingers 5-9 set to 0
            - 'close hand' or 'grab' -> Fingers 5-9 set to 180
            - If usage is unclear, ask for clarification in 'response_text' and keep 'motor_values' empty.
            """
            logger.info("🤖 Directing voice command parser to local Ollama...")
            ollama_response = ollama_interface.query_ollama(prompt)
            if ollama_response:
                clean_text = ollama_response.replace('```json', '').replace('```', '').strip()
                for bad_key in ["exec", "eval", "__import__"]:
                    if bad_key in clean_text:
                        raise ValueError("Malicious injection keywords found in LLM output payload.")
                
                command_data = json.loads(clean_text)
                if 'motor_values' in command_data:
                    # Map string keys back to int motor IDs
                    command_data['motor_values'] = {int(k): int(v) for k, v in command_data['motor_values'].items()}
                command_data['type'] = 'ollama_command'
                return command_data
        except Exception as e:
            logger.warning(f"⚠️ Local Ollama query failed. Falling back to Gemini: {e}")

        # 2. Backup Fallback to Google Gemini
        if self.gemini_model:
            try:
                prompt = f"""
                You are LUNA, a robotic arm. User said: '{user_text}'.
                My Hardware: 4 Motors (IDs: 2=Elbow, 3=Wrist Pitch, 4=Wrist Roll, 5-9=Fingers).
                
                Analyze the request and return valid JSON ONLY.
                Format:
                {{
                    "action": "short_action_name",
                    "motor_values": {{ "2": int_angle_0_to_180, "3": int_angle_0_to_180, ... }},
                    "response_text": "Short spoken response for the user"
                }}
                """
                response = self.gemini_model.generate_content(prompt)
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                     return None
                     
                clean_text = response.text.replace('```json', '').replace('```', '').strip()
                for bad_key in ["exec", "eval", "__import__"]:
                    if bad_key in clean_text:
                        logger.critical("🛑 prompt injection in Gemini output blocked!")
                        return {"type": "error", "response_text": "Malicious content detected."}
                
                command_data = json.loads(clean_text)
                if 'motor_values' in command_data:
                    command_data['motor_values'] = {int(k): int(v) for k, v in command_data['motor_values'].items()}
                command_data['type'] = 'gemini_command'
                return command_data
            except Exception as e:
                logger.error(f"⚠️ Gemini processing error: {e}")

        # 3. Last-resort basic keyword parser
        return self.basic_parse_command(user_text)

    def basic_parse_command(self, text):
        """Legacy keyword parser (Fallback)"""
        if not text: return None
        text = text.lower()
        command = {'type': None, 'action': None, 'motor_values': {}}

        if 'arm up' in text:
            command.update({'type': 'motor', 'action': 'arm_up', 'motor_values': {2: 0}})
        elif 'arm down' in text:
            command.update({'type': 'motor', 'action': 'arm_down', 'motor_values': {2: 180}})
        elif 'open hand' in text:
            command.update({'type': 'hand', 'action': 'open', 'motor_values': {5: 0, 6: 0, 7: 0, 8: 0, 9: 0}})
        elif 'close hand' in text or 'grab' in text:
            command.update({'type': 'hand', 'action': 'close', 'motor_values': {5: 180, 6: 180, 7: 180, 8: 180, 9: 180}})
        elif 'stop' in text:
            command.update({'type': 'system', 'action': 'emergency_stop', 'motor_values': {}})
        else:
            return None
        return command

    def listen_loop(self):
        """Main listening loop"""
        if not self.microphone and not self.use_whisper: return
        logger.info("🎤 Voice listening loop active")
        
        while self.is_listening:
            try:
                text = None
                if self.use_whisper and self.whisper_model:
                    with self.microphone as source:
                        audio = self.speech_recognizer.listen(source, timeout=1, phrase_time_limit=4)
                    wav_data = io.BytesIO(audio.get_wav_data())
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        tmp.write(wav_data.read())
                        tmp_path = tmp.name
                    
                    if getattr(self, 'use_faster_whisper', False):
                        segments, info = self.whisper_model.transcribe(tmp_path, language=self.language)
                        text = " ".join([segment.text for segment in segments]).strip()
                    else:
                        result = self.whisper_model.transcribe(tmp_path, language=self.language)
                        text = result['text'].strip()
                    
                    os.unlink(tmp_path)
                elif self.speech_recognizer:
                    with self.microphone as source:
                        audio = self.speech_recognizer.listen(source, timeout=1, phrase_time_limit=4)
                    text = self.speech_recognizer.recognize_google(audio, language=self.language)

                if text:
                    logger.info(f"🎤 Heard: '{text}'")
                    command = self.process_ai_command(text)
                    if command:
                        # Queue overflow handler B4 (drop oldest)
                        with self.lock:
                            if self.command_queue.full():
                                try:
                                    self.command_queue.get_nowait()
                                    logger.warning("⚠️ Command queue full. Dropped oldest frame.")
                                except queue.Empty:
                                    pass
                            self.command_queue.put(command)

            except Exception:
                pass
                
    def start_listening(self):
        if self.is_listening: return
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listen_thread.start()
        logger.info("✅ Voice listening thread started")

    def stop_listening(self):
        self.is_listening = False
        if self.listen_thread: self.listen_thread.join(timeout=1)

    def get_command(self, timeout=None):
        try:
            return self.command_queue.get(timeout=timeout)
        except queue.Empty:
            return None
