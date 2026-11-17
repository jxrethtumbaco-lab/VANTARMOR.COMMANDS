"""Make the website show counts and status for all registered commands."""
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

import guild_profile_settings
import web_server

_STATUS_LOCK = threading.RLock()
_STATUS = {"online": False, "servers": 0, "slash_commands": 0, "prefix_commands": 9}
_STATS_FEATURES = [
    "Anti-Raid y alertas de seguridad",
    "Anti-Nuke con modo pánico manual",
    "Anti-Bot y lista autorizada",
    "Filtro de cuentas nuevas",
    "Moderación y bloqueo de canales",
    "Tickets, registros y copias de seguridad",
]


def _command_leaf_names(commands, prefix=""):
    names = set()
    for command in commands:
        name = f"{prefix} {command.name}".strip()
        children = getattr(command, "commands", None)
        if children:
            names.update(_command_leaf_names(children, name))
        else:
            names.add(name)
    return names


def count_commands(tree, guild=None):
    commands = list(tree.get_commands())
    if guild is not None:
        commands.extend(tree.get_commands(guild=guild))
    return len(_command_leaf_names(commands))


def set_bot_status(online, guild_count=0, command_count=0):
    with _STATUS_LOCK:
        _STATUS.update(online=bool(online), servers=max(0, int(guild_count)), slash_commands=max(0, int(command_count)))


def _bot_present_guilds(guilds):
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ValueError("El bot no está configurado en este servicio.")
    present = []
    for guild in guilds:
        guild_id = str(guild.get("id", ""))
        if not guild_id.isdecimal():
            continue
        try:
            guild_profile_settings._discord_json(f"/guilds/{guild_id}", token=token)
            present.append(guild)
        except HTTPError as error:
            if error.code not in (403, 404):
                raise
    return present


def _manageable_guilds(session):
    guilds = web_server.discord_request("/users/@me/guilds", token=session["access_token"])
    return [guild for guild in guilds if guild.get("owner") or int(guild.get("permissions", "0")) & (0x8 | 0x20)]


def install_website_api(handler_class):
    previous_get = handler_class.do_GET

    def do_get(self):
        path = urlparse(self.path).path
        if path in ("/api/guilds", "/api/settings/guilds"):
            session = self.get_session()
            if not session:
                return self.send_json({"error": "inicia_sesion"}, 401)
            try:
                manageable = _manageable_guilds(session)
                if path == "/api/settings/guilds":
                    guilds = _bot_present_guilds(manageable)
                    return self.send_json({"guilds": [{"id": g["id"], "name": g["name"]} for g in guilds]})
                installed = {g["id"] for g in _bot_present_guilds(manageable)}
                return self.send_json({"guilds": [{"id": g["id"], "name": g["name"], "bot_installed": g["id"] in installed} for g in manageable]})
            except (HTTPError, URLError, OSError, ValueError, TypeError):
                return self.send_error_json("No se pudieron cargar tus servidores de Discord.", 502)
        if path == "/api/stats":
            from premium_store import public_stats
            stats = public_stats()
            with _STATUS_LOCK:
                status = dict(_STATUS)
            stats.update(bot_online=status["online"], servers=status["servers"], slash_commands=status["slash_commands"], prefix_commands=status["prefix_commands"], total_commands=status["slash_commands"] + status["prefix_commands"], security_features=_STATS_FEATURES)
            return self.send_json(stats)
        return previous_get(self)

    handler_class.do_GET = do_get


def install_bot_status_hooks(app_file):
    source = app_file.read_text(encoding="utf-8")
    import_anchor = "from discord import app_commands\n"
    if "import website_runtime_features\n" not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el bloque de imports de app.py para el estado web.")
        source = source.replace(import_anchor, import_anchor + "import website_runtime_features\n", 1)
    ready_anchor = '    print(f"Conectado como {client.user}")\n'
    ready_status = "    website_runtime_features.set_bot_status(True, len(client.guilds), website_runtime_features.count_commands(tree, GUILD))\n"
    if ready_anchor not in source:
        raise RuntimeError("No encontré on_ready para actualizar el estado de la web.")
    if ready_status not in source:
        source = source.replace(ready_anchor, ready_anchor + ready_status, 1)
    sync_line = '        commands = await tree.sync(guild=GUILD)\n        print(f"Comandos sincronizados: {len(commands)}")\n'
    sync_block = '        guild_commands = await tree.sync(guild=GUILD)\n        global_commands = await tree.sync()\n        command_count = website_runtime_features.count_commands(tree, GUILD)\n        website_runtime_features.set_bot_status(True, len(client.guilds), command_count)\n        print(f"Comandos sincronizados: {command_count} ({len(guild_commands)} de servidor, {len(global_commands)} globales)")\n'
    if sync_line in source:
        source = source.replace(sync_line, sync_block, 1)
    elif "global_commands = await tree.sync()" not in source:
        raise RuntimeError("No encontré la sincronización de comandos de app.py.")
    run_anchor = "client.run(TOKEN)\n"
    if run_anchor not in source:
        raise RuntimeError("No encontré client.run para conectar el estado web.")
    marker = "# VANTARMOR_WEBSITE_STATUS_HOOKS_V2"
    if marker not in source:
        hooks = "@client.event\nasync def on_disconnect():\n    website_runtime_features.set_bot_status(False, len(client.guilds), website_runtime_features.count_commands(tree, GUILD))\n\n\n@client.event\nasync def on_resumed():\n    website_runtime_features.set_bot_status(True, len(client.guilds), website_runtime_features.count_commands(tree, GUILD))\n\n\n" + marker + "\n"
        source = source.replace(run_anchor, hooks + run_anchor, 1)
    app_file.write_text(source, encoding="utf-8")


__all__ = ["count_commands", "install_bot_status_hooks", "install_website_api", "set_bot_status"]
