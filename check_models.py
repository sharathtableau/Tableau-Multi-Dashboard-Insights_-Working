import os
import config
from google import genai
import logging

logging.basicConfig(level=logging.INFO)

try:
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    print("Checking available Gemini models...")
    for model in client.models.list():
        print(f" - {model.name}")
except Exception as e:
    print(f"Error checking models: {e}")
