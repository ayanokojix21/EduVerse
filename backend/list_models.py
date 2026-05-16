import os
import google.generativeai as genai
from app.config import get_settings

genai.configure(api_key=get_settings().google_api_key)
for m in genai.list_models():
    if "gemini" in m.name or "gemma" in m.name:
        print(m.name)
