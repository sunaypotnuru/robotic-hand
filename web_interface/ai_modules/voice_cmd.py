"""
LUNA Voice Command Module
Whisper AI for Voice Recognition + Google Gemini for Intelligence
"""

import threading
import queue
import json
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger("LUNA.Voice")

# Load environment variables from .env file
load_dotenv()

class VoiceCommandProcessor:
    """
    Voice command processor using Whisper AI for hearing and Gemini for understanding
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
        self.command_queue = queue.Queue()
        self.lock = threading.Lock()
        self.listen_thread = None
        
        # --- GEMINI SETUP ---
        # Securely load API Key from .env file
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = None
        
        try:
            if self.api_key:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                
                # Robust Model Selection with Deep Validation
                # We try generating content to ensure the model actually exists and is accessible
                model_options = [
                    'gemini-2.0-flash',
                    'gemini-2.0-flash-lite',
                    'gemini-flash-latest',
                    'models/gemini-2.0-flash',
                    'gemini-1.5-flash'
                ]
                self.gemini_model = None
                
                logger.info("🔄 verifying Gemini Models...")
                for model_name in model_options:
                    try:
                        logger.debug(f"   Testing {model_name}...")
                        temp_model = genai.GenerativeModel(model_name)
                        # Deep Validation: Attempt actual generation
                        response = temp_model.generate_content("test")
                        if response:
                            self.gemini_model = temp_model
                            logger.info("✅ SUCCESS")
                            logger.info(f"✅ Active Model: {model_name}")
                            break
                    except Exception as e:
                        logger.warning(f"❌ FAILED ({str(e)})")
                        continue
                        
                if not self.gemini_model:
                     logger.critical("\n⚠️  Could not find ANY working Gemini model.")
                     logger.info("   Please check your API Key and Google AI Studio project settings.")
                     try:
                         logger.info("   Available Models on your key:")
                         for m in genai.list_models():
                             if 'generateContent' in m.supported_generation_methods:
                                 logger.info(f"   - {m.name}")
                     except:
                         pass

            else:
                logger.warning("⚠️  Gemini API Key missing in .env file. Using legacy basic commands.")
        except Exception as e:
            logger.error(f"⚠️  Gemini initialization error: {e}")

        # --- TTS SETUP ---
        self.tts_engine = None
        self.tts_lock = threading.Lock()
        self.init_tts()
        
        # --- WHISPER / SR SETUP ---
        if use_whisper:
            try:
                import whisper
                self.whisper_model = whisper.load_model(model)
                logger.info(f"✅ Whisper model loaded: {model}")
            except ImportError:
                logger.warning("⚠️  Whisper not installed. Falling back to Google Speech Recognition")
                self.use_whisper = False
            except Exception as e:
                logger.error(f"⚠️  Whisper initialization error: {e}. Falling back to Google Speech Recognition")
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
                logger.error(f"⚠️  Speech Recognition initialization error: {e}")

    def init_tts(self):
        """Initialize Text-to-Speech engine"""
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            # Try to set a robotic/female voice
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
            logger.error(f"⚠️  TTS initialization error: {e}")

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
        Send text to Gemini and get structured robot commands.
        """
        if not self.gemini_model:
            logger.warning("⚠️  Gemini not configured, falling back to basic parser.")
            return self.basic_parse_command(user_text)

        try:
            prompt = f"""
            You are LUNA, a robotic arm. User said: '{user_text}'.
            My Hardware: 4 Motors (IDs: 2=Elbow, 3=Wrist Pitch, 4=Wrist Roll, 5-9=Fingers).
            
            Analyze the request and return valid JSON ONLY.
            Format:
            {{
                "action": "short_action_name",
                "motor_values": {{ "motor_id": int_angle_0_to_180, ... }},
                "response_text": "Short spoken response for the user"
            }}

            Rules:
            - 'home' -> All 90 (Fingers 0)
            - 'open hand' -> Fingers 5-9 set to 0
            - 'close hand' or 'grab' -> Fingers 5-9 set to 180
            - If usage is unclear, ask for clarification in 'response_text' and keep 'motor_values' empty.
            """
            
            response = self.gemini_model.generate_content(prompt)
            # Check blockage
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                 print(f"⚠️  Gemini Blocked: {response.prompt_feedback.block_reason}")
                 return None
                 
            # Clean response to ensure valid JSON (strip markdown codes if any)
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            
            command_data = json.loads(clean_text)
            command_data['type'] = 'gemini_command' # Tag it for processing
            return command_data

        except json.JSONDecodeError as e:
            logger.error(f"⚠️ Gemini returned invalid JSON: {e}")
            return {"type": "error", "response_text": "I received a malformed command. Please repeat."}
        except Exception as e:
            logger.error(f"⚠️ Gemini processing error: {e}")
            return self.basic_parse_command(user_text)

    def basic_parse_command(self, text):
        """Legacy keyword parser (Fallback)"""
        if not text: return None
        text = text.lower()
        command = {'type': 'unknown', 'action': None, 'motor_values': {}}

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
        
        return command if command['type'] != 'unknown' else None

    def listen_loop(self):
        """Main listening loop"""
        if not self.microphone and not self.use_whisper: return
        logger.info("🎤 Voice listening loop active")
        
        while self.is_listening:
            try:
                text = None
                if self.use_whisper and self.whisper_model:
                    import tempfile
                    with self.microphone as source:
                        audio = self.speech_recognizer.listen(source, timeout=1, phrase_time_limit=4)
                    wav_data = io.BytesIO(audio.get_wav_data())
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        tmp.write(wav_data.read())
                        tmp_path = tmp.name
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
                        self.command_queue.put(command)

            except Exception:
                pass # Ignore timeouts
                
    def start_listening(self):
        if self.is_listening: return
        
        # Check if we have the required components
        if not self.microphone and not self.use_whisper:
            # Silent fail for now is okay, we handle it in main
            return

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


if __name__ == "__main__":
    print("\n--- LUNA VOICE COMMAND TEST ---")
    print("Initializing...")
    
    # Initialize implementation
    processor = VoiceCommandProcessor(model='base', use_whisper=False)
    
    # Try to start listening
    processor.start_listening()
    
    if processor.is_listening:
        print("✅ Microphone Active. Speak now!")
        print("Listening... (Press Ctrl+C to stop)")
        mode = "voice"
    else:
        print("\n⚠️  Microphone/Voice modules missing or failed.")
        print("👉 STARTING TEXT MODE instead.")
        print("   Type your commands below (e.g., 'Luna, open hand')")
        mode = "text"

    try:
        while True:
            if mode == "voice":
                cmd = processor.get_command(timeout=1.0)
                if cmd:
                    print(f"\n✅ COMMAND RECEIVED ({cmd['type']}):")
                    print(json.dumps(cmd, indent=2))
                    if 'response_text' in cmd and processor.tts_engine:
                        processor.speak(cmd['response_text'])
            else:
                try:
                    user_text = input("\n📝 Command: ")
                    if not user_text: continue
                    if user_text.lower() in ['exit', 'quit']: break
                    
                    cmd = processor.process_ai_command(user_text)
                    
                    if cmd:
                        print(f"✅ PROCESSED:")
                        print(json.dumps(cmd, indent=2))
                        
                        if 'response_text' in cmd:
                            print(f"🤖 LUNA SAYS: {cmd['response_text']}")
                            if processor.tts_engine:
                                processor.speak(cmd['response_text'])
                    else:
                        print("❌ Failed to process command (Check API/Model error above)")
                            
                except EOFError:
                    break
                    
    except KeyboardInterrupt:
        print("\nStopping...")
        if processor.is_listening:
            processor.stop_listening()
        print("Done.")
