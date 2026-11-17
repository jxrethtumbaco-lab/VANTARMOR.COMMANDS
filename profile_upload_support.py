"""Safe image-upload support and responsive styling for account/admin panels."""
import base64
import io
import json
import re
import urllib.parse
from pathlib import Path

from PIL import Image, UnidentifiedImageError

import guild_profile_settings

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
IMAGE_DATA_URI = re.compile(r"^data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/=]+)$")
ROOT = Path(__file__).resolve().parent


def _avatar_from_upload(value):
    if not isinstance(value, str) or not value.startswith("data:"):
        return guild_profile_settings._download_avatar(value)
    match = IMAGE_DATA_URI.fullmatch(value)
    if not match:
        raise ValueError("La imagen subida debe ser PNG, JPG, WEBP o GIF.")
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("El archivo de imagen no es válido.") from error
    if not image_bytes or len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("La imagen procesada debe pesar como máximo 2 MB.")
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "GIF"}:
                raise ValueError("La imagen subida debe ser PNG, JPG, WEBP o GIF.")
            if image.width * image.height > 20_000_000:
                raise ValueError("La resolución de la imagen es demasiado grande.")
            image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("El archivo subido no es una imagen válida.") from error
    mime = match.group(1)
    return f"data:image/{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def _install_responsive_styles():
    """Generate and link styles at startup, without changing API authorization."""
    assets = ROOT / "website" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    account_css = r'''/* Account configuration: readable, responsive and aligned with Premium key form. */
[hidden] { display: none !important; }
#bot-profile-settings[hidden] { display: none !important; }
.account-settings { box-sizing:border-box; width:100%; margin:28px 0 0; padding:clamp(20px,4vw,32px); border:1px solid rgba(255,255,255,.14); border-radius:20px; background:linear-gradient(145deg,rgba(18,20,23,.98),rgba(8,9,11,.98)); box-shadow:0 16px 42px rgba(0,0,0,.24); }
.account-settings > .eyebrow { color:#67e8f9; letter-spacing:.18em; font-weight:800; font-size:.78rem; }
.account-settings h3 { margin:8px 0 12px; font-size:clamp(1.25rem,5vw,1.65rem); }
.account-settings > p:not(.eyebrow) { color:#aaaab4; line-height:1.75; }
#guild-profile-form, .guild-profile-form { display:grid; grid-template-columns:1fr; gap:10px; margin-top:22px; }
#guild-profile-form label, .guild-profile-form label { margin-top:8px; color:#e7e7ec; font-size:.95rem; font-weight:650; }
#guild-profile-form input:not([type=file]), #guild-profile-form select, .guild-profile-form input:not([type=file]), .guild-profile-form select { box-sizing:border-box; width:100%; min-height:48px; padding:11px 14px; border:1px solid rgba(255,255,255,.2); border-radius:12px; background:#101114; color:#f5f5f7; font:inherit; }
#guild-profile-form input[type=file], .guild-profile-form input[type=file] { box-sizing:border-box; width:100%; padding:12px; border:1px dashed rgba(255,255,255,.25); border-radius:12px; background:#101114; color:#ddd; font:inherit; }
#guild-profile-form small, #guild-profile-form .hint, .guild-profile-form .hint { color:#a5a5af; line-height:1.6; }
#guild-profile-form .button, .guild-profile-form .button { justify-self:start; margin-top:12px; min-height:48px; }
#avatar-preview { max-width:min(180px,100%); max-height:180px; border-radius:16px; object-fit:cover; }
.account-actions { display:flex; flex-wrap:wrap; gap:10px; margin:18px 0 8px; }
.account-actions .button { margin:0; }
@media(max-width:600px) { .account-settings { padding:20px 16px; } .account-actions { display:grid; grid-template-columns:1fr; } .account-actions .button { width:100%; text-align:center; box-sizing:border-box; } }
'''
    admin_css = r'''/* Admin dashboard: card layout on mobile, no overflowing inline controls. */
[hidden] { display:none !important; }
.admin-page { overflow-x:hidden; }
.admin-shell { box-sizing:border-box; width:min(1100px,100%); margin:0 auto; padding:clamp(20px,4vw,48px) clamp(16px,4vw,28px) 60px; }
.admin-heading { margin-bottom:28px; }
.admin-heading h1 { font-size:clamp(2.4rem,9vw,4.6rem); line-height:1.05; margin:10px 0 14px; overflow-wrap:anywhere; }
.admin-heading > p:last-child, .admin-panel > p { color:#a8a8b2; line-height:1.7; }
.admin-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; align-items:start; }
.admin-panel { box-sizing:border-box; min-width:0; margin:16px 0; padding:clamp(18px,3vw,26px); border:1px solid rgba(255,255,255,.13); border-radius:18px; background:linear-gradient(145deg,rgba(19,20,23,.98),rgba(9,10,12,.98)); box-shadow:0 14px 34px rgba(0,0,0,.22); }
.admin-panel h2 { font-size:clamp(1.35rem,5vw,2rem); line-height:1.2; margin:8px 0 16px; overflow-wrap:anywhere; }
.admin-panel .eyebrow { color:#67e8f9; letter-spacing:.17em; font-size:.76rem; font-weight:800; }
.admin-form { display:grid; grid-template-columns:1fr; gap:10px; }
.admin-form label { margin-top:6px; color:#eee; font-weight:650; }
.admin-form input:not([type=checkbox]):not([type=file]), .admin-form select { box-sizing:border-box; width:100%; min-height:48px; padding:11px 14px; border:1px solid rgba(255,255,255,.2); border-radius:12px; background:#101114; color:#f5f5f7; font:inherit; }
.admin-form input[type=file] { box-sizing:border-box; width:100%; padding:12px; border:1px dashed rgba(255,255,255,.25); border-radius:12px; background:#101114; color:#ddd; font:inherit; }
.admin-form input[type=checkbox] { width:20px; height:20px; accent-color:#64dce9; vertical-align:middle; }
.admin-form .button, .admin-panel > .button { justify-self:start; margin-top:8px; min-height:46px; }
.users-panel, .guild-profile-panel { width:100%; }
.users-heading { display:flex; justify-content:space-between; align-items:center; gap:14px; }
.users-panel table { display:block; width:100%; overflow-x:auto; border-collapse:collapse; white-space:nowrap; }
.users-panel th, .users-panel td { padding:12px 10px; text-align:left; border-bottom:1px solid rgba(255,255,255,.1); }
.admin-status { min-height:1.5em; color:#9fe8c6; overflow-wrap:anywhere; }
.admin-status.error { color:#ff9b9b; }
.guild-profile-form .hint { color:#a8a8b2; line-height:1.6; }
#avatar-preview { max-width:180px; max-height:180px; border-radius:16px; }
@media(max-width:700px) { .admin-grid { grid-template-columns:1fr; gap:0; } .admin-panel { margin:12px 0; } .users-heading { align-items:flex-start; flex-direction:column; } .admin-topbar { gap:8px; } .admin-topbar .brand { max-width:65%; font-size:.8rem; } .admin-topbar > a:last-child { white-space:nowrap; } }
'''
    (assets / "account-settings.css").write_text(account_css, encoding="utf-8")
    (assets / "admin.css").write_text(admin_css, encoding="utf-8")
    index_path = ROOT / "website" / "index.html"
    admin_path = ROOT / "website" / "admin.html"
    for path, tag in (
        (index_path, '<link rel="stylesheet" href="/assets/account-settings.css?v=2">'),
        (admin_path, '<link rel="stylesheet" href="/assets/admin.css?v=2">'),
    ):
        try:
            html = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if tag not in html:
            html = html.replace("</head>", f"  {tag}\n</head>", 1)
        path.write_text(html, encoding="utf-8")


def install_profile_upload_support(handler_class):
    """Allow bounded JSON image uploads and install responsive account/admin styles."""
    _install_responsive_styles()
    guild_profile_settings._download_avatar = _avatar_from_upload
    original_read_json_body = handler_class.read_json_body

    def read_json_body(self):
        if urllib.parse.urlparse(self.path).path != "/api/settings/guild-profile":
            return original_read_json_body(self)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            raise ValueError("Tamaño de solicitud no válido.")
        if not 0 < length <= 3 * 1024 * 1024:
            raise ValueError("La imagen es demasiado grande; el límite de subida es 2 MB.")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("Solicitud no válida.")
        return data

    handler_class.read_json_body = read_json_body
    original_do_get = handler_class.do_GET
    index_path = ROOT / "website" / "index.html"

    def do_get(self):
        if urllib.parse.urlparse(self.path).path not in ("/", "/index.html"):
            return original_do_get(self)
        try:
            html = index_path.read_text(encoding="utf-8")
        except OSError:
            return original_do_get(self)
        script = '<script src="/assets/profile-upload.js?v=2" defer></script>'
        if script not in html:
            html = html.replace("</body>", f"  {script}\n</body>")
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    handler_class.do_GET = do_get


__all__ = ["install_profile_upload_support"]
