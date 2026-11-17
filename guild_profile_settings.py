"""Per-guild visual nickname and avatar settings for the current bot member."""
import base64
import binascii
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, UnidentifiedImageError

DISCORD_API = "https://discord.com/api/v10"
MAX_UPLOAD = 2 * 1024 * 1024
MAX_BODY = 3 * 1024 * 1024


def _discord_json(path, *, token, method="GET", payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        DISCORD_API + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bot {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Vantarmor-Commands/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = response.read(1024 * 1024)
        return json.loads(raw.decode("utf-8")) if raw else {}


def _manageable_guilds(session):
    import web_server
    try:
        guilds = web_server.discord_request("/users/@me/guilds", token=session["access_token"])
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as error:
        raise ValueError("No pude consultar tus servidores; inicia sesión otra vez.") from error
    return {
        str(guild["id"]): guild.get("name", "Servidor")
        for guild in guilds
        if guild.get("owner") or int(guild.get("permissions", "0")) & (0x8 | 0x20)
    }


def _bot_token_for_guild(guild_id):
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ValueError("Falta configurar DISCORD_TOKEN en Railway.")
    try:
        _discord_json(f"/guilds/{guild_id}", token=token)
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            raise ValueError("El bot no está unido a ese servidor o ya no tiene acceso.") from error
        raise ValueError("Discord no pudo validar la pertenencia del bot al servidor.") from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise ValueError("No se pudo validar el servidor con Discord.") from error
    return token


def _validated_avatar(data_uri):
    match = re.fullmatch(r"data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/=]+)", data_uri)
    if not match:
        raise ValueError("Sube una imagen PNG, JPG, WEBP o GIF válida.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("El archivo de imagen no es válido.") from error
    if not raw or len(raw) > MAX_UPLOAD:
        raise ValueError("La imagen debe pesar como máximo 2 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            expected = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP", "gif": "GIF"}[match.group(1)]
            if image.format != expected or image.width * image.height > 20_000_000:
                raise ValueError("La imagen no es compatible o tiene demasiada resolución.")
            image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("El archivo no contiene una imagen válida.") from error
    return f"data:image/{match.group(1)};base64,{base64.b64encode(raw).decode('ascii')}"


def install_guild_profile_settings(handler_class):
    old_get, old_post = handler_class.do_GET, handler_class.do_POST

    def do_get(self):
        if urllib.parse.urlparse(self.path).path != "/api/settings/guilds":
            return old_get(self)
        session = self.get_session()
        if not session:
            return self.send_error_json("Inicia sesión con Discord.", 401)
        try:
            manageable = _manageable_guilds(session)
            present = []
            for guild_id, name in manageable.items():
                try:
                    _bot_token_for_guild(guild_id)
                except ValueError:
                    continue
                present.append({"id": guild_id, "name": name})
            return self.send_json({"guilds": present})
        except ValueError as error:
            return self.send_error_json(str(error), 502)

    def do_post(self):
        if urllib.parse.urlparse(self.path).path != "/api/settings/guild-profile":
            return old_post(self)
        session = self.get_session()
        if not session:
            return self.send_error_json("Inicia sesión con Discord primero.", 401)
        if not self.require_csrf(session):
            return self.send_error_json("Verificación de seguridad fallida. Recarga e inténtalo otra vez.", 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("La solicitud es demasiado grande; la imagen debe pesar como máximo 2 MB.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Solicitud no válida.")
            guild_id = str(data.get("guild_id", ""))
            nickname = str(data.get("nickname", "")).strip()
            avatar_data = str(data.get("avatar_url", "")).strip()
            if not guild_id.isdecimal():
                raise ValueError("Selecciona un servidor válido.")
            if not nickname and not avatar_data:
                raise ValueError("Indica un apodo o selecciona una imagen antes de guardar.")
            if len(nickname) > 32:
                raise ValueError("El apodo no puede superar 32 caracteres.")
            manageable = _manageable_guilds(session)
            if guild_id not in manageable:
                raise ValueError("El servidor seleccionado ya no está disponible o no tienes permisos de administración.")
            token = _bot_token_for_guild(guild_id)
            payload = {"nick": nickname or None}
            if avatar_data:
                payload["avatar"] = _validated_avatar(avatar_data)
            _discord_json(f"/guilds/{guild_id}/members/@me", token=token, method="PATCH", payload=payload)
            return self.send_json({"ok": True, "message": f"Apodo y avatar visual actualizados solo en {manageable[guild_id]}."})
        except (ValueError, json.JSONDecodeError) as error:
            return self.send_error_json(str(error), 400)
        except urllib.error.HTTPError as error:
            if error.code == 403:
                return self.send_error_json("Discord rechazó el cambio; comprueba el rol y los permisos del bot.", 403)
            if error.code == 404:
                return self.send_error_json("El bot ya no está en ese servidor; actualiza la lista y selecciona otro.", 400)
            return self.send_error_json("Discord no pudo actualizar el perfil del bot.", 502)
        except (urllib.error.URLError, OSError):
            return self.send_error_json("No se pudo conectar con Discord.", 502)

    handler_class.do_GET = do_get
    handler_class.do_POST = do_post


__all__ = ["install_guild_profile_settings"]
