"""Reliable cookie-race and user-info slash commands."""
import asyncio

import discord
from discord import app_commands


class CookieRaceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.winner_id = None
        self.lock = asyncio.Lock()
        self.message = None

    @discord.ui.button(label="🍪", style=discord.ButtonStyle.primary)
    async def tap_cookie(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.lock:
            if self.winner_id is not None:
                await interaction.response.send_message("La galleta ya tiene ganador.", ephemeral=True)
                return
            self.winner_id = interaction.user.id
            button.disabled = True
            embed = discord.Embed(
                title="🍪 ¡Tenemos ganador!",
                description=f"{interaction.user.mention} ha sido la primera persona en tocar la galleta. ¡Felicidades! 🎉",
                color=discord.Color.gold(),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=self,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass


def _userinfo_embed(member: discord.Member) -> discord.Embed:
    color = member.color if member.color.value else discord.Color.blurple()
    embed = discord.Embed(title=f"Información de {member.display_name}", color=color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Cuenta", value=(
        f"ID: `{member.id}`\n"
        f"Bot: {'Sí' if member.bot else 'No'}\n"
        f"Creada: <t:{int(member.created_at.timestamp())}:F>"
    ), inline=False)
    joined = f"<t:{int(member.joined_at.timestamp())}:F>" if member.joined_at else "Desconocido"
    embed.add_field(name="Servidor", value=f"Entró: {joined}\nApodo: {member.nick or 'Ninguno'}\nRol más alto: {member.top_role.mention}", inline=False)
    roles = [role.mention for role in reversed(member.roles) if not role.is_default()]
    role_text = ", ".join(roles) or "Ninguno"
    if len(role_text) > 1024:
        role_text = role_text[:1018] + "…"
    embed.add_field(name=f"Roles ({len(roles)})", value=role_text, inline=False)
    if member.timed_out_until:
        embed.add_field(name="Aislamiento", value=f"Hasta <t:{int(member.timed_out_until.timestamp())}:F>", inline=False)
    return embed


def register_cookie_game(tree):
    cookie_group = app_commands.Group(name="cookie", description="Juegos de tocar la galleta")

    @cookie_group.command(name="game", description="Sé el primero en tocar la galleta")
    async def cookie_game(interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("Este juego solo funciona en un servidor.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🍪 ¡Prepárate para la galleta!",
            description="La galleta aparecerá en **5**…",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for remaining in (4, 3, 2, 1, 0):
            await asyncio.sleep(1)
            embed.description = "🍪 **¡Tócala ahora!**" if remaining == 0 else f"La galleta aparecerá en **{remaining}**…"
            await message.edit(embed=embed)
        view = CookieRaceView()
        view.message = message
        await message.edit(view=view)

    tree.add_command(cookie_group)

    @tree.command(name="userinfo", description="Muestra información de un miembro")
    @app_commands.describe(usuario="Miembro cuya información quieres consultar (opcional)")
    async def userinfo(interaction: discord.Interaction, usuario: discord.Member = None):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return
        member = usuario or interaction.user
        if not isinstance(member, discord.Member):
            try:
                member = await interaction.guild.fetch_member(member.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                await interaction.response.send_message("No pude encontrar a ese miembro en este servidor.", ephemeral=True)
                return
        try:
            await interaction.response.send_message(embed=_userinfo_embed(member), allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            if not interaction.response.is_done():
                await interaction.response.send_message("No pude mostrar la información de ese miembro.", ephemeral=True)

    return cookie_group, userinfo


__all__ = ["register_cookie_game"]
