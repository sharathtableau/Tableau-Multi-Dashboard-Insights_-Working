"""
Run this from your project folder:  python diagnose_gemini.py
It will tell you exactly why Gemini is not initializing.
"""

print("\n========== GEMINI DIAGNOSTIC ==========\n")

# Step 1: Check google-genai import
print("Step 1: Importing google-genai...")
try:
    from google import genai
    print("  ✅ google-genai imported successfully")
except ImportError as e:
    print(f"  ❌ IMPORT FAILED: {e}")
    print("  👉 Fix: Run   pip install google-genai   in your project folder")
    exit(1)

# Step 2: Check config
print("\nStep 2: Loading config...")
try:
    import config
    print(f"  ✅ config.py loaded")
    print(f"     GEMINI_API_KEY : {'SET (' + config.GEMINI_API_KEY[:8] + '...)' if config.GEMINI_API_KEY else 'MISSING ❌'}")
    print(f"     GEMINI_MODEL   : {config.GEMINI_MODEL}")
    print(f"     AI_PROVIDER    : {config.AI_PROVIDER}")
    print(f"     ENABLE_AI_INSIGHTS: {config.ENABLE_AI_INSIGHTS}")
except Exception as e:
    print(f"  ❌ config.py failed to load: {e}")
    exit(1)

# Step 3: Initialize client
print("\nStep 3: Initializing Gemini client...")
try:
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    print("  ✅ Client initialized")
except Exception as e:
    print(f"  ❌ Client init FAILED: {e}")
    exit(1)

# Step 4: Make a real test call
print("\nStep 4: Making test API call to gemini-2.5-flash...")
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=["Say hello in one word."]
    )
    print(f"  ✅ API call SUCCESS! Response: {response.text.strip()}")
except Exception as e:
    print(f"  ❌ API call FAILED: {e}")
    print("\n  👉 Try these fallback models:")
    for model in ["gemini-2.0-flash", "gemini-2.5-pro"]:
        print(f"     Testing {model}...")
        try:
            r = client.models.generate_content(model=model, contents=["Say hello in one word."])
            print(f"     ✅ {model} works! Response: {r.text.strip()}")
        except Exception as ex:
            print(f"     ❌ {model} failed: {ex}")

print("\n========== END DIAGNOSTIC ==========\n")
