import runpy
from pathlib import Path

from abuse_registration_patch import patch_app_file as patch_abuse_protection
from anti_link_registration_patch import patch_app_file as patch_anti_link
from web_server import start_website

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"

if not APP_FILE.is_file():
    raise FileNotFoundError(f"No encontré el archivo del bot: {APP_FILE}")

patch_anti_link(APP_FILE)
patch_abuse_protection(APP_FILE)
start_website()
print("Iniciando Vantarmor Commands...")
runpy.run_path(str(APP_FILE), run_name="__main__")
