"""
LUNA Ollama Local LLM Module
GPU accelerated command parsing and bimanual macro planning
"""

import requests
import json
import logging

logger = logging.getLogger("LUNA.Ollama")


def query_ollama(prompt, model='llama3.1:8b'):
    """
    Query local Ollama model (llama3.1:8b or gemma2:9b) for command parsing.
    """
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",  # Forces JSON formatted response output
        "options": {
            "temperature": 0.0,  # Enforces deterministic robotics intent output
            "num_ctx": 2048     # Limits context memory to optimize GPU VRAM throughput
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=8.0)
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "").strip()
            return response_text
        else:
            logger.warning(f"⚠️ Ollama service returned status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"⚠️ Failed to reach local Ollama at {url}: {e}. Ensure Ollama is running.")
        return None


def parse_macro_command(user_text, model='llama3.1:8b'):
    """
    Decompose complex voice sequences into atomic multi-step macro lists (Resolved Feature 3)
    """
    system_prompt = f"""
    You are LUNA, a robotic system. Parse this complex sequence: "{user_text}".
    Decompose it into a list of atomic operations.
    Output ONLY a valid JSON object matching the following schema structure:
    {{
        "actions": [
            {{"type": "move", "target": "object_name_or_coords"}},
            {{"type": "grab"}},
            {{"type": "move", "target": "destination_name_or_coords"}},
            {{"type": "release"}},
            {{"type": "wait", "duration": 2.0}}
        ]
    }}
    Rules:
    - Supported types: "move", "grab", "release", "wait", "loop".
    - Respond only with clean JSON. No markdown syntax, explanation, or conversational text.
    """
    
    response_text = query_ollama(system_prompt, model=model)
    if response_text:
        try:
            # Strip markdown JSON wrappers
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Robust JSON extraction using regex (Upgrade 2.6)
            import re
            match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if match:
                clean_text = match.group()
            
            # Security sanitization (V2 - Gemini/Ollama prompt injection safeguards)
            for bad_key in ["exec", "eval", "__import__"]:
                if bad_key in clean_text:
                    logger.critical(f"🛑 Security violation: Malicious keyword '{bad_key}' rejected!")
                    return None
            
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"⚠️ Failed to parse or sanitize Ollama macro payload: {e}")
    return None
