from pathlib import Path
import re

MARKER = "# VANTARMOR_KILL_ROLEPLAY_BUTTONS_V2"

KILL_VIEW = r'''# VANTARMOR_KILL_ROLEPLAY_BUTTONS_V2
class KillRoleplayView(discord.ui.View):
    """Two fictional, non-graphic roleplay outcomes for the mentioned user."""
    def __init__(self, initiator, recipient):
        super().__init__(timeout=300)
        self.initiator = initiator
        self.recipient = recipient
        self.finished = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.recipient.id:
            await interaction.response.send_message("Solo la persona mencionada puede elegir una respuesta.", ephemeral=True)
            return False
        if self.finished:
            await interaction.response.send_message("Esta escena ya terminó.", ephemeral=True)
            return False
        return True

    async def finish(self, interaction, action):
        self.finished = True
        for item in self.children:
            item.disabled = True
        if action == "revenge":
            text = f"💀 {self.recipient.mention} volvió al combate para vengarse de {self.initiator.mention}. *(Roleplay ficticio.)*"
            image = await random_anime_gif("revenge")
        else:
            text = f"👻 {self.recipient.mention} volvió como fantasma para asustar a {self.initiator.mention}. *(Roleplay ficticio.)*"
            image = await random_anime_gif("scare")
        embed = discord.Embed(description=text, color=discord.Color.blurple())
        if image:
            embed.set_image(url=image)
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        await interaction.message.edit(view=self)

    @discord.ui.button(label="💀 Vengar", style=discord.ButtonStyle.danger)
    async def revenge(self, interaction, button):
        await self.finish(interaction, "revenge")

    @discord.ui.button(label="👻 Asustar", style=discord.ButtonStyle.secondary)
    async def scare(self, interaction, button):
        await self.finish(interaction, "scare")
'''

KILL_HANDLER = r'''    if command == "?kill":
        target = message.mentions[0] if message.mentions else None
        if target is None and message.reference and message.reference.message_id:
            try:
                referenced = message.reference.resolved
                if referenced is None or not hasattr(referenced, "author"):
                    referenced = await message.channel.fetch_message(message.reference.message_id)
                target = getattr(referenced, "author", None)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                target = None
        if target is None:
            await message.reply("Menciona a alguien o responde a su mensaje con `?kill` (roleplay ficticio).", mention_author=False)
            return True
        if target.bot or target.id == message.author.id:
            await message.reply("Elige a otra persona; este comando es solo roleplay.", mention_author=False)
            return True
        embed = discord.Embed(
            description=f"⚔️ {message.author.mention} derrota a {target.mention} en una pelea de anime y lo deja fuera de combate por un momento. *(Roleplay ficticio, sin daño real.)*",
            color=discord.Color.blurple(),
        )
        image = await random_anime_gif("kill")
        if image:
            embed.set_image(url=image)
        await message.reply(
            embed=embed,
            view=KillRoleplayView(message.author, target),
            mention_author=False,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        return True
'''


def _add_gif_action(source, dictionary_marker, before_marker, lines):
    if any(f'"{action}":' in source for action in ("revenge", "scare")):
        return source
    start = source.find(dictionary_marker)
    if start < 0:
        return source
    end = source.find(before_marker, start)
    if end < 0:
        return source
    return source[:end] + lines + source[end:]


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    handler = "async def handle_reaction_command(message, content):\n"
    if handler not in source:
        print("No encontré el manejador de comandos de reacción en app.py; omito el parche de roleplay.")
        return

    source = re.sub(
        r'(?ms)^class KillRoleplayView\(discord\.ui\.View\):\n.*?(?=^class |^async def handle_reaction_command)',
        "",
        source,
        count=1,
    )
    source = source.replace(handler, KILL_VIEW + "\n\n" + handler, 1)

    kill_pattern = r'(?ms)^    if command == "\?kill":\n.*?^        return True\n'
    source, found = re.subn(kill_pattern, KILL_HANDLER, source, count=1)
    if not found:
        insertion = '    if command not in ("?kiss", "?slap"):\n'
        if insertion not in source:
            print("No encontré un punto válido para instalar ?kill; omito el parche.")
            return
        source = source.replace(insertion, KILL_HANDLER + "\n" + insertion, 1)

    source = _add_gif_action(
        source,
        "REACTION_GIF_ENDPOINTS = {",
        "\n}",
        '    "revenge": ("https://nekos.best/api/v2/kick", "https://api.waifu.pics/sfw/kick"),\n'
        '    "scare": ("https://nekos.best/api/v2/scare", "https://api.waifu.pics/sfw/scare"),\n',
    )
    source = _add_gif_action(
        source,
        "REACTION_GIF_FALLBACKS = {",
        "\n}",
        '    "revenge": (),\n    "scare": (),\n',
    )
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
