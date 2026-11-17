"""Frontend installer for a runtime-updated public statistics tab."""
from pathlib import Path


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    old = 'const tabSections = [...document.querySelectorAll("main > section[id]")];'
    new = 'const tabSections = () => [...document.querySelectorAll("main > section[id]")];'
    if old in source:
        source = source.replace(old, new, 1)
    source = source.replace("tabSections.find((section)", "tabSections().find((section)")
    source = source.replace("for (const section of tabSections)", "for (const section of tabSections())")
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
