"""
PelerProxy Bot — Configuration
Loads settings from config.toml (gitignored).
See config.example.toml for the template.
"""
import tomllib
from pathlib import Path

# ==================== PATHS ====================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ACCOUNTS_FILE = BASE_DIR / "webshare_accounts.json"
PROXIES_FILE = BASE_DIR / "proxies.txt"
DB_PATH = DATA_DIR / "pelerproxy.db"
CONFIG_FILE = BASE_DIR / "config.toml"

# ==================== LOAD CONFIG ====================

def _load_config() -> dict:
    """Load config.toml or fail with a clear error."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"config.toml not found at {CONFIG_FILE}\n"
            "Copy config.example.toml to config.toml and fill in your values."
        )
    return tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))

_cfg = _load_config()

# ==================== BOT ====================

BOT_TOKEN = _cfg["bot"]["token"]

# ==================== ADMIN ====================

ADMIN_IDS: list[int] = _cfg["admin"]["ids"]

# ==================== CAPTCHA PROVIDERS ====================

CAPTCHA_DEFAULT_PROVIDER = _cfg["captcha"].get("default_provider", "2captcha")

CAPTCHA_PROVIDERS = {
    "azcaptcha": {
        "name": "AZCaptcha",
        "api_url": "https://azcaptcha.com/in.php",
        "result_url": "https://azcaptcha.com/res.php",
        "api_key": _cfg["captcha"].get("azcaptcha", {}).get("api_key", ""),
    },
    "2captcha": {
        "name": "2Captcha",
        "api_url": "https://2captcha.com/in.php",
        "result_url": "https://2captcha.com/res.php",
        "api_key": _cfg["captcha"].get("2captcha", {}).get("api_key", ""),
    },
}

# ==================== WEBSHARE ====================

FIXED_PASSWORD = _cfg["webshare"]["fixed_password"]
WEBSHARE_RECAPTCHA_SITEKEY = _cfg["webshare"]["recaptcha_sitekey"]
WEBSHARE_REGISTER_URL = _cfg["webshare"]["register_url"]
API_BASE = _cfg["webshare"]["api_base"]

# ==================== PROXY SETTINGS ====================

PROXY_MODE_DEFAULT = _cfg["proxy"].get("mode_default", True)
PROXY_CHECK_TIMEOUT = _cfg["proxy"].get("check_timeout", 15)
PROXY_CHECK_URL = _cfg["proxy"].get("check_url", "http://httpbin.org/ip")
PROXY_MAX_RETRIES = _cfg["proxy"].get("max_retries", 5)

# ==================== LIMITS ====================

MAX_REGISTRATIONS_PER_DAY = _cfg["limits"].get("max_registrations_per_day", 1)
MAX_PROXIES_PER_FETCH = _cfg["limits"].get("max_proxies_per_fetch", 10)
MAX_ACCOUNTS_KEPT = _cfg["limits"].get("max_accounts_kept", 20)