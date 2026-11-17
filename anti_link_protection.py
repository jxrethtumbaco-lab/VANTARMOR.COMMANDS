"""Per-guild link filtering with owner DM alerts and guarded ban actions."""
import re
from datetime import datetime, timezone

import discord
from discord import app_commands

from premium_security_system import _guild_config, _require_premium_admin, _update_guild

LINK_PATTERN = re.compile(
    r"(?:https?://|www\.)[^\s<>]+"
    r"|(?:discord\.gg|discord(?:app)?\.com/invite)/[^\s<>]+"
    r"|\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}(?::\d+)?(?:/[^\s<>]*)?",
    re.IGNORECASE,
)


def _neutralize_links(text: str, limit: int = 450) -> str:
    text = LINK_PATTERN.sub("[enlace eliminado]", text or "")
    return text[:limit] or "(sin texto)"


async def _record(guild: discord.Guild, title: str, description: str, color=discord.Color.orange()):
    channel = discord.utils.get(guild.text_channels, name="auditoria-logs")
    if channel is None:
        return
    embed = discord.Embed(title=title, description=description[:3500], color=color, timestamp=datetime.now(timezone.utc))
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No se pudo escribir auditoria-logs del servidor {guild.id}: {type(exc).__name__}")


class LinkAlertView(discord.ui.View):
    def __init__(self, guild_id: int, member_id: int, message_url: str):
        super().__init__(timeout=86400)
        self.guild_id = guild_id
        self.member_id = member_id
        self.resolved = False
        self.add_item(discord.ui.Button(label="♿ Ir al servidor", style=discord.ButtonStyle.link, url=message_url))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.resolved:
            await interaction.response.send_message("Esta alerta ya fue atendida.", ephemeral=True)
            return False
        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message("El servidor ya no está disponible.", ephemeral=True)
            return False
        member = guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None
        if member is None or (member.id != guild.owner_id and not member.guild_permissions.administrator):
            await interaction.response.send_message("Solo el propietario o un administrador puede usar esta acción.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="❌ Banear usuario", style=discord.ButtonStyle.danger)
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message("El servidor no está disponible.", ephemeral=True)
            return
        moderator = guild.get_member(interaction.user.id)
        target = guild.get_member(self.member_id)
        if moderator is None or (moderator.id != guild.owner_id and not moderator.guild_permissions.administrator):
            await interaction.response.send_message("Solo el propietario o un administrador puede banear.", ephemeral=True)
            return
        if moderator.id != guild.owner_id and not moderator.guild_permissions.ban_members:
            await interaction.response.send_message("Necesitas el permiso Banear miembros.", ephemeral=True)
            return
        if target is None:
            self.resolved = True
            await interaction.response.edit_message(content="El usuario ya no está en el servidor; no se realizó ningún baneo.", view=self)
            return
        if target.id == guild.owner_id or target.id == moderator.id:
            await interaction.response.send_message("No puedes banear al propietario ni a ti mismo.", ephemeral=True)
            return
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.ban_members:
            await interaction.response.send_message("Al bot le falta el permiso Banear miembros.", ephemeral=True)
            return
        if target.top_role >= bot_member.top_role:
            await interaction.response.send_message("No puedo banearlo: su rol está al mismo nivel o por encima del rol del bot.", ephemeral=True)
            return
        try:
            await guild.ban(target, reason=f"Enlace detectado; baneo confirmado por {moderator} ({moderator.id})")
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(f"No se pudo banear al usuario ({type(exc).__name__}).", ephemeral=True)
            return
        self.resolved = True
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                item.disabled = True
        await interaction.response.edit_message(content=f"❌ {target} fue baneado por {moderator}.", view=self)
        await _record(guild, "⛔ Baneo tras alerta de enlace", f"**Usuario:** {target} (`{target.id}`)\n**Decisión de:** {moderator} (`{moderator.id}`).", discord.Color.red())

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.style != discord.ButtonStyle.link:
                item.disabled = True


async def on_message_link_filter(message: discord.Message):
    if message.guild is None or message.author.bot or not message.content:
        return
    state = _guild_config(message.guild.id)
    if not state.get("anti_link", {}).get("enabled", False) or not LINK_PATTERN.search(message.content):
        return

    safe_excerpt = _neutralize_links(message.content)
    deleted = True
    try:
        await message.delete()
    except (discord.Forbidden, discord.HTTPException) as exc:
        deleted = False
        print(f"No se pudo borrar el enlace en {message.guild.id}/{message.channel.id}: {type(exc).__name__}")

    jump_url = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
    embed = discord.Embed(
        title="🔗 Alerta de enlace",
        description=(
            f"En tu servidor **{message.guild.name}** se detectó un mensaje con enlace.\n\n"
            f"**Responsable:** {message.author} (`{message.author.id}`)\n"
            f"**Canal:** {message.channel.mention}\n"
            f"**Mensaje:** {safe_excerpt}\n"
            f"**Eliminado:** {'Sí' if deleted else 'No; revisa permisos del bot.'}"
        ),
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    owner = message.guild.get_member(message.guild.owner_id)
    if owner is None:
        try:
            owner = await message.guild.fetch_member(message.guild.owner_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            owner = None
    if owner is not None:
        try:
            await owner.send(embed=embed, view=LinkAlertView(message.guild.id, message.author.id, jump_url))
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"No se pudo enviar alerta Anti-Link al propietario de {message.guild.id}: {type(exc).__name__}")

    await _record(message.guild, "🔗 Enlace detectado", f"**Responsable:** {message.author} (`{message.author.id}`)\n**Canal:** {message.channel.mention}\n**Mensaje:** {safe_excerpt}\n**Eliminado:** {'Sí' if deleted else 'No'}")


def register_anti_link(tree, client, guild_id: int):
    """Register the slash command only. Listener dispatch is inserted in app.py."""
    guild_obj = discord.Object(id=guild_id)
    if tree.get_command("anti-link", guild=guild_obj) is not None:
        return

    @tree.command(name="anti-link", description="Activa o desactiva la eliminación inmediata de enlaces", guild=guild_obj)
    @app_commands.describe(accion="true activa; false desactiva Anti-Link")
    async def anti_link(interaction: discord.Interaction, accion: bool):
        if not await _require_premium_admin(interaction):
            return
        try:
            _update_guild(interaction.guild.id, lambda state: state.update(anti_link={"enabled": bool(accion)}))
        except OSError:
            await interaction.response.send_message("No pude guardar la configuración. Inténtalo otra vez.", ephemeral=True)
            return
        status = "activado" if accion else "desactivado"
        await interaction.response.send_message(
            f"✅ Anti-Link {status}. {'Se borrarán inmediatamente los mensajes con enlaces y se notificará al propietario.' if accion else 'Los mensajes con enlaces ya no se filtrarán.'}",
            ephemeral=True,
        )


__all__ = ["register_anti_link", "on_message_link_filter"]
