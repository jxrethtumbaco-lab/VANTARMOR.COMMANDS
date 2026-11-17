from pathlib import Path

IMPORT_LINE = "from premium_security_system import register_security_commands\n"
REGISTER_LINE = "register_security_commands(tree, client)\n"

FREE_SECURITY_GUARD = (
    '    if interaction.command and interaction.command.name not in {"lockdown", "filtro-cuentas"} '
    'and not is_premium_user(interaction.user.id):\n'
)
OLD_PREMIUM_GUARD = '    if not is_premium_user(interaction.user.id):\n'


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    import_anchor = "from discord import app_commands\n"
    if IMPORT_LINE not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el punto de importación de app_commands en app.py.")
        source = source.replace(import_anchor, import_anchor + IMPORT_LINE, 1)
    tree_anchor = "tree = app_commands.CommandTree(client)\n"
    if REGISTER_LINE not in source:
        if tree_anchor not in source:
            raise RuntimeError("No encontré la creación del árbol de comandos en app.py.")
        source = source.replace(tree_anchor, tree_anchor + REGISTER_LINE, 1)
    app_file.write_text(source, encoding="utf-8")

    # Patch legacy source if present. Accept the newer equivalent guard too,
    # rather than crashing when the source has already been updated.
    security_file = app_file.with_name("premium_security_system.py")
    security_source = security_file.read_text(encoding="utf-8")
    if OLD_PREMIUM_GUARD in security_source:
        security_source = security_source.replace(OLD_PREMIUM_GUARD, FREE_SECURITY_GUARD, 1)
        security_file.write_text(security_source, encoding="utf-8")
        return

    helper_start = security_source.find("async def _require_premium_admin(")
    helper_end = security_source.find("\ndef _get_audit_channel", helper_start)
    helper = security_source[helper_start:helper_end] if helper_start >= 0 and helper_end > helper_start else ""
    if "is_premium_user(interaction.user.id)" not in helper:
        raise RuntimeError("No encontré una validación Premium segura en _require_premium_admin.")


__all__ = ["patch_app_file"]
