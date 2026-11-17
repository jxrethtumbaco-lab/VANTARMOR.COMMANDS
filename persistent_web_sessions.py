"""Persist Discord OAuth sessions across website restarts using refresh tokens.

For sessions to survive Railway container replacement, configure
VANTARMOR_DATA_DIR to point at a persistent volume.
"""
import base64
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import web_server
from premium_store import register_web_user

_LOCK = threading.RLock()
_SESSION_FILE = Path(os.getenv("VANTARMOR_DATA_DIR", ".")) / "website_sessions.json"
SESSION_MAX_AGE = 30 * 24 * 60 * 60


def _load():
    try:
        value = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(sessions):
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = _SESSION_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(sessions, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(_SESSION_FILE)
    try:
        os.chmod(_SESSION_FILE, 0o600)
    except OSError:
        pass


def _refresh(session):
    cfg = web_server.oauth_config()
    refresh_token = session.get("refresh_token")
    if not refresh_token or not cfg.get("client_id") or not cfg.get("client_secret"):
        return False
    basic = base64.b64encode(f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
    tokens = web_server.discord_request(
        "/oauth2/token",
        form={"grant_type": "refresh_token", "refresh_token": refresh_token},
        basic=basic,
    )
    session["access_token"] = tokens["access_token"]
    session["refresh_token"] = tokens.get("refresh_token", refresh_token)
    session["access_expires"] = time.time() + int(tokens.get("expires_in", 3600))
    session["expires"] = time.time() + SESSION_MAX_AGE
    return True


def install_persistent_sessions(handler_class):
    """Install callback, refresh, persistence, and logout behavior on web handler."""
    def get_session(self):
        sid = self.get_cookie("vantarmor_session")
        if not sid:
            return None
        with _LOCK, web_server.LOCK:
            session = web_server.SESSIONS.get(sid)
            if session is None:
                session = _load().get(sid)
                if session:
                    web_server.SESSIONS[sid] = session
            if not session or session.get("expires", 0) <= time.time():
                web_server.SESSIONS.pop(sid, None)
                saved = _load()
                if saved.pop(sid, None) is not None:
                    _save(saved)
                return None
            try:
                if session.get("access_expires", 0) <= time.time() + 60:
                    if not _refresh(session):
                        return None
                saved = _load()
                saved[sid] = session
                _save(saved)
            except (HTTPError, URLError, OSError, KeyError, ValueError):
                return None
            return session

    old_get = handler_class.do_GET

    def do_get(self):
        path = urlparse(self.path).path
        if path == "/auth/callback":
            cfg = web_server.oauth_config()
            query = parse_qs(urlparse(self.path).query)
            state = query.get("state", [""])[0]
            if not state or not secrets.compare_digest(state, self.get_cookie("vantarmor_oauth_state") or ""):
                return self.send_error_json("Falló la verificación de inicio de sesión. Inténtalo otra vez.", 400)
            code = query.get("code", [""])[0]
            if not code:
                return self.send_error_json("Discord no autorizó el acceso.", 400)
            try:
                credentials = base64.b64encode(f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
                tokens = web_server.discord_request(
                    "/oauth2/token",
                    form={"grant_type": "authorization_code", "code": code, "redirect_uri": cfg["redirect_uri"]},
                    basic=credentials,
                )
                user = web_server.discord_request("/users/@me", token=tokens["access_token"])
            except (HTTPError, URLError, KeyError, ValueError, OSError) as error:
                print(f"Discord OAuth falló: {type(error).__name__}")
                return self.send_error_json("No se pudo completar el inicio de sesión. Revisa OAuth y la URL de retorno.", 502)

            now = time.time()
            sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            session = {
                "user": user,
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token", ""),
                "access_expires": now + int(tokens.get("expires_in", 3600)),
                "csrf": csrf,
                "expires": now + SESSION_MAX_AGE,
            }
            register_web_user(user["id"], user)
            with _LOCK, web_server.LOCK:
                web_server.SESSIONS[sid] = session
                saved = _load()
                saved[sid] = session
                _save(saved)
            self.send_response(302)
            self.send_header("Location", "/?login=ok")
            self.send_header("Set-Cookie", self.cookie_header("vantarmor_session", sid, SESSION_MAX_AGE))
            self.send_header("Set-Cookie", self.cookie_header("vantarmor_oauth_state", "", 0))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/auth/logout":
            sid = self.get_cookie("vantarmor_session")
            with _LOCK, web_server.LOCK:
                web_server.SESSIONS.pop(sid, None)
                saved = _load()
                saved.pop(sid, None)
                _save(saved)
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", self.cookie_header("vantarmor_session", "", 0))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        return old_get(self)

    handler_class.get_session = get_session
    handler_class.do_GET = do_get


__all__ = ["install_persistent_sessions"]
