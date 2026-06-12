import os
# ============================================================
# CONFIGURATION FILE
# ============================================================
# This file stores configuration values including API keys
#
# **PLACE YOUR GEMINI API KEY HERE** ↓

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Tableau Configuration (optional - can also be set via web form)
TABLEAU_SERVER_URL = "https://us-east-1.online.tableau.com/"
TABLEAU_SITE_ID = "carlosadarusa-384949925f"

# AI Model Configuration
# NOTE: As of the current key/tier, gemini-2.0-flash and gemini-2.5-pro return
# 429 "limit: 0" (no free-tier quota). gemini-2.5-flash and gemini-2.5-flash-lite
# work. Keep this on a model with quota or insights will fail.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Cache AI insights to disk so an identical report (same data + dashboard name)
# replays instantly with NO API call. Pre-run a report once before a live demo and
# the on-stage run is offline/instant and cannot hit a rate limit.
ENABLE_INSIGHTS_CACHE = True
print(f"[CONFIG] Loaded from: {__file__} | Model: {GEMINI_MODEL}")
ENABLE_AI_INSIGHTS = True  # Set to False to disable AI insights

# Anthropic Configuration (Alternative)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
AI_PROVIDER = "gemini"  # "gemini" or "anthropic"

# Email Automation Configuration (Gmail/Outlook)
EMAIL_SENDER = "sharathtableaupoc@gmail.com"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

# Automation Credentials (for background jobs)
# Providing these allows scheduled jobs to run without user session
AUTO_TABLEAU_TOKEN_NAME = "tableau"
AUTO_TABLEAU_TOKEN_KEY = os.environ.get("AUTO_TABLEAU_TOKEN_KEY", "")

# Selenium Extraction Credentials (for headless browser login to Tableau)
# These are your direct Tableau Online login email + password
SELENIUM_USERNAME = "car.los.a.daru.sa@gmail.com"
SELENIUM_PASSWORD = os.environ.get("SELENIUM_PASSWORD", "")

# ── Local development overrides (config_local.py is gitignored) ──
# On Render/production, secrets come from environment variables above.
try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass
