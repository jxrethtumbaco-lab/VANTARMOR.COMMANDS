"""Idempotently route reaction prefix commands through the existing message event."""
from pathlib import Path


IMPORT_LINE = "from prefix_reactions import handle_prefix_reaction\n"
DISPATCH_LINE = "    if await handle_prefix_reaction(message):\n        return\n"


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    import_anchor = "from discord import app_commands\n"
    if IMPORT_LINE not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el punto de importación de app_commands en app.py para restaurar comandos de reacción.")
        source = source.replace(import_anchor, import_anchor + IMPORT_LINE, 1)

    event_anchor = "@client.event\nasync def on_message(message):\n"
    guard = "    if message.author.bot or message.guild is None:\n        return\n"
    if DISPATCH_LINE not in source:
        start = source.find(event_anchor)
        if start < 0:
            raise RuntimeError("No encontré on_message en app.py para conectar los comandos de prefijo.")
        guard_start = source.find(guard, start)
        if guard_start < 0:
            raise RuntimeError("No encontré la protección inicial de on_message en app.py.")
        insert_at = guard_start + len(guard)
        source = source[:insert_at] + DISPATCH_LINE + source[insert_at:]

    app_file.write_text(source, encoding="utf-8")
