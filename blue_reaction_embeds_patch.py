from pathlib import Path

MARKER = "# VANTARMOR_MESSAGE_REACTIONS_V2"
EVENT_MARKER = "@client.event\nasync def on_message(message):\n"


def patch_app_file(app_file: Path) -> None:
    """Color reaction embeds blue; safely skip if their generator did not run."""
    source = app_file.read_text(encoding="utf-8")
    start = source.find(MARKER)
    if start < 0:
        # Do not stop Railway startup for an optional cosmetic transformation.
        print("No encontré el bloque de reacciones en app.py; omito el estilo azul.")
        return
    end = source.find(EVENT_MARKER, start)
    if end < 0:
        print("No encontré on_message después del bloque de reacciones; omito el estilo azul.")
        return

    block = source[start:end]
    block = block.replace("discord.Color.green()", "discord.Color.blurple()")
    block = block.replace("discord.Color.pink()", "discord.Color.blurple()")
    block = block.replace("discord.Color.orange()", "discord.Color.blurple()")
    app_file.write_text(source[:start] + block + source[end:], encoding="utf-8")


__all__ = ["patch_app_file"]
