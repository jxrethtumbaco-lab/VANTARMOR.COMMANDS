import runpy
import threading
from pathlib import Path

from abuse_registration_patch import patch_app_file as patch_abuse_protection
from anti_link_registration_patch import patch_app_file as patch_anti_link
from web_server import start_website

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"


def run_bot():
    """Run the Discord bot separately so a bot startup error won't stop the website."""
    try:
        if not APP_FILE.is_file():
            raise FileNotFoundError(f"No encontré el archivo del bot: {APP_FILE}")
        patch_anti_link(APP_FILE)
        patch_abuse_protection(APP_FILE)
        print("Iniciando Vantarmor Commands...")
        runpy.run_path(str(APP_FILE), run_name="__main__")
    except Exception as exc:
        print(f"El bot no pudo iniciar; el sitio web seguirá activo: {type(exc).__name__}: {exc}")


# Start the HTTP service first. The main thread stays alive for Railway's health checks.
server = start_website()
if server is None:
    raise RuntimeError("No se pudo iniciar el sitio: falta website/index.html.")

threading.Thread(target=run_bot, name="vantarmor-bot", daemon=True).start()
print("Servidor web activo; manteniendo el proceso disponible para Railway.")
server.serve_forever()
