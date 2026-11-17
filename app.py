import asyncio
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "1559455132821753856"))

if not TOKEN:
    raise RuntimeError("Falta la variable DISCORD_TOKEN en Railway.")

GUILD = discord.Object(id=GUILD_ID)
intents = discord.Intents.default()
intents.guild_messages = True
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
CONFIG_FILE = Path("bot_config.json")
CONFIG_DEFAULTS = {
    "ticket_role": {},
    "ticket_category": {},
    "ticket_log": {},
    "audit_log": {},
    "autorole": {},
    "blocked_words": {},
    "antispam": {},
    "antilink": {},
}
config = {key: {} for key in CONFIG_DEFAULTS}


def load_config():
    try:
        saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        for key in CONFIG_DEFAULTS:
            if isinstance(saved.get(key), dict):
                config[key] = saved[key]
    except (OSError, json.JSONDecodeError):
        pass


def save_config():
    try:
        CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"No pude guardar la configuración: {exc}")


load_config()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def duration_seconds(text: str) -> Optional[int]:
    value = normalize((text or "").strip())
    match = re.fullmatch(r"(\d+)\s*(m|min|mins|minuto|minutos|h|hr|hrs|hora|horas|d|dia|dias|mon|month|mes|meses|year|yr|ano|anos)", value)
    if not match:
        return None
    count = int(match.group(1))
    unit = match.group(2)
    if unit in ("m", "min", "mins", "minuto", "minutos"):
        return count * 60
    if unit in ("h", "hr", "hrs", "hora", "horas"):
        return count * 3600
    if unit in ("d", "dia", "dias"):
        return count * 86400
    if unit in ("mon", "month", "mes", "meses"):
        return count * 30 * 86400
    return count * 365 * 86400


def duration_label(seconds: int) -> str:
    if seconds % (365 * 86400) == 0:
        return f"{seconds // (365 * 86400)} año(s)"
    if seconds % (30 * 86400) == 0:
        return f"{seconds // (30 * 86400)} mes(es)"
    if seconds % 86400 == 0:
        return f"{seconds // 86400} día(s)"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} hora(s)"
    return f"{seconds // 60} minuto(s)"


def get_role(guild, setting):
    role_id = config[setting].get(str(guild.id))
    return guild.get_role(int(role_id)) if role_id else None


def get_channel(guild, setting):
    channel_id = config[setting].get(str(guild.id))
    return guild.get_channel(int(channel_id)) if channel_id else None


def is_admin_or_owner(member):
    return isinstance(member, discord.Member) and (
        member.id == member.guild.owner_id or member.guild_permissions.administrator
    )


async def audit(guild, title, description, color=discord.Color.orange()):
    channel = get_channel(guild, "audit_log")
    if not channel:
        return
    embed = discord.Embed(title=title, description=(description or "Sin detalles")[:4000], color=color, timestamp=datetime.now(timezone.utc))
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No pude escribir auditoria: {exc}")


async def ticket_log(guild, title, description, color=discord.Color.blurple()):
    channel = get_channel(guild, "ticket_log")
    if not channel:
        return
    embed = discord.Embed(title=title, description=(description or "Sin detalles")[:4000], color=color, timestamp=datetime.now(timezone.utc))
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No pude escribir tickets: {exc}")


async def timeout_member(guild, actor, target, seconds):
    if not isinstance(actor, discord.Member):
        return "Este comando solo se puede usar en un servidor."
    if not (is_admin_or_owner(actor) or actor.guild_permissions.manage_guild):
        return "Necesitas ser administrador o tener permiso de gestionar servidor."
    if seconds is None or seconds < 60:
        return "Duración no válida. Usa `12m`, `1h`, `1d`, `1mon` o `1year` (mínimo 1m)."
    if seconds > 28 * 86400:
        return "Discord limita el aislamiento a 28 días. Usa `28d` o menos."
    if target.bot or target.id in (guild.owner_id, actor.id):
        return "No puedes aislar a bots, al propietario ni a ti mismo."
    if target.top_role >= actor.top_role and not is_admin_or_owner(actor):
        return "No puedes aislar a alguien con un rol igual o superior al tuyo."
    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.moderate_members:
        return "Al bot le falta el permiso Moderar miembros."
    if target.top_role >= bot_member.top_role:
        return "El rol del miembro está por encima o al mismo nivel que el rol del bot."
    try:
        await target.timeout(datetime.now(timezone.utc) + timedelta(seconds=seconds), reason=f"Aislamiento aplicado por {actor}")
        return f"🔇 {target.mention} quedó aislado durante **{duration_label(seconds)}**."
    except discord.Forbidden:
        return "Discord rechazó el aislamiento. Revisa Moderar miembros y jerarquía de roles."
    except discord.HTTPException:
        return "No pude aplicar el aislamiento por un error de Discord."


async def moderate_member(guild, actor, target, action):
    permission = "ban_members" if action == "ban" else "kick_members"
    if not getattr(actor.guild_permissions, permission, False):
        return "No tienes permiso para hacer eso."
    bot_member = guild.me
    if bot_member is None or not getattr(bot_member.guild_permissions, permission, False):
        return "Al bot le falta el permiso necesario."
    if target.id in (guild.owner_id, actor.id):
        return "No puedes moderar al propietario ni a ti mismo."
    if actor.id != guild.owner_id and target.top_role >= actor.top_role:
        return "No puedes moderar a alguien con un rol igual o superior al tuyo."
    if target.top_role >= bot_member.top_role:
        return "El rol del miembro está por encima o al mismo nivel que el rol del bot."
    try:
        if action == "ban":
            await guild.ban(target, reason=f"Acción solicitada por {actor}")
            return f"🔨 {target.mention} fue baneado."
        await guild.kick(target, reason=f"Acción solicitada por {actor}")
        return f"👢 {target.mention} fue expulsado."
    except (discord.Forbidden, discord.HTTPException) as exc:
        return f"No pude completar la acción: {exc}"


async def change_channel_lock(channel, actor, lock):
    guild = channel.guild
    if not actor.guild_permissions.manage_channels:
        return "Necesitas el permiso Administrar canales."
    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_channels:
        return "Al bot le falta el permiso Administrar canales."
    if not isinstance(channel, discord.TextChannel):
        return "Este comando solo funciona en canales de texto."
    overwrite = channel.overwrites_for(guild.default_role)
    overwrite.send_messages = False if lock else None
    try:
        await channel.set_permissions(guild.default_role, overwrite=overwrite if not overwrite.is_empty() else None, reason=f"Canal {'bloqueado' if lock else 'desbloqueado'} por {actor}")
    except (discord.Forbidden, discord.HTTPException):
        return "No pude cambiar los permisos del canal. Revisa los permisos del bot."
    return f"🔒 {channel.mention} quedó bloqueado." if lock else f"🔓 {channel.mention} quedó desbloqueado."


async def avatar_embed(user):
    try:
        full_user = await client.fetch_user(user.id)
    except discord.HTTPException:
        full_user = user
    embed = discord.Embed(title=f"Avatar y banner de {user}", color=discord.Color.blurple())
    embed.set_thumbnail(url=user.display_avatar.url)
    if getattr(full_user, "banner", None):
        embed.set_image(url=full_user.banner.url)
    else:
        embed.description = "Este usuario no tiene un banner configurado."
    return embed


def server_info_embed(guild):
    text_count = sum(isinstance(ch, discord.TextChannel) for ch in guild.channels)
    voice_count = sum(isinstance(ch, (discord.VoiceChannel, discord.StageChannel)) for ch in guild.channels)
    category_count = sum(isinstance(ch, discord.CategoryChannel) for ch in guild.channels)
    embed = discord.Embed(title=f"Información de {guild.name}", color=discord.Color.blurple())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Servidor", value=f"ID: `{guild.id}`\nPropietario: <@{guild.owner_id}>\nCreado: <t:{int(guild.created_at.timestamp())}:F>", inline=False)
    embed.add_field(name="Miembros", value=f"Total: **{guild.member_count or 0}**\nBots: **{sum(member.bot for member in guild.members)}**", inline=True)
    embed.add_field(name="Canales", value=f"Texto: **{text_count}**\nVoz/Escenario: **{voice_count}**\nCategorías: **{category_count}**", inline=True)
    embed.add_field(name="Roles", value=f"**{len(guild.roles)}**", inline=True)
    embed.add_field(name="Boosts", value=f"Nivel: **{guild.premium_tier}**\nBoosts: **{guild.premium_subscription_count or 0}**", inline=True)
    embed.add_field(name="Verificación", value=f"**{guild.verification_level}**", inline=True)
    return embed


def user_info_embed(member):
    roles = [role.mention for role in reversed(member.roles) if not role.is_default()]
    embed = discord.Embed(title=f"Información de {member}", color=member.color if member.color.value else discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Cuenta", value=f"ID: `{member.id}`\nBot: **{'Sí' if member.bot else 'No'}**\nCreada: <t:{int(member.created_at.timestamp())}:F>", inline=False)
    embed.add_field(name="Servidor", value=f"Entró: {f'<t:{int(member.joined_at.timestamp())}:F>' if member.joined_at else 'Desconocido'}\nApodo: **{member.nick or 'Ninguno'}**\nRol más alto: {member.top_role.mention}", inline=False)
    embed.add_field(name=f"Roles ({len(roles)})", value=", ".join(roles)[:1024] or "Ninguno", inline=False)
    if member.timed_out_until:
        embed.add_field(name="Aislamiento", value=f"Hasta <t:{int(member.timed_out_until.timestamp())}:F>", inline=False)
    return embed


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Abrir ticket", style=discord.ButtonStyle.primary, custom_id="support_ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Este panel solo funciona en un servidor.", ephemeral=True)
            return
        category = guild.get_channel(int(config["ticket_category"].get(str(guild.id), 0)))
        support_role = get_role(guild, "ticket_role")
        if not isinstance(category, discord.CategoryChannel) or support_role is None:
            await interaction.response.send_message("El sistema de tickets aún no está configurado.", ephemeral=True)
            return
        for existing in category.text_channels:
            if existing.topic and f"ticket_owner:{interaction.user.id}" in existing.topic:
                await interaction.response.send_message(f"Ya tienes un ticket abierto: {existing.mention}", ephemeral=True)
                return
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await interaction.response.send_message("Al bot le falta Administrar canales.", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True),
            bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True),
        }
        try:
            channel = await guild.create_text_channel(name=f"ticket-{interaction.user.name}"[:90], category=category, overwrites=overwrites, topic=f"ticket_owner:{interaction.user.id}", reason=f"Ticket creado por {interaction.user}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(f"No pude crear el ticket: {exc}", ephemeral=True)
            return
        await interaction.response.send_message(f"Ticket creado: {channel.mention}", ephemeral=True)
        await channel.send(f"{interaction.user.mention} {support_role.mention}, cuéntanos cómo podemos ayudarte.", view=TicketCloseView(), allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False))
        await ticket_log(guild, "Ticket abierto", f"**Abierto por:** {interaction.user.mention}\n**Canal:** {channel.mention}", discord.Color.green())


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Cerrar ticket", style=discord.ButtonStyle.danger, custom_id="support_ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel, guild = interaction.channel, interaction.guild
        if guild is None or not isinstance(channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("No pude identificar este ticket.", ephemeral=True)
            return
        match = re.search(r"ticket_owner:(\d+)", channel.topic or "")
        owner_id = int(match.group(1)) if match else None
        if interaction.user.id != owner_id and not (interaction.user.guild_permissions.manage_guild or is_admin_or_owner(interaction.user)):
            await interaction.response.send_message("Solo quien abrió el ticket o un administrador puede cerrarlo.", ephemeral=True)
            return
        await interaction.response.send_message("Cerrando el ticket…", ephemeral=True)
        await ticket_log(guild, "Ticket cerrado", f"**Cerrado por:** {interaction.user.mention}\n**Abierto por:** <@{owner_id}>\n**Canal:** `#{channel.name}` (`{channel.id}`)", discord.Color.red())
        try:
            await channel.delete(reason=f"Ticket cerrado por {interaction.user}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.followup.send(f"No pude eliminar el canal: {exc}", ephemeral=True)


@tree.command(name="ping", description="Comprueba si el bot responde", guild=GUILD)
async def ping(interaction):
    await interaction.response.send_message("¡Pong! ✅")


@tree.command(name="ayuda", description="Muestra comandos disponibles", guild=GUILD)
async def ayuda(interaction):
    await interaction.response.send_message(
        "Comandos básicos: `/ping`, `/serverinfo`, `/userinfo`, `/avatar`, `/ban`, `/kick`, `/timeout`, `/lock`, `/unlock`, `/ticket-panel`.",
        ephemeral=True,
    )


@tree.command(name="serverinfo", description="Muestra información del servidor", guild=GUILD)
async def serverinfo(interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Úsalo en un servidor.", ephemeral=True)
        return
    await interaction.response.send_message(embed=server_info_embed(interaction.guild))


@tree.command(name="userinfo", description="Muestra información de un miembro", guild=GUILD)
@app_commands.describe(usuario="Usuario cuya información quieres consultar")
async def userinfo(interaction, usuario: discord.Member):
    await interaction.response.send_message(embed=user_info_embed(usuario))


@tree.command(name="avatar", description="Muestra avatar y banner de un miembro", guild=GUILD)
@app_commands.describe(usuario="Miembro cuyo avatar quieres ver")
async def avatar_command(interaction, usuario: discord.Member):
    await interaction.response.send_message(embed=await avatar_embed(usuario))


@tree.command(name="ticket-rol", description="Configura el rol de soporte de tickets", guild=GUILD)
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(rol="Rol del equipo que atenderá tickets")
async def ticket_role_command(interaction: discord.Interaction, rol: discord.Role):
    if interaction.guild is None or not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Necesitas Administrar servidor.", ephemeral=True)
        return
    config["ticket_role"][str(interaction.guild.id)] = rol.id
    save_config()
    await interaction.response.send_message(f"✅ El rol de soporte ahora es {rol.mention}.", ephemeral=True)


@tree.command(name="ticket-categoria", description="Selecciona la categoría donde se crearán los tickets", guild=GUILD)
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(categoria="Categoría para los tickets")
async def ticket_category_command(interaction: discord.Interaction, categoria: discord.CategoryChannel):
    if interaction.guild is None or not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Necesitas Administrar servidor.", ephemeral=True)
        return
    config["ticket_category"][str(interaction.guild.id)] = categoria.id
    save_config()
    await interaction.response.send_message(f"✅ Los tickets se crearán en **{categoria.name}**.", ephemeral=True)


@tree.command(name="ticket-panel", description="Publica un panel para abrir tickets", guild=GUILD)
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(canal="Canal donde se enviará el panel", descripcion="Descripción opcional")
async def ticket_panel_command(interaction: discord.Interaction, canal: discord.TextChannel, descripcion: Optional[str] = None):
    if interaction.guild is None or not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Necesitas Administrar servidor.", ephemeral=True)
        return
    category_id = config["ticket_category"].get(str(interaction.guild.id))
    category = interaction.guild.get_channel(int(category_id)) if category_id else None
    if get_role(interaction.guild, "ticket_role") is None or not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message("Primero configura `/ticket-rol` y `/ticket-categoria`.", ephemeral=True)
        return
    embed = discord.Embed(title="🎫 Soporte", description=(descripcion or "Pulsa el botón para crear un ticket privado con el equipo de soporte.")[:4000], color=discord.Color.blurple())
    try:
        await canal.send(embed=embed, view=TicketPanelView())
    except (discord.Forbidden, discord.HTTPException) as exc:
        await interaction.response.send_message(f"No pude enviar el panel: {exc}", ephemeral=True)
        return
    await interaction.response.send_message(f"✅ Panel de tickets enviado a {canal.mention}.", ephemeral=True)


@tree.command(name="setlog", description="Crea/configura el canal de auditoría", guild=GUILD)
@app_commands.default_permissions(manage_guild=True)
async def setlog(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Necesitas Administrar servidor.", ephemeral=True)
        return
    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_channels:
        await interaction.response.send_message("Al bot le falta Administrar canales.", ephemeral=True)
        return
    channel = discord.utils.get(guild.text_channels, name="auditoria-logs")
    if channel is None:
        try:
            channel = await guild.create_text_channel("auditoria-logs")
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(f"No pude crear auditoria-logs: {exc}", ephemeral=True)
            return
    config["audit_log"][str(guild.id)] = channel.id
    save_config()
    await interaction.response.send_message(f"✅ Auditoría configurada en {channel.mention}.", ephemeral=True)


@tree.command(name="ban", description="Banea a un miembro", guild=GUILD)
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(usuario="Miembro que quieres banear")
async def ban_command(interaction, usuario: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("Úsalo dentro de un servidor.", ephemeral=True)
        return
    await interaction.response.send_message(await moderate_member(interaction.guild, interaction.user, usuario, "ban"), allowed_mentions=discord.AllowedMentions.none())


@tree.command(name="kick", description="Expulsa a un miembro", guild=GUILD)
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(usuario="Miembro que quieres expulsar")
async def kick_command(interaction, usuario: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("Úsalo dentro de un servidor.", ephemeral=True)
        return
    await interaction.response.send_message(await moderate_member(interaction.guild, interaction.user, usuario, "kick"), allowed_mentions=discord.AllowedMentions.none())


@tree.command(name="timeout", description="Aísla temporalmente a un miembro", guild=GUILD)
@app_commands.describe(usuario="Miembro que se aislará", duracion="Duración como 12m, 1h, 1d o 1mon")
async def timeout_command(interaction, usuario: discord.Member, duracion: str):
    seconds = duration_seconds(duracion)
    result = await timeout_member(interaction.guild, interaction.user, usuario, seconds)
    await interaction.response.send_message(result, allowed_mentions=discord.AllowedMentions.none())


@tree.command(name="lock", description="Bloquea el canal actual", guild=GUILD)
@app_commands.default_permissions(manage_channels=True)
async def lock_command(interaction):
    if interaction.guild and interaction.channel and isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(await change_channel_lock(interaction.channel, interaction.user, True))
    else:
        await interaction.response.send_message("Úsalo en un canal del servidor.", ephemeral=True)


@tree.command(name="unlock", description="Desbloquea el canal actual", guild=GUILD)
@app_commands.default_permissions(manage_channels=True)
async def unlock_command(interaction):
    if interaction.guild and interaction.channel and isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(await change_channel_lock(interaction.channel, interaction.user, False))
    else:
        await interaction.response.send_message("Úsalo en un canal del servidor.", ephemeral=True)


@tree.command(name="purge", description="Elimina de 1 a 100 mensajes", guild=GUILD)
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(cantidad="Cantidad de mensajes, entre 1 y 100")
async def purge_command(interaction, cantidad: app_commands.Range[int, 1, 100]):
    if interaction.guild is None or interaction.channel is None or not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("Necesitas Administrar mensajes.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = len(await interaction.channel.purge(limit=cantidad, bulk=False))
    await interaction.followup.send(f"Eliminé {deleted} mensaje(s).", ephemeral=True)


@client.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return
    content = message.content.strip()
    if content.casefold() == "?ping":
        await message.channel.send("¡Pong! ✅")
        return
    if content.casefold() == "?servidor":
        await message.channel.send(embed=server_info_embed(message.guild))
        return
    if content.casefold() == "?info":
        reference = message.reference
        if not reference or not reference.message_id:
            await message.channel.send("Responde al mensaje de un miembro con `?info`.")
            return
        try:
            replied = reference.resolved or await message.channel.fetch_message(reference.message_id)
            member = message.guild.get_member(replied.author.id) or await message.guild.fetch_member(replied.author.id)
            await message.channel.send(embed=user_info_embed(member))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await message.channel.send("No pude encontrar al miembro respondido.")
        return


@client.event
async def on_ready():
    print(f"Conectado como {client.user}")
    if not getattr(client, "ticket_views_registered", False):
        client.add_view(TicketPanelView())
        client.add_view(TicketCloseView())
        client.ticket_views_registered = True
    try:
        commands = await tree.sync(guild=GUILD)
        print(f"Comandos sincronizados: {len(commands)}")
    except Exception as exc:
        print(f"Error al sincronizar comandos: {exc}")


client.run(TOKEN)
