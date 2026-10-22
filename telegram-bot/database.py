"""
PelerProxy Bot — SQLite Database Layer
Handles schema initialization, CRUD operations, and migration from JSON.
"""
import sqlite3
import time
from pathlib import Path
from typing import Optional

import config

# ==================== CONNECTION ====================

def get_db() -> sqlite3.Connection:
    """Get a database connection with WAL mode and foreign keys enabled."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ==================== INIT ====================

def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at INTEGER NOT NULL,
            last_activity INTEGER NOT NULL,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            password TEXT,
            token TEXT,
            created_at INTEGER NOT NULL,
            proxy_count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            proxy_string TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            is_alive INTEGER DEFAULT 1,
            last_checked INTEGER DEFAULT 0,
            FOREIGN KEY (registration_id) REFERENCES registrations(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ==================== USERS ====================

def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> dict:
    """Get existing user or create a new one. Returns user dict."""
    conn = get_db()
    now = int(time.time())

    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    if user:
        conn.execute(
            "UPDATE users SET last_activity = ?, username = ?, first_name = ? WHERE user_id = ?",
            (now, username, first_name, user_id),
        )
        conn.commit()
        result = dict(user)
        result["last_activity"] = now
    else:
        # First user is admin if they're in ADMIN_IDS
        is_admin = 1 if user_id in config.ADMIN_IDS else 0
        conn.execute(
            "INSERT INTO users (user_id, username, first_name, joined_at, last_activity, is_admin) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, first_name, now, now, is_admin),
        )
        conn.commit()
        result = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "joined_at": now,
            "last_activity": now,
            "is_banned": 0,
            "is_admin": is_admin,
        }

    conn.close()
    return result


def is_banned(user_id: int) -> bool:
    conn = get_db()
    row = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return bool(row and row["is_banned"])


def is_admin(user_id: int) -> bool:
    # Always check ADMIN_IDS first (fallback for pre-existing users)
    if user_id in config.ADMIN_IDS:
        return True
    conn = get_db()
    row = conn.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return bool(row and row["is_admin"])


def get_all_users(limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY last_activity DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_users() -> int:
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    conn.close()
    return row["cnt"] if row else 0


def ban_user(user_id: int):
    conn = get_db()
    conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unban_user(user_id: int):
    conn = get_db()
    conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ==================== REGISTRATIONS ====================

def add_registration(user_id: int, email: str, password: str, token: str, proxy_count: int = 0) -> int:
    """Add a new registration. Returns the registration ID."""
    conn = get_db()
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO registrations (user_id, email, password, token, created_at, proxy_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, email, password, token, now, proxy_count),
    )
    conn.commit()
    reg_id = cur.lastrowid
    conn.close()
    return reg_id


def get_today_registration_count(user_id: int) -> int:
    """Count registrations this user made today."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM registrations "
        "WHERE user_id = ? AND date(created_at, 'unixepoch') = date('now')",
        (user_id,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def can_register_today(user_id: int) -> tuple[bool, str]:
    """Check if user can register today. Returns (can_register, reason)."""
    if is_banned(user_id):
        return False, "🚫 You are banned from using this bot."

    count = get_today_registration_count(user_id)
    if count >= config.MAX_REGISTRATIONS_PER_DAY:
        return False, f"⏳ You've reached the daily limit ({config.MAX_REGISTRATIONS_PER_DAY}x per day). Try again tomorrow."

    return True, ""


def get_user_registrations(user_id: int, limit: int = 10) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM registrations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_registration(user_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM registrations WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def count_today_registrations() -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM registrations WHERE date(created_at, 'unixepoch') = date('now')"
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def delete_today_registrations(user_id: int):
    """Admin: delete today's registrations for a user (reset limit)."""
    conn = get_db()
    conn.execute(
        "DELETE FROM registrations WHERE user_id = ? AND date(created_at, 'unixepoch') = date('now')",
        (user_id,),
    )
    conn.commit()
    conn.close()


# ==================== PROXIES ====================

def add_proxies(registration_id: int, proxy_strings: list[str]):
    """Add proxy records for a registration (idempotent — skips duplicates)."""
    conn = get_db()
    now = int(time.time())
    added = 0
    for ps in proxy_strings:
        try:
            host, port, user, pw = ps.split(":", 3)
        except ValueError:
            continue
        exists = conn.execute(
            "SELECT 1 FROM proxies WHERE registration_id = ? AND proxy_string = ? LIMIT 1",
            (registration_id, ps),
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO proxies (registration_id, host, port, username, password, proxy_string, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (registration_id, host, int(port), user, pw, ps, now),
        )
        added += 1
    conn.commit()
    conn.close()
    return added


def get_recent_proxies(limit: int = 50) -> list[str]:
    """Get recent proxy strings from admin accounts only (proxy-pool use)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT p.proxy_string FROM proxies p "
        "JOIN registrations r ON p.registration_id = r.id "
        "JOIN users u ON r.user_id = u.user_id "
        "WHERE u.is_admin = 1 "
        "ORDER BY p.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [r["proxy_string"] for r in rows]


def get_proxies_for_registration(registration_id: int) -> list[str]:
    conn = get_db()
    rows = conn.execute(
        "SELECT proxy_string FROM proxies WHERE registration_id = ?",
        (registration_id,),
    ).fetchall()
    conn.close()
    return [r["proxy_string"] for r in rows]


def count_proxies() -> int:
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM proxies").fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_used_emails() -> set[str]:
    """Emails already used for a registration — skip them when picking new ones."""
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT email FROM registrations").fetchall()
    conn.close()
    return {r["email"].lower() for r in rows}


def count_alive_proxies() -> int:
    """Count alive proxies from admin accounts only (proxy pool)."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM proxies p "
        "JOIN registrations r ON p.registration_id = r.id "
        "JOIN users u ON r.user_id = u.user_id "
        "WHERE p.is_alive = 1 AND u.is_admin = 1"
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_alive_proxies(limit: int = 50) -> list[str]:
    """Get alive proxies from admin accounts only (proxy pool)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT p.proxy_string FROM proxies p "
        "JOIN registrations r ON p.registration_id = r.id "
        "JOIN users u ON r.user_id = u.user_id "
        "WHERE p.is_alive = 1 AND u.is_admin = 1 "
        "ORDER BY RANDOM() LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [r["proxy_string"] for r in rows]


def get_all_alive_proxies(limit: int = 5000, user_id: int | None = None) -> list[str]:
    """
    List every ALIVE proxy in scope.
    user_id=None → whole pool (admin export); otherwise only that user's accounts.
    """
    conn = get_db()
    if user_id is None:
        rows = conn.execute(
            "SELECT DISTINCT p.proxy_string FROM proxies p "
            "WHERE p.is_alive = 1 "
            "ORDER BY p.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT p.proxy_string FROM proxies p "
            "JOIN registrations r ON p.registration_id = r.id "
            "WHERE p.is_alive = 1 AND r.user_id = ? "
            "ORDER BY p.id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    conn.close()
    return [r["proxy_string"] for r in rows]


def get_all_proxy_strings(limit: int = 5000, user_id: int | None = None) -> list[str]:
    """
    List every proxy (alive + dead) in scope — used for bulk health re-checks.
    user_id=None → whole pool; otherwise only that user's accounts.
    """
    conn = get_db()
    if user_id is None:
        rows = conn.execute(
            "SELECT DISTINCT p.proxy_string FROM proxies p "
            "ORDER BY p.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT p.proxy_string FROM proxies p "
            "JOIN registrations r ON p.registration_id = r.id "
            "WHERE r.user_id = ? "
            "ORDER BY p.id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    conn.close()
    return [r["proxy_string"] for r in rows]


def count_all_proxies(user_id: int | None = None) -> int:
    """Count every proxy (alive + dead) in scope."""
    conn = get_db()
    if user_id is None:
        row = conn.execute("SELECT COUNT(*) as cnt FROM proxies").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM proxies p "
            "JOIN registrations r ON p.registration_id = r.id "
            "WHERE r.user_id = ?",
            (user_id,),
        ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def mark_proxy_alive(proxy_string: str):
    conn = get_db()
    now = int(time.time())
    conn.execute(
        "UPDATE proxies SET is_alive = 1, last_checked = ? WHERE proxy_string = ?",
        (now, proxy_string),
    )
    conn.commit()
    conn.close()


def mark_proxy_dead(proxy_string: str):
    conn = get_db()
    now = int(time.time())
    conn.execute(
        "UPDATE proxies SET is_alive = 0, last_checked = ? WHERE proxy_string = ?",
        (now, proxy_string),
    )
    conn.commit()
    conn.close()


def delete_dead_proxies() -> int:
    """Remove dead proxies from admin accounts only (proxy pool). Returns count deleted."""
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM proxies WHERE is_alive = 0 "
        "AND registration_id IN ("
        "  SELECT r.id FROM registrations r "
        "  JOIN users u ON r.user_id = u.user_id "
        "  WHERE u.is_admin = 1"
        ")"
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted


# ==================== SETTINGS ====================

def get_setting(key: str, default: str = None) -> str | None:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )
    conn.commit()
    conn.close()


def get_proxy_mode() -> bool:
    """Check if proxy mode is enabled. Default: True."""
    val = get_setting("proxy_mode")
    if val is None:
        return config.PROXY_MODE_DEFAULT
    return val.lower() == "true"


def toggle_proxy_mode() -> bool:
    """Toggle proxy mode. Returns new state."""
    current = get_proxy_mode()
    new_val = not current
    set_setting("proxy_mode", "true" if new_val else "false")
    return new_val


def set_proxy_mode(val: bool):
    """Set proxy mode directly."""
    set_setting("proxy_mode", "true" if val else "false")


# ==================== STATS ====================

# ==================== CAPTCHA SETTINGS ====================

def get_captcha_provider() -> str:
    """Get the active captcha provider. Default from config."""
    val = get_setting("captcha_provider")
    if val is None:
        return config.CAPTCHA_DEFAULT_PROVIDER
    return val


def set_captcha_provider(provider: str):
    """Set the active captcha provider."""
    set_setting("captcha_provider", provider)


def get_captcha_api_key(provider: str = None) -> str:
    """
    Get the API key for the active provider.
    Checks DB first, then falls back to config.
    """
    if provider is None:
        provider = get_captcha_provider()
    # Check DB first (admin-set key)
    val = get_setting(f"captcha_key_{provider}")
    if val:
        return val
    # Fallback to config
    provider_config = config.CAPTCHA_PROVIDERS.get(provider, {})
    return provider_config.get("api_key", "")


def set_captcha_api_key(provider: str, api_key: str):
    """Set the API key for a captcha provider."""
    set_setting(f"captcha_key_{provider}", api_key)


def get_captcha_provider_info() -> dict:
    """Get full info about the active captcha provider."""
    provider = get_captcha_provider()
    provider_config = config.CAPTCHA_PROVIDERS.get(provider, {})
    return {
        "provider": provider,
        "name": provider_config.get("name", provider),
        "api_url": provider_config.get("api_url", ""),
        "result_url": provider_config.get("result_url", ""),
        "api_key": get_captcha_api_key(provider),
        "api_key_masked": _mask_key(get_captcha_api_key(provider)),
    }


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return key
    return key[:4] + "..." + key[-4:]


# ==================== STATS ====================

def get_stats() -> dict:
    """Get dashboard stats."""
    return {
        "total_users": count_users(),
        "today_registrations": count_today_registrations(),
        "total_proxies": count_proxies(),
        "alive_proxies": count_alive_proxies(),
        "proxy_mode": get_proxy_mode(),
        "captcha_provider": get_captcha_provider(),
    }


# ==================== MIGRATION ====================

def migrate_from_json():
    """Import existing webshare_accounts.json data into SQLite."""
    if not config.ACCOUNTS_FILE.exists():
        return

    import json
    try:
        data = json.loads(config.ACCOUNTS_FILE.read_text(encoding="utf-8"))
        accounts = data.get("accounts", [])
    except Exception:
        return

    if not accounts:
        return

    conn = get_db()
    now = int(time.time())
    migrated = 0

    for acc in accounts:
        email = acc.get("email", "")
        if not email:
            continue

        # Check if already exists
        existing = conn.execute(
            "SELECT id FROM registrations WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            continue

        # Find or create a system user for migrated accounts
        sys_user = conn.execute("SELECT user_id FROM users WHERE user_id = 0").fetchone()
        if not sys_user:
            conn.execute(
                "INSERT INTO users (user_id, username, first_name, joined_at, last_activity) "
                "VALUES (0, 'migrated', 'Migrated', ?, ?)",
                (now, now),
            )

        reg_id = conn.execute(
            "INSERT INTO registrations (user_id, email, password, token, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (0, email, acc.get("password", ""), acc.get("token", ""), acc.get("registered_at", now)),
        ).lastrowid
        migrated += 1

    conn.commit()
    conn.close()

    if migrated > 0:
        # Rename the JSON file so we don't re-migrate
        config.ACCOUNTS_FILE.rename(config.ACCOUNTS_FILE.with_suffix(".json.bak"))