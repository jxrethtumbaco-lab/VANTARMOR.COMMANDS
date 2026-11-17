from pathlib import Path
import re


def remove_backup_commands(app_file: Path) -> None:
    """Remove stale generated backup slash commands before reinserting one copy."""
    source = app_file.read_text(encoding="utf-8")
    source, _ = re.subn(
        r'(?ms)^@tree\.command\(name="seguridad-copia"[^\n]*\)\n.*?(?=^@tree\.command|\Z)',
        "",
        source,
    )
    app_file.write_text(source, encoding="utf-8")


__all__ = ["remove_backup_commands"]
