"""Lightweight prefix roleplay commands restored alongside app.py's existing commands."""
import random

import discord

REACTIONS = {
    "?kiss": ("💋", "le da un beso de roleplay a"),
    "?slap": ("👋", "le da una bofetada de roleplay a"),
    "?hug": ("🤗", "abraza a"),
    "?spank": ("😄", "le da una palmadita amistosa a"),
    "?kill": ("⚔️", "derrota en una escena ficticia a"),
}


class ReactionReplyView(discord.ui.View):
    def __init__(self, initiator, recipient, command):
        super().__init__(timeout=300)
        self.initiator = initiator
        self.recipient = recipient
        self.command = command
        self.finished = False
        if command == "?kiss":
            self._add("💋 Aceptar", discord.ButtonStyle.success, "accept")
            self._add("Rechazar", discord.ButtonStyle.secondary, "reject")
        elif command == "?kill":
            self._add("💚 Volver al combate", discord.ButtonStyle.success, "return")
        else:
            self._add("↩️ Devolver", discord.ButtonStyle.secondary, "return")

    def _add(self, label, style, outcome):
        button = discord.ui.Button(label=label, style=style)

        async def callback(interaction):
            if self.finished:
                await interaction.response.send_message("Esta interacción ya terminó.", ephemeral=True)
                return
            if interaction.user.id != self.recipient.id:
                await interaction.response.send_message("Este botón es para la persona mencionada.", ephemeral=True)
                return
            self.finished = True
            for child in self.children:
                child.disabled = True
            if outcome == "reject":
                text = f"🙂 {self.recipient.mention} rechazó el beso de roleplay de {self.initiator.mention}."
            elif self.command == "?kill":
                text = f"💚 {self.recipient.mention} volvió al combate: ¡solo era roleplay ficticio!"
            elif self.command == "?kiss":
                text = f"💋 {self.recipient.mention} correspondió el beso de roleplay a {self.initiator.mention}."
            else:
                text = f"↩️ {self.recipient.mention} devolvió la interacción a {self.initiator.mention}."
            embed = discord.Embed(description=text, color=discord.Color.blurple())
            await interaction.response.edit_message(embed=embed, view=self, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))

        button.callback = callback
        self.add_item(button)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.recipient.id:
            await interaction.response.send_message("Este botón es para la persona mencionada.", ephemeral=True)
            return False
        return True


async def _target_from_message(message):
    if message.mentions:
        return message.mentions[0]
    if message.reference and message.reference.message_id:
        try:
            referenced = message.reference.resolved
            if referenced is None or not hasattr(referenced, "author"):
                referenced = await message.channel.fetch_message(message.reference.message_id)
            return getattr(referenced, "author", None)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    return None


async def handle_prefix_reaction(message):
    content = (message.content or "").strip()
    command = content.split(maxsplit=1)[0].casefold() if content else ""
    if command not in (*REACTIONS, "?banana"):
        return False

    if command == "?banana":
        target = await _target_from_message(message) or message.author
        size = random.randint(1, 30)
        embed = discord.Embed(description=f"🍌 La banana virtual de {target.mention} mide **{size} cm**. *(Broma ficticia.)*", color=discord.Color.blurple())
        await message.reply(embed=embed, mention_author=False, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        return True

    target = await _target_from_message(message)
    if target is None:
        await message.reply(f"Menciona a alguien o responde a su mensaje con `{command}`.", mention_author=False)
        return True
    if target.bot or target.id == message.author.id:
        await message.reply("Usa el comando con otra persona, no contigo mismo ni con un bot.", mention_author=False)
        return True

    emoji, action = REACTIONS[command]
    disclaimer = " *(Roleplay ficticio y no gráfico.)*" if command == "?kill" else ""
    embed = discord.Embed(description=f"{emoji} {message.author.mention} {action} {target.mention}.{disclaimer}", color=discord.Color.blurple())
    view = ReactionReplyView(message.author, target, command)
    await message.reply(embed=embed, view=view, mention_author=False, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
    return True
