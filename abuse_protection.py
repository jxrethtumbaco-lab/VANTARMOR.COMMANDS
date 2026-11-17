"""Defensive anti-nuke alerts and configurable repeated-message cleanup."""
import asyncio
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

from premium_security_system import _guild_config, _require_premium_admin, _set_lockdown, _update_guild

WINDOW_SECONDS = 10
SPAM_HISTORY = defaultdict(deque)
NUKE_HISTORY = defaultdict(lambda: defaultdict(deque))


def _owner_dm_view(guild_id: int, actor_id: int, actor_label: str):
    return NukeActorActionView(guild_id, actor_id, actor_label)


class NukeActorActionView(discord.ui.View):
    """Owner/admin can explicitly decide whether to ban an audit-log actor."""
    def __init__(self, guild_id: int, actor_id: int, actor_label: str):
        super().__init__(timeout=86400)
        self.guild_id = guild_id
        self.actor_id = actor_id
        self.actor_label = actor_label
        self.resolved = False

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
            await interaction.response.send_message("Solo el propietario o un administrador puede decidir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Banear actor (confirmar)", style=discord.ButtonStyle.danger)
    async def ban_actor(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message("Servidor no disponible.", ephemeral=True)
            return
        moderator = guild.get_member(interaction.user.id)
        target = guild.get_member(self.actor_id)
        if target is None:
            self.resolved = True
            await interaction.response.edit_message(content=f"El actor {self.actor_label} ya no está en el servidor; no se aplicó ningún baneo.", view=self)
            return
        if target.id == guild.owner_id or target.id == interaction.user.id:
            await interaction.response.send_message("No puedes banear al propietario ni a ti mismo.", ephemeral=True)
            return
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.ban_members:
            await interaction.response.send_message("Al bot le falta Banear miembros.", ephemeral=True)
            return
        if target.top_role >= bot_member.top_role:
            await interaction.response.send_message("No puedo banear al actor: su rol está al mismo nivel o por encima del rol del bot.", ephemeral=True)
            return
        try:
            await guild.ban(target, reason=f"Anti-Nuke confirmado por {interaction.user} ({interaction.user.id})")
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(f"No se pudo completar el baneo ({type(exc).__name__}).", ephemeral=True)
            return
        self.resolved = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"Actor {self.actor_label} baneado tras confirmación de {interaction.user}.", view=self)
        await _audit(guild, "⛔ Baneo confirmado por Anti-Nuke", f"Actor: `{self.actor_id}`\nConfirmado por: {interaction.user} (`{interaction.user.id}`).", discord.Color.red())

    @discord.ui.button(label="No banear", style=discord.ButtonStyle.secondary)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.resolved = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Alerta revisada; no se baneó al actor.", view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def _audit(guild: discord.Guild, title: str, description: str, color=discord.Color.orange()):
    channel = discord.utils.get(guild.text_channels, name="auditoria-logs")
    if channel is None:
        return
    embed = discord.Embed(title=title, description=description[:3500], color=color, timestamp=datetime.now(timezone.utc))
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No se pudo escribir auditoria-logs ({guild.id}): {type(exc).__name__}")


async def _notify_owner(guild: discord.Guild, actor, action_label: str, count: int):
    owner = guild.get_member(guild.owner_id)
    if owner is None:
        try:
            owner = await guild.fetch_member(guild.owner_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            owner = None
    if owner is None:
        return
    actor_id = getattr(actor, "id", 0)
    actor_label = f"{actor} (`{actor_id}`)" if actor else f"ID {actor_id} (no identificado)"
    embed = discord.Embed(
        title="🚨 Alerta Anti-Nuke",
        description=(
            f"El usuario o bot {actor_label} intentó nukear tu servidor **{guild.name}**.\n"
            f"Detectamos **{count}** acciones de {action_label} en {WINDOW_SECONDS} segundos y activamos el modo de protección.\n\n"
            "El actor no se banea automáticamente porque el registro de auditoría puede atribuir acciones incorrectamente. Revisa y confirma el baneo si corresponde."
        ),
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    )
    try:
        await owner.send(embed=embed, view=_owner_dm_view(guild.id, actor_id, actor_label))
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No se pudo notificar al propietario de {guild.id}: {type(exc).__name__}")


async def _find_audit_executor(guild: discord.Guild, action, target_id: int):
    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.view_audit_log:
        return None
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=20)
        async for entry in guild.audit_logs(limit=12, action=action, after=cutoff):
            if getattr(entry.target, "id", None) == target_id:
                return entry.user
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No se pudo revisar auditoría de {guild.id}: {type(exc).__name__}")
    return None


async def _track_nuke(guild: discord.Guild, action, target_id: int, action_key: str, label: str, threshold: int):
    rules = _guild_config(guild.id).get("anti_nuke", {})
    if not rules.get("enabled", False):
        return
    actor = await _find_audit_executor(guild, action, target_id)
    if actor is None or actor.id == (guild.me.id if guild.me else 0):
        return
    key = (actor.id, action_key)
    history = NUKE_HISTORY[guild.id][key]
    now = time.monotonic()
    while history and now - history[0] > WINDOW_SECONDS:
        history.popleft()
    history.append(now)
    if len(history) < threshold:
        return
    count = len(history)
    history.clear()
    success, status = await _set_lockdown(guild, True, reason=f"Anti-Nuke: umbral de {label} detectado")
    await _audit(guild, "🚨 Anti-Nuke activado", f"Actor: {actor} (`{actor.id}`)\nAcción: {label}\nConteo: {count}\nProtección: {status}", discord.Color.red())
    await _notify_owner(guild, actor, label, count)


async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    if channel.guild:
        rules = _guild_config(channel.guild.id).get("anti_nuke", {})
        await _track_nuke(channel.guild, discord.AuditLogAction.channel_delete, channel.id, "channel_delete", "eliminación de canales", int(rules.get("channels", 3)))


async def on_guild_role_create(role: discord.Role):
    rules = _guild_config(role.guild.id).get("anti_nuke", {})
    await _track_nuke(role.guild, discord.AuditLogAction.role_create, role.id, "role_create", "creación de roles", int(rules.get("roles", 2)))


async def on_member_ban(guild: discord.Guild, user: discord.User):
    rules = _guild_config(guild.id).get("anti_nuke", {})
    await _track_nuke(guild, discord.AuditLogAction.ban, user.id, "ban", "baneos", int(rules.get("bans", 3)))


async def on_member_message(message: discord.Message):
    if message.guild is None or message.author.bot or not message.content:
        return
    settings = _guild_config(message.guild.id).get("anti_spam", {})
    if not settings.get("enabled"):
        return
    normalized = re.sub(r"\s+", " ", message.content).strip().casefold()
    if len(normalized) < 3:
        return
    key = (message.guild.id, message.channel.id, message.author.id, normalized)
    history = SPAM_HISTORY[key]
    now = time.monotonic()
    while history and now - history[0][0] > WINDOW_SECONDS:
        history.popleft()
    history.append((now, message))
    threshold = int(settings.get("threshold", 3))
    if len(history) < threshold:
        return
    victims = [entry[1] for entry in history]
    history.clear()
    deleted = 0
    for victim in victims:
        try:
            await victim.delete()
            deleted += 1
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            continue
    await _audit(message.guild, "🧹 Anti-Spam: mensajes repetidos eliminados", f"**Usuario:** {message.author} (`{message.author.id}`)\n**Canal:** {message.channel.mention}\n**Umbral:** {threshold}\n**Eliminados:** {deleted}", discord.Color.orange())


def register_abuse_protection(tree, client, guild_id: int):
    """Register thresholds and audit event callbacks; spam runs inside app's message handler."""
    if not getattr(client, "abuse_nuke_events_registered", False):
        client.event(on_guild_channel_delete)
        client.event(on_guild_role_create)
        client.event(on_member_ban)
        client.abuse_nuke_events_registered = True

    guild_obj = discord.Object(id=guild_id)
    if tree.get_command("anti-nuke", guild=guild_obj) is None:
        @tree.command(name="anti-nuke", description="Configura límites de detección Anti-Nuke", guild=guild_obj)
        @app_commands.describe(accion="true activa; false desactiva", canales="Canales eliminados (1-10)", bans="Baneos (1-10)", roles="Roles creados (1-3)")
        async def anti_nuke(interaction: discord.Interaction, accion: bool, canales: app_commands.Range[int, 1, 10], bans: app_commands.Range[int, 1, 10], roles: app_commands.Range[int, 1, 3]):
            if not await _require_premium_admin(interaction):
                return
            try:
                _update_guild(interaction.guild.id, lambda state: state.update(anti_nuke={"enabled": bool(accion), "channels": int(canales), "bans": int(bans), "roles": int(roles)}))
            except OSError:
                await interaction.response.send_message("No pude guardar la configuración Anti-Nuke.", ephemeral=True)
                return
            await interaction.response.send_message(f"✅ Anti-Nuke {'activado' if accion else 'desactivado'}. Umbrales por {WINDOW_SECONDS} s: canales {canales}, baneos {bans}, roles {roles}. Al alcanzar uno, activa modo de protección y notifica al dueño para revisar el posible baneo.", ephemeral=True)

    if tree.get_command("anti-spam", guild=guild_obj) is None:
        @tree.command(name="anti-spam", description="Configura la eliminación de mensajes repetidos", guild=guild_obj)
        @app_commands.describe(accion="true activa; false desactiva", spam="Mensajes idénticos antes de eliminarlos (1-10)")
        async def anti_spam(interaction: discord.Interaction, accion: bool, spam: app_commands.Range[int, 1, 10]):
            if not await _require_premium_admin(interaction):
                return
            try:
                _update_guild(interaction.guild.id, lambda state: state.update(anti_spam={"enabled": bool(accion), "threshold": int(spam)}))
            except OSError:
                await interaction.response.send_message("No pude guardar la configuración Anti-Spam.", ephemeral=True)
                return
            await interaction.response.send_message(f"✅ Anti-Spam {'activado' if accion else 'desactivado'}: se detectan {spam} mensajes idénticos en {WINDOW_SECONDS} segundos y se intenta borrar todo el grupo.", ephemeral=True)
