import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR / "repos"
INDEX_DIR = BASE_DIR / "indexes"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

REPO_DIR.mkdir(exist_ok=True)
INDEX_DIR.mkdir(exist_ok=True)


def read_windows_env(name: str):
    if sys.platform != "win32":
        return None

    try:
        import winreg
    except ImportError:
        return None

    locations = [
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]

    for root, path in locations:
        try:
            with winreg.OpenKey(root, path) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    return str(value).strip()
        except OSError:
            continue

    return None


def get_setting(name: str, default: str = ""):
    dotenv_value = os.getenv(name)
    registry_value = read_windows_env(name)
    value = registry_value or dotenv_value or default
    return value.strip() if isinstance(value, str) else value


def get_deepseek_client():
    return OpenAI(
        api_key=get_setting("DEEPSEEK_API_KEY"),
        base_url=get_setting("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
