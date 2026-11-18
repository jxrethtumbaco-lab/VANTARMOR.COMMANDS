"""Start Railway's website and bot, installing all command modules before launch."""
import runpy
import threading
from pathlib import Path

import web_server
import website_admin_gate
import website_public_config
import website_profile_api
import website_runtime_features
import guild_profile_settings
from abuse_registration_patch import patch_app_file as patch_abuse_protection
from anti_bot_registration_patch import patch_app_file as patch_anti_bot
from anti_link_registration_patch import patch_app_file as patch_anti_link
from cookie_game_patch import patch_app_file as patch_cookie_game
from giveaway_patch import patch_app_file as patch_giveaways
from message_reactions_patch import patch_app as patch_message_reactions
from moderation_prefix_patch import patch_app_file as patch_prefix_moderation
from premium_backup_patch import patch_app_file as patch_premium_backup
from premium_security_patch import patch_app_file as patch_premium_security
from web_server import start_website

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"


def run_bot():
    try:
        if not APP_FILE.is_file():
            raise FileNotFoundError(f"No encontré el archivo del bot: {APP_FILE}")
        patches = (
            ("Anti-Link", patch_anti_link),
            ("Anti-Spam/Anti-Nuke", patch_abuse_protection),
            ("Anti-Bot", patch_anti_bot),
            ("Seguridad Premium", patch_premium_security),
            ("Moderación por prefijo", patch_prefix_moderation),
            ("Reacciones por prefijo", patch_message_reactions),
            ("Bienvenidas y copias", patch_premium_backup),
            ("Cookie y userinfo", patch_cookie_game),
            ("Sorteos", patch_giveaways),
        )
        for label, patch in patches:
            print(f"Registrando comandos: {label}…")
            patch(APP_FILE)
        source = APP_FILE.read_text(encoding="utf-8")
        compile(source, str(APP_FILE), "exec")
        website_runtime_features.install_bot_status_hooks(APP_FILE)
        print("Módulos de comandos registrados. Arrancando Discord…")
        runpy.run_path(str(APP_FILE), run_name="__main__")
    except Exception as exc:
        website_runtime_features.set_bot_status(False)
        print(f"El bot no pudo iniciar: {type(exc).__name__}: {exc}")
        raise


website_runtime_features.install_website_api(web_server.Handler)
website_public_config.install_public_website_config(web_server.Handler)
website_profile_api.install_profile_api(web_server.Handler)
guild_profile_settings.install_guild_profile_settings(web_server.Handler)
website_admin_gate.install_admin_entry(web_server.Handler)
server = start_website()
if server is None:
    raise RuntimeError("No se pudo iniciar el sitio: falta website/index.html.")
threading.Thread(target=run_bot, name="vantarmor-bot", daemon=True).start()
print("Sitio web activo; Discord inicia en un hilo separado.")
threading.Event().wait()
