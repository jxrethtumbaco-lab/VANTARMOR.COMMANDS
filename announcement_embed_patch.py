from pathlib import Path
import re

PATCH_MARKER = "# VANTARMOR_ANNOUNCEMENT_EMBED_OPTION_V1"

REPLACEMENT = '''@tree.command(name="anuncio", description="Envía un anuncio", guild=GUILD)
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(mensaje="Texto del anuncio", embed="True lo envía en un marco embed; False lo envía como texto normal")
async def anuncio(interaction, mensaje: str, embed: bool):
    message = mensaje.strip()
    if not message or len(message) > 2000:
        await interaction.response.send_message("Escribe un anuncio de 1 a 2000 caracteres.", ephemeral=True)
        return
    if embed:
        announcement = discord.Embed(
            title="📢 ANUNCIO IMPORTANTE",
            description=message,
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=announcement, allowed_mentions=discord.AllowedMentions.none())
    else:
        await interaction.response.send_message(f"📢 {message}", allowed_mentions=discord.AllowedMentions.none())


'''


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    if PATCH_MARKER in source:
        return
    pattern = re.compile(
        r'(?ms)^@tree\.command\(name="anuncio"[^\n]*\)\n'
        r'.*?(?=^@client\.event\nasync def on_message\(message\):)'
    )
    if not pattern.search(source):
        raise RuntimeError("No encontré el comando /anuncio en app.py.")
    source = pattern.sub(REPLACEMENT, source, count=1)
    source = source.replace(
        REPLACEMENT,
        REPLACEMENT + PATCH_MARKER + "\n",
        1,
    )
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
