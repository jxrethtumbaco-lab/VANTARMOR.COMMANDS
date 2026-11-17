from pathlib import Path
import re

IMPORTS = "from giveaway_system import register_giveaway_commands, register_advanced_giveaway_commands, resume_giveaways\n"
REGISTER = "register_giveaway_commands(tree, client)\n"
ADVANCED_REGISTER = "register_advanced_giveaway_commands(tree, client)\n"
RESUME = "    await resume_giveaways(client)\n"


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")

    source = re.sub(
        r'(?ms)^@tree\.command\(name="sorteo"[^\n]*\)\n.*?(?=^@tree\.command|^@client\.event|\Z)',
        "",
        source,
    )

    import_anchor = "from discord import app_commands\n"
    if IMPORTS not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el import de app_commands para instalar /sorteo y /sorteo-avanzado.")
        source = source.replace(import_anchor, import_anchor + IMPORTS, 1)

    tree_anchor = "tree = app_commands.CommandTree(client)\n"
    if REGISTER not in source:
        if tree_anchor not in source:
            raise RuntimeError("No encontré la creación del árbol de comandos para instalar los sorteos.")
        source = source.replace(tree_anchor, tree_anchor + REGISTER, 1)
    if ADVANCED_REGISTER not in source:
        if tree_anchor not in source:
            raise RuntimeError("No encontré la creación del árbol de comandos para registrar /sorteo-avanzado.")
        source = source.replace(tree_anchor, tree_anchor + ADVANCED_REGISTER, 1)

    ready_anchor = '    print(f"Conectado como {client.user}")\n'
    if RESUME not in source:
        if ready_anchor not in source:
            raise RuntimeError("No encontré on_ready para restaurar los temporizadores de sorteos.")
        source = source.replace(ready_anchor, ready_anchor + RESUME, 1)

    if "register_giveaway_commands(tree, client)" not in source or "register_advanced_giveaway_commands(tree, client)" not in source or "await resume_giveaways(client)" not in source:
        raise RuntimeError("No se pudo instalar el comando y la restauración de sorteos.")
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
