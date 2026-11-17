"""Idempotently register anti-link and dispatch it from app.py's on_message."""
from pathlib import Path


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    import_anchor = "from discord import app_commands\n"
    import_line = "from anti_link_protection import on_message_link_filter, register_anti_link\n"
    tree_anchor = "tree = app_commands.CommandTree(client)\n"
    register_line = "register_anti_link(tree, client, GUILD_ID)\n"
    event_anchor = "@client.event\nasync def on_message(message):\n"
    event_guard = "    if message.author.bot or message.guild is None:\n        return\n"
    dispatch = "    await on_message_link_filter(message)\n"

    if import_line not in source:
        # Replace an older single-symbol import if this patch previously ran.
        old_import = "from anti_link_protection import register_anti_link\n"
        if old_import in source:
            source = source.replace(old_import, import_line, 1)
        elif import_anchor in source:
            source = source.replace(import_anchor, import_anchor + import_line, 1)
        else:
            raise RuntimeError("No encontré el import app_commands para instalar Anti-Link.")

    if register_line not in source:
        if tree_anchor not in source:
            raise RuntimeError("No encontré el árbol de comandos para instalar Anti-Link.")
        source = source.replace(tree_anchor, tree_anchor + register_line, 1)

    if dispatch not in source:
        if event_anchor not in source or event_guard not in source:
            raise RuntimeError("No encontré el on_message existente para conectar Anti-Link.")
        source = source.replace(event_anchor + event_guard, event_anchor + event_guard + dispatch, 1)

    app_file.write_text(source, encoding="utf-8")
