"""Add the server-profile editor script to the protected admin page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADMIN_HTML = ROOT / "website" / "admin.html"
SCRIPT_TAG = '<script src="/assets/admin-profile.js?v=3" defer></script>'


def install_admin_profile_ui() -> None:
    html = ADMIN_HTML.read_text(encoding="utf-8")
    if SCRIPT_TAG not in html:
        html = html.replace("</body>", f"  {SCRIPT_TAG}\n</body>", 1)
        ADMIN_HTML.write_text(html, encoding="utf-8")
