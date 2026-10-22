"""
PelerProxy Bot — Entry Point
Modular Webshare proxy account creator Telegram bot.
"""
import warnings
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
)

import config
from database import init_db, migrate_from_json
from handlers.start import start, button_handler
from handlers.register import build_conv_handler
from handlers.proxies import alive_command
from handlers.admin import (
    admin_callback_handler,
    build_admin_conv_handler,
)

# ==================== LOGGING ====================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("pelerproxy")

warnings.filterwarnings("ignore", message=".*per_message.*")
warnings.filterwarnings("ignore", message=".*CallbackQueryHandler.*")


# ==================== MAIN ====================

def main():
    # Init database + migrate old JSON data
    log.info("Initializing database...")
    init_db()
    migrate_from_json()

    # Build application
    app = Application.builder().token(config.BOT_TOKEN).build()

    # Register handlers
    # /start command
    app.add_handler(CommandHandler("start", start))

    # /alive — re-check pool + export every alive proxy as TXT
    app.add_handler(CommandHandler("alive", alive_command))
    app.add_handler(CommandHandler("allproxies", alive_command))

    # Main menu callbacks: auto, proxies, alive_proxies, start, admin
    app.add_handler(CallbackQueryHandler(
        button_handler, pattern="^(auto|proxies|alive_proxies|start|admin)$"
    ))

    # Manual registration conversation handler
    app.add_handler(build_conv_handler())

    # Admin conversation handler (broadcast, ban, reset)
    app.add_handler(build_admin_conv_handler())

    # Admin callback handler (stats, users, ban/unban, reset, proxy, captcha settings)
    app.add_handler(CallbackQueryHandler(
        admin_callback_handler,
        pattern="^(admin_stats|admin_users|admin_broadcast|admin_ban_menu|admin_reset|"
                "admin_user_|admin_ban_|admin_unban_|admin_reset_|admin_users_p|"
                "admin_proxy_menu|admin_proxy_toggle|admin_proxy_check|admin_proxy_prune|"
                "admin_proxy_alive|"
                "admin_captcha_menu|admin_captcha_switch|admin_captcha_key)",
    ))

    log.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()