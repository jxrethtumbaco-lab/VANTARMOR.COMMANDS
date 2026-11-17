"""Idempotently register abuse controls and dispatch Anti-Spam in app.py."""
from pathlib import Path


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    import_anchor = "from discord import app_commands\n"
    import_line = "from abuse_protection import on_member_message, register_abuse_protection\n"
    tree_anchor = "tree = app_commands.CommandTree(client)\n"
    register_line = "register_abuse_protection(tree, client, GUILD_ID)\n"
    event_anchor = "@client.event\nasync def on_message(message):\n"
    guard = "    if message.author.bot or message.guild is None:\n        return\n"
    dispatch = "    await on_member_message(message)\n"

    if import_line not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el import app_commands para instalar protecciones.")
        source = source.replace(import_anchor, import_anchor + import_line, 1)
    if register_line not in source:
        if tree_anchor not in source:
            raise RuntimeError("No encontré el árbol de comandos para instalar protecciones.")
        source = source.replace(tree_anchor, tree_anchor + register_line, 1)
    if dispatch not in source:
        if event_anchor not in source or guard not in source:
            raise RuntimeError("No encontré on_message para conectar Anti-Spam.")
        source = source.replace(event_anchor + guard, event_anchor + guard + dispatch, 1)
    app_file.write_text(source, encoding="utf-8")
