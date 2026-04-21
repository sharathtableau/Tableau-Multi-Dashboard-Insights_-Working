# ============================================================
# CONFIGURATION FILE
# ============================================================
# This file stores configuration values including API keys
#
# **PLACE YOUR GEMINI API KEY HERE** ↓

GEMINI_API_KEY = "AIzaSyB0gTyBqohQmtY6ZupJaS0XkURhaZwyt-Y"  # Replace with your actual Gemini API key

# Tableau Configuration (optional - can also be set via web form)
TABLEAU_SERVER_URL = "https://us-east-1.online.tableau.com/"
TABLEAU_SITE_ID = "lasexihe-2b1e27ff34"

# AI Model Configuration
GEMINI_MODEL = "gemini-2.0-flash"
print(f"[CONFIG] Loaded from: {__file__} | Model: {GEMINI_MODEL}")
ENABLE_AI_INSIGHTS = True  # Set to False to disable AI insights

# Anthropic Configuration (Alternative)
ANTHROPIC_API_KEY = "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"
ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
AI_PROVIDER = "gemini"  # "gemini" or "anthropic"

# Email Automation Configuration (Gmail/Outlook)
EMAIL_SENDER = "sharathtableaupoc@gmail.com"
EMAIL_PASSWORD = "fged vfzd pzgu lfbd"  # Use App Password for Gmail
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

# Automation Credentials (for background jobs)
# Providing these allows scheduled jobs to run without user session
AUTO_TABLEAU_TOKEN_NAME = "test"
AUTO_TABLEAU_TOKEN_KEY = "ECKzRFtESSm35pv3NqPJnw==:2lIPV1UuPrGhvY0J8yOtzs43nbPCKNqn"

# Selenium Extraction Credentials (for headless browser login to Tableau)
# These are your direct Tableau Online login email + password
SELENIUM_USERNAME = "buqitegi@denipl.net"
SELENIUM_PASSWORD = "4YmpJwg0haKy@"
