"""Per-guild approval flow for newly added Discord bots."""
from datetime import datetime, timezone
from urllib.parse import urlencode

import discord
from discord import app_commands

from premium_security_system import (
    _guild_config,
    _require_premium_admin,
    _security_log,
    _update_guild,
)


def _invite_url(bot_id: int, guild_id: int) -> str:
    query = urlencode({
        "client_id": str(bot_id),
        "scope": "bot applications.commands",
        "guild_id": str(guild_id),
        "disable_guild_select": "true",
        "permissions": "0",
    })
    return f"https://discord.com/oauth2/authorize?{query}"


async def _find_bot_add_actor(guild: discord.Guild, bot_id: int):
    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.view_audit_log:
        return None
    try:
        async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.bot_add):
            target = getattr(entry, "target", None)
            if getattr(target, "id", None) == bot_id:
                age = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
                if age <= 120:
                    return entry.user
                break
    except (discord.Forbidden, discord.HTTPException):
        pass
    return None


async def _secure_audit_channel(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name="auditoria-logs")
    bot_member = guild.me
    if channel is None or bot_member is None:
        return channel

    # Hide the channel from @everyone and non-admin overrides. Discord's
    # Administrator permission still grants access; the owner is explicitly allowed.
    try:
        await channel.set_permissions(
            guild.default_role,
            overwrite=discord.PermissionOverwrite(view_channel=False),
            reason="Restringir auditoria-logs a administradores y propietario",
        )
        for target, old_overwrite in list(channel.overwrites.items()):
            overwrite = old_overwrite.copy()
            if isinstance(target, discord.Role):
                if target.is_default():
                    continue
                if not target.permissions.administrator:
                    overwrite.view_channel = False
                    await channel.set_permissions(target, overwrite=overwrite, reason="Privacidad de auditoria-logs")
            elif isinstance(target, discord.Member):
                if target.id == guild.owner_id or target.guild_permissions.administrator or target.id == bot_member.id:
                    overwrite.view_channel = True
                    overwrite.send_messages = True
                    overwrite.embed_links = True
                else:
                    overwrite.view_channel = False
                await channel.set_permissions(target, overwrite=overwrite, reason="Privacidad de auditoria-logs")
        await channel.set_permissions(
            bot_member,
            view_channel=True,
            send_messages=True,
            embed_links=True,
            read_message_history=True,
            reason="Permitir registros de seguridad",
        )
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No se pudieron asegurar permisos de auditoria-logs en {guild.id}: {type(exc).__name__}")
    return channel


async def _audit_bot_event(guild: discord.Guild, title: str, detail: str):
    channel = await _secure_audit_channel(guild)
    if channel is None:
        return
    embed = discord.Embed(title=title, description=detail[:3500], color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"No se pudo registrar Anti-Bot en {guild.id}: {type(exc).__name__}")


class BotApprovalView(discord.ui.View):
    def __init__(self, client: discord.Client, guild_id: int, bot_id: int, bot_name: str):
        super().__init__(timeout=86400)
        self.client = client
        self.guild_id = guild_id
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.finished:
            await interaction.response.send_message("Esta solicitud ya fue resuelta o expiró.", ephemeral=True)
            return False
        guild = self.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message("El servidor ya no está disponible; vuelve a intentarlo después.", ephemeral=True)
            return False
        member = guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None
        if member is None or (member.id != guild.owner_id and not member.guild_permissions.administrator):
            await interaction.response.send_message("Solo el propietario o un administrador del servidor puede decidir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Autorizar", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message("El servidor ya no está disponible.", ephemeral=True)
            return

        def allow_bot(state):
            allowed = {str(value) for value in state.get("allowed_bots", [])}
            allowed.add(str(self.bot_id))
            state["allowed_bots"] = sorted(allowed)
            denied = {str(value) for value in state.get("denied_bots", [])}
            denied.discard(str(self.bot_id))
            state["denied_bots"] = sorted(denied)

        try:
            _update_guild(guild.id, allow_bot)
        except OSError:
            await interaction.response.send_message("No pude guardar la autorización. Inténtalo otra vez.", ephemeral=True)
            return

        self.finished = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"✅ Se autorizó **{self.bot_name}** para este servidor.", embed=None, view=self)
        link_view = discord.ui.View(timeout=300)
        link_view.add_item(discord.ui.Button(label="Invitar bot al servidor", style=discord.ButtonStyle.link, url=_invite_url(self.bot_id, self.guild_id)))
        await interaction.followup.send(
            "Discord requiere que un administrador confirme la instalación. Usa el botón para añadir el bot autorizado; tendrá los permisos que selecciones.",
            view=link_view,
            ephemeral=True,
        )
        await _audit_bot_event(guild, "✅ Bot autorizado", f"**Bot:** {self.bot_name} (`{self.bot_id}`)\n**Autorizado por:** {interaction.user} (`{interaction.user.id}`). Se proporcionó el enlace OAuth para instalarlo.")

    @discord.ui.button(label="🚫 Negar", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message("El servidor ya no está disponible.", ephemeral=True)
            return

        def deny_bot(state):
            allowed = {str(value) for value in state.get("allowed_bots", [])}
            allowed.discard(str(self.bot_id))
            state["allowed_bots"] = sorted(allowed)
            denied = {str(value) for value in state.get("denied_bots", [])}
            denied.add(str(self.bot_id))
            state["denied_bots"] = sorted(denied)

        try:
            _update_guild(guild.id, deny_bot)
        except OSError:
            await interaction.response.send_message("No pude guardar la decisión. Inténtalo otra vez.", ephemeral=True)
            return

        self.finished = True
        for item in self.children:
            item.disabled = True
        current_bot = guild.get_member(self.bot_id)
        kick_result = "El bot ya no estaba en el servidor."
        if current_bot is not None:
            bot_member = guild.me
            if bot_member and bot_member.guild_permissions.kick_members:
                try:
                    await guild.kick(current_bot, reason=f"Anti-Bot: denegado por {interaction.user} ({interaction.user.id})")
                    kick_result = "Se expulsó el bot del servidor."
                except (discord.Forbidden, discord.HTTPException) as exc:
                    kick_result = f"No se pudo expulsar; revisa permiso Expulsar miembros y jerarquía ({type(exc).__name__})."
            else:
                kick_result = "Al bot de seguridad le falta Expulsar miembros; el bot no autorizado sigue dentro."
        await interaction.response.edit_message(content=f"🚫 Se negó **{self.bot_name}**. {kick_result}", embed=None, view=self)
        await _audit_bot_event(guild, "🚫 Bot denegado", f"**Bot:** {self.bot_name} (`{self.bot_id}`)\n**Decisión de:** {interaction.user} (`{interaction.user.id}`).\n{kick_result}")

    async def on_timeout(self):
        self.finished = True
        for item in self.children:
            item.disabled = True


async def on_member_join(member: discord.Member):
    if not member.bot:
        return
    guild = member.guild
    state = _guild_config(guild.id)
    if not state.get("anti_bot_enabled", False):
        return
    if str(member.id) in {str(value) for value in state.get("allowed_bots", [])}:
        return

    actor = await _find_bot_add_actor(guild, member.id)
    # Reject immediately so an unapproved bot cannot operate while the owner decides.
    kicked = False
    bot_member = guild.me
    if bot_member and bot_member.guild_permissions.kick_members:
        try:
            await guild.kick(member, reason="Anti-Bot: requiere autorización del propietario o un administrador")
            kicked = True
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"No se pudo retirar el bot pendiente {member.id} de {guild.id}: {type(exc).__name__}")

    view = BotApprovalView(member._state._get_client(), guild.id, member.id, str(member))
    embed = discord.Embed(
        title="🤖 Solicitud de bot nuevo",
        description=(
            f"Un bot extraño quiere ingresar a tu servidor **{guild.name}**.\n\n"
            f"Por medidas de seguridad, **{member}** (`{member.id}`) todavía no está autorizado.\n"
            f"¿Qué hacemos?\n\n"
            f"{'El bot fue retirado mientras esperábamos tu decisión.' if kicked else 'No se pudo retirar automáticamente; comprueba el permiso Expulsar miembros.'}"
        ),
        color=discord.Color.orange(),
    )
    recipients = {guild.owner_id}
    if isinstance(actor, discord.Member) and (actor.id == guild.owner_id or actor.guild_permissions.administrator):
        recipients.add(actor.id)

    dm_sent = 0
    for recipient_id in recipients:
        try:
            user = member._state._get_client().get_user(recipient_id) or await member._state._get_client().fetch_user(recipient_id)
            await user.send(embed=embed, view=BotApprovalView(member._state._get_client(), guild.id, member.id, str(member)))
            dm_sent += 1
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            continue

    await _audit_bot_event(
        guild,
        "⚠️ Solicitud de bot no autorizado",
        f"**Servidor:** {guild.name} (`{guild.id}`)\n**Bot:** {member} (`{member.id}`)\n**Añadido por:** {actor or 'No identificado'}\n**DM entregado:** {dm_sent}\n{'Bot retirado mientras se espera aprobación.' if kicked else 'No se pudo retirar automáticamente; revisar permisos.'}",
    )


def register_anti_bot_approval(tree, client):
    """Register the boolean /anti-bot toggle and pending-bot approval listener."""
    if not getattr(client, "anti_bot_approval_listener_registered", False):
        client.event(on_member_join)
        client.anti_bot_approval_listener_registered = True

    if tree.get_command("anti-bot", guild=discord.Object(id=int(__import__("os").getenv("GUILD_ID", "1559455132821753856")))) is not None:
        return

    @tree.command(name="anti-bot", description="Activa o desactiva la aprobación de bots nuevos")
    @app_commands.describe(accion="true activa; false desactiva Anti-Bot")
    async def anti_bot(interaction: discord.Interaction, accion: bool):
        if not await _require_premium_admin(interaction):
            return
        try:
            _update_guild(interaction.guild.id, lambda state: state.update(anti_bot_enabled=bool(accion)))
        except OSError:
            await interaction.response.send_message("No pude guardar la configuración. Inténtalo otra vez.", ephemeral=True)
            return
        status = "activada" if accion else "desactivada"
        explanation = "Los bots nuevos no autorizados serán retirados mientras el propietario/admin decide por DM." if accion else "Los nuevos bots podrán entrar sin aprobación de esta protección."
        await interaction.response.send_message(f"✅ Protección Anti-Bot {status}. {explanation}", ephemeral=True)


__all__ = ["register_anti_bot_approval", "BotApprovalView"]
