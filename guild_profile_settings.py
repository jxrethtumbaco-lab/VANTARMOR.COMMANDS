from pathlib import Path
import base64
import ipaddress
import io
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, UnidentifiedImageError

DISCORD_API = "https://discord.com/api/v10"
MAX_AVATAR_BYTES = 5 * 1024 * 1024


def _discord_json(path, *, token, method="GET", payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(DISCORD_API + path, data=body, method=method, headers={"Authorization": f"Bot {token}", "Accept": "application/json", "User-Agent": "Vantarmor-Commands/1.0", **({"Content-Type": "application/json"} if body is not None else {})})
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = response.read(1024 * 1024)
        return json.loads(raw.decode("utf-8")) if raw else {}


def _download_avatar(value):
    if value.startswith("data:"):
        import re
        match = re.fullmatch(r"data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/=]+)", value)
        if not match:
            raise ValueError("La imagen debe ser PNG, JPG, WEBP o GIF.")
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ValueError("El archivo de imagen no es válido.") from error
        if not raw or len(raw) > 2 * 1024 * 1024:
            raise ValueError("La imagen debe pesar como máximo 2 MB.")
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP", "GIF"} or image.width * image.height > 20_000_000:
                    raise ValueError("La imagen no es compatible o tiene demasiada resolución.")
                image.verify()
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("El archivo no contiene una imagen válida.") from error
        return f"data:image/{match.group(1)};base64,{base64.b64encode(raw).decode('ascii')}"

    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("La imagen debe usar un enlace HTTPS público.")
    host = parsed.hostname.rstrip(".")
    if host.casefold() == "localhost" or host.casefold().endswith(".local"):
        raise ValueError("La URL no puede apuntar a un host local.")
    try:
        addresses = {entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as error:
        raise ValueError("No se pudo resolver el host de la imagen.") from error
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("La URL debe apuntar a un servidor público.")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, new_url): return None
    try:
        with urllib.request.build_opener(NoRedirect).open(urllib.request.Request(value, headers={"User-Agent": "Vantarmor-Commands/1.0"}), timeout=10) as response:
            if not response.headers.get_content_type().startswith("image/"): raise ValueError("El enlace debe apuntar directamente a una imagen.")
            raw = response.read(MAX_AVATAR_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ValueError("No se pudo descargar la imagen.") from error
    if not raw or len(raw) > MAX_AVATAR_BYTES: raise ValueError("La imagen debe pesar como máximo 5 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "GIF"} or image.width * image.height > 20_000_000: raise ValueError("La imagen no es compatible o tiene demasiada resolución.")
            image.verify(); fmt = image.format.lower()
    except (UnidentifiedImageError, OSError) as error: raise ValueError("El enlace no contiene una imagen válida.") from error
    return f"data:image/{'jpeg' if fmt == 'jpg' else fmt};base64,{base64.b64encode(raw).decode('ascii')}"


def _manageable_guild_ids(session):
    import web_server
    try: guilds = web_server.discord_request("/users/@me/guilds", token=session["access_token"])
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as error: raise ValueError("No pude consultar tus servidores; inicia sesión otra vez.") from error
    return {str(g["id"]): g.get("name", "Servidor") for g in guilds if g.get("owner") or int(g.get("permissions", "0")) & (0x8 | 0x20)}


def _bot_member_token(guild_id):
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token: raise ValueError("Falta configurar DISCORD_TOKEN en Railway.")
    try: _discord_json(f"/guilds/{guild_id}", token=token)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as error: raise ValueError("El bot no está unido a ese servidor o ya no tiene acceso.") from error
    return token


def install_guild_profile_settings(handler_class):
    old_get, old_post = handler_class.do_GET, handler_class.do_POST
    def do_get(self):
        if urllib.parse.urlparse(self.path).path != "/api/settings/guilds": return old_get(self)
        session = self.get_session()
        if not session: return self.send_error_json("Inicia sesión con Discord.", 401)
        try:
            manageable = _manageable_guild_ids(session); present = []
            for guild_id, name in manageable.items():
                try: _bot_member_token(guild_id)
                except ValueError: continue
                present.append({"id": guild_id, "name": name})
            return self.send_json({"guilds": present})
        except ValueError as error: return self.send_error_json(str(error), 502)
    def do_post(self):
        if urllib.parse.urlparse(self.path).path != "/api/settings/guild-profile": return old_post(self)
        session = self.get_session()
        if not session: return self.send_error_json("Inicia sesión con Discord primero.", 401)
        if not self.require_csrf(session): return self.send_error_json("Verificación de seguridad fallida. Recarga e inténtalo otra vez.", 403)
        try:
            data = self.read_json_body(); guild_id = str(data.get("guild_id", "")); nickname = str(data.get("nickname", "")).strip(); avatar_data = str(data.get("avatar_url", "")).strip()
            if not guild_id.isdecimal(): raise ValueError("Selecciona un servidor válido.")
            if len(nickname) > 32: raise ValueError("El apodo no puede superar 32 caracteres.")
            manageable = _manageable_guild_ids(session)
            if guild_id not in manageable: raise ValueError("Debes ser propietario o administrador del servidor seleccionado.")
            token = _bot_member_token(guild_id)
            payload = {"nick": nickname or None}
            if avatar_data: payload["avatar"] = _download_avatar(avatar_data)
            _discord_json(f"/guilds/{guild_id}/members/@me", token=token, method="PATCH", payload=payload)
            return self.send_json({"ok": True, "message": f"Cambios aplicados gratis únicamente en {manageable[guild_id]}."})
        except (ValueError, json.JSONDecodeError) as error: return self.send_error_json(str(error), 400)
        except urllib.error.HTTPError as error:
            if error.code == 403: return self.send_error_json("Discord rechazó el cambio. Revisa permisos del bot y jerarquía de roles.", 403)
            return self.send_error_json("Discord no pudo actualizar el perfil del bot.", 502)
        except (urllib.error.URLError, OSError): return self.send_error_json("No se pudo conectar con Discord.", 502)
    handler_class.do_GET = do_get
    handler_class.do_POST = do_post


__all__ = ["install_guild_profile_settings"]
