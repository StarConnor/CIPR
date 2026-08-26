# load environment variables from .env file
from dotenv import load_dotenv
import os


def get_model_api(model_name, base_url=None, agent=None):
    load_dotenv()  # Load environment variables from .env file

    if model_name in ["deepseek-v4-flash", "deepseek-v4-pro"]:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        api_base_url = os.getenv("DEEPSEEK_BASE_URL")
        if agent == "cc_cli":
            api_base_url = os.getenv("DEEPSEEK_ANTHROPIC_LIKE_BASE_URL")
    
    elif model_name in ['gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.3-codex']:
        api_key = os.getenv("CODEX_API_KEY")
        api_base_url = os.getenv("CODEX_BASE_URL")

    elif model_name.startswith('gemini-') or model_name in ['pro', 'flash', 'flash-lite']:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        api_base_url = os.getenv("GOOGLE_GEMINI_BASE_URL") or os.getenv("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com"
    
    elif model_name in ['doubao-seed-2-0-pro-260215']:
        api_key = os.getenv("VOLCENGINE_API_KEY")
        api_base_url = os.getenv("VOLCENGINE_BASE_URL")
    
    elif model_name == 'cheap_claude' or model_name.startswith('claude-'):
        api_key = os.getenv("CHEAP_API_KEY")
        api_base_url = os.getenv("CHEAP_BASE_URL")
    
    else:
        api_key = os.getenv("V_API_KEY")
        api_base_url = os.getenv("V_BASE_URL")

    return api_key, api_base_url
