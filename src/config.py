import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_MODEL_NAME = os.getenv("GITHUB_MODEL_NAME", "microsoft/Phi-3.5-mini-instruct")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEFAULT_HEADLESS = os.getenv("DEFAULT_HEADLESS", "False").lower() == "true"
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "30000"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "1"))

def validate_config():
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is required but not found in environment variables. Please set it in your .env file.")
    
    print(f"✅ Configuration loaded:")
    print(f"   • OpenRouter API Key: {'Set (masked)' if OPENROUTER_API_KEY else 'Not set - REQUIRED'}")
    print(f"   • Model: Google Gemini-2.0-Flash-Exp (Free) - via OpenRouter")
    print(f"   • Log Level: {LOG_LEVEL}")
    print(f"   • Browser Headless: {DEFAULT_HEADLESS}")

if __name__ == "__main__":
    validate_config()