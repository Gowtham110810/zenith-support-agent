import os
import re
import json
import sqlite3
from datetime import datetime, timezone
from google import genai
from google.genai import types

SUPPORT_DB = "support.db"

def init_databases():
    conn = sqlite3.connect(SUPPORT_DB)
    cur = conn.cursor()
    # Stores the company FAQs and policies
    cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            added_at TEXT
        )
    """)
    # Logs all customer queries and AI responses/escalations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_email TEXT,
            query TEXT,
            ai_response TEXT,
            status TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def call_gemini(prompt, temperature=0.1):
    """Dynamic Gemini model discovery for strict text generation."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "System Error: API Key missing."
    
    try:
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))
        models = [m.name.replace("models/", "") for m in client.models.list() 
                  if "gemini" in m.name and not any(x in m.name for x in ["embedding", "imagen", "veo", "tts"])]
        models.sort(key=lambda x: (0 if "flash" in x else 1, x), reverse=True)

        for model_name in models:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=temperature)
                )
                return resp.text.strip()
            except Exception:
                continue
    except Exception as e:
        return f"System Error: {str(e)}"
    return "Error: Could not generate response."
