"""Add public config for website links without exposing OAuth secrets."""
import os
from urllib.parse import urlparse


def install_public_website_config(handler_class):
    previous_get = handler_class.do_GET

    def do_get(self):
        if urlparse(self.path).path == "/config.json":
            from web_server import oauth_config
            cfg = oauth_config()
            support_url = os.getenv("SUPPORT_SERVER_URL", "").strip()
            if support_url and not (urlparse(support_url).scheme == "https" and urlparse(support_url).netloc):
                support_url = ""
            return self.send_json({
                "auth_enabled": bool(all(cfg.values())),
                "bot_client_id": cfg["client_id"],
                "invite_url": os.getenv("BOT_INVITE_URL", "").strip(),
                "bot_permissions": os.getenv("BOT_PERMISSIONS", "0").strip(),
                "support_server_url": support_url,
            })
        return previous_get(self)

    handler_class.do_GET = do_get
