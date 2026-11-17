"""Ensure the authenticated profile API includes a usable Discord avatar URL."""
from urllib.parse import urlparse


def install_profile_api(handler_class):
    previous_get = handler_class.do_GET

    def do_get(self):
        if urlparse(self.path).path == "/api/me":
            session = self.get_session()
            if not session:
                return self.send_json({"authenticated": False}, 401)
            user = session["user"]
            user_id = str(user.get("id", ""))
            avatar_hash = user.get("avatar")
            avatar_url = (
                f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size=256"
                if avatar_hash
                else f"https://cdn.discordapp.com/embed/avatars/{int(user_id or 0) % 6}.png"
            )
            name = user.get("global_name") or user.get("username") or "Usuario de Discord"
            return self.send_json({
                "authenticated": True,
                "is_admin": self.require_admin(session),
                "csrf": session["csrf"],
                "user": {
                    "id": user_id,
                    "name": name,
                    "username": user.get("username", ""),
                    "avatar": avatar_hash,
                    "avatar_url": avatar_url,
                },
            })
        return previous_get(self)

    handler_class.do_GET = do_get
