"""PelerProxy Bot — Configuration
Loads settings from config.toml (gitignored).
See config.example.toml for the template.
"""
import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "pelerproxy.db"
CONFIG_FILE = BASE_DIR / "config.toml"

def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("config.toml not found")
    return tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))

_cfg = _load_config()

BOT_TOKEN = _cfg["bot"]["token"]
ADMIN_IDS: list[int] = _cfg["admin"]["ids"]
CAPTCHA_DEFAULT_PROVIDER = _cfg["captcha"].get("default_provider", "2captcha")
CAPTCHA_PROVIDERS = {
    "azcaptcha": {"name": "AZCaptcha", "api_url": "https://azcaptcha.com/in.php", "result_url": "https://azcaptcha.com/res.php", "api_key": _cfg["captcha"].get("azcaptcha", {}).get("api_key", "")},
    "2captcha": {"name": "2Captcha", "api_url": "https://2captcha.com/in.php", "result_url": "https://2captcha.com/res.php", "api_key": _cfg["captcha"].get("2captcha", {}).get("api_key", "")},
}
