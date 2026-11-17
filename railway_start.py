"""Start the website and Discord bot as independent services in one Railway process."""
import runpy
import threading
from pathlib import Path

import web_server
import website_public_config
import website_profile_api
import website_runtime_features
import guild_profile_settings
from abuse_registration_patch import patch_app_file as patch_abuse_protection
from anti_link_registration_patch import patch_app_file as patch_anti_link
from web_server import start_website

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"


def run_bot():
    try:
        if not APP_FILE.is_file():
            raise FileNotFoundError(f"No encontré el archivo del bot: {APP_FILE}")
        patch_anti_link(APP_FILE)
        patch_abuse_protection(APP_FILE)
        website_runtime_features.install_bot_status_hooks(APP_FILE)
        print("Iniciando Vantarmor Commands...")
        runpy.run_path(str(APP_FILE), run_name="__main__")
    except Exception as exc:
        website_runtime_features.set_bot_status(False)
        print(f"El bot no pudo iniciar; el sitio web seguirá activo: {type(exc).__name__}: {exc}")


website_runtime_features.install_website_api(web_server.Handler)
website_public_config.install_public_website_config(web_server.Handler)
website_profile_api.install_profile_api(web_server.Handler)
guild_profile_settings.install_guild_profile_settings(web_server.Handler)
server = start_website()
if server is None:
    raise RuntimeError("No se pudo iniciar el sitio: falta website/index.html.")
threading.Thread(target=run_bot, name="vantarmor-bot", daemon=True).start()
print("Web de Vantarmor escuchando; el proceso queda activo para Railway.")
server.serve_forever()
