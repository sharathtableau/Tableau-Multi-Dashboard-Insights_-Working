import config
import os

print("--- Environment Verification ---")
print(f"GEMINI_API_KEY from config: {config.GEMINI_API_KEY[:5]}...{config.GEMINI_API_KEY[-5:]}")
print(f"AI_PROVIDER from config: {config.AI_PROVIDER}")
print(f"SELENIUM_USERNAME from config: {config.SELENIUM_USERNAME}")

if config.GEMINI_API_KEY == "AIzaSyB0gTyBqohQmtY6ZupJaS0XkURhaZwyt-Y":
    print("SUCCESS: config.py correctly loaded values from .env")
else:
    print("FAILURE: config.py did not load the expected value from .env")
