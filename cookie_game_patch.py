"""Install the cookie game and replace the old fragile /userinfo handler."""
from pathlib import Path
import re

IMPORT_LINE = "from cookie_game_system import register_cookie_game\n"
REGISTER_LINE = "register_cookie_game(tree)\n"


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    # Remove previous /cookie and /userinfo top-level command definitions;
    # their replacements are registered by cookie_game_system.
    source = re.sub(
        r'(?ms)^@tree\.command\(name="(?:cookie|userinfo)"[^\n]*\)\n.*?(?=^@tree\.command|^@client\.event|\Z)',
        "",
        source,
    )
    if IMPORT_LINE not in source:
        anchor = "from discord import app_commands\n"
        if anchor not in source:
            raise RuntimeError("No encontré el import app_commands para instalar cookie game/userinfo.")
        source = source.replace(anchor, anchor + IMPORT_LINE, 1)
    if REGISTER_LINE not in source:
        anchor = "tree = app_commands.CommandTree(client)\n"
        if anchor not in source:
            raise RuntimeError("No encontré el árbol de comandos para instalar cookie game/userinfo.")
        source = source.replace(anchor, anchor + REGISTER_LINE, 1)
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
