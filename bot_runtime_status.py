"""Expose live bot status metrics through the public website stats API."""
import re
import threading
from urllib.parse import urlparse

from premium_store import public_stats

_LOCK = threading.RLock()
_STATUS = {"online": False, "servers": 0, "slash_commands": 0}
_MARKER = "# VANTARMOR_LIVE_STATUS_HOOKS_V1"


def set_bot_status(online, servers=0, slash_commands=0):
    with _LOCK:
        _STATUS.update(
            online=bool(online),
            servers=max(0, int(servers)),
            slash_commands=max(0, int(slash_commands)),
        )


def install_status_api(handler_class):
    original_do_get = handler_class.do_GET

    def do_get(self):
        if urlparse(self.path).path != "/api/stats":
            return original_do_get(self)
        stats = public_stats()
        with _LOCK:
            status = dict(_STATUS)
        stats.update(
            bot_online=status["online"],
            servers=status["servers"],
            slash_commands=status["slash_commands"],
            security_features=[
                "Anti-Raid y alertas de seguridad",
                "Anti-Nuke con modo pánico manual",
                "Anti-Bot y lista autorizada",
                "Filtro de cuentas nuevas",
                "Moderación y bloqueo de canales",
                "Tickets, registros y copias de seguridad",
            ],
        )
        return self.send_json(stats)

    handler_class.do_GET = do_get


def install_status_hooks(app_file):
    """Keep the website's bot-online metrics synchronized with Discord events."""
    source = app_file.read_text(encoding="utf-8")
    if _MARKER in source:
        return
    import_anchor = "from discord import app_commands\n"
    if import_anchor not in source:
        raise RuntimeError("No encontré el bloque de imports de app.py para el estado web.")
    source = source.replace(import_anchor, import_anchor + "import bot_runtime_status\n", 1)

    ready_anchor = '    print(f"Conectado como {client.user}")\n'
    if ready_anchor not in source:
        raise RuntimeError("No encontré on_ready para conectar las estadísticas del bot.")
    source = source.replace(
        ready_anchor,
        ready_anchor + "    bot_runtime_status.set_bot_status(True, len(client.guilds), len(tree.get_commands()))\n",
        1,
    )

    run_anchor = "client.run(TOKEN)\n"
    if run_anchor not in source:
        raise RuntimeError("No encontré client.run para conectar el estado de desconexión.")
    source = source.replace(
        run_anchor,
        "@client.event\n"
        "async def on_disconnect():\n"
        "    bot_runtime_status.set_bot_status(False, len(client.guilds), len(tree.get_commands()))\n\n\n"
        "@client.event\n"
        "async def on_resumed():\n"
        "    bot_runtime_status.set_bot_status(True, len(client.guilds), len(tree.get_commands()))\n\n\n"
        + _MARKER + "\n"
        + run_anchor,
        1,
    )
    app_file.write_text(source, encoding="utf-8")


__all__ = ["install_status_api", "install_status_hooks", "set_bot_status"]
