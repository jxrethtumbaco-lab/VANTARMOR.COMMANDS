"""Safe, confirmed recreation of a text channel without its message history."""
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands


class NukeConfirmView(discord.ui.View):
    def __init__(self, requester_id: int, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.requester_id = requester_id
        self.channel = channel
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("Solo quien inició `/nuke` puede confirmar o cancelar.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirmar recreación", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.send_message("Esta acción ya terminó.", ephemeral=True)
            return
        guild = interaction.guild
        if guild is None or self.channel.guild.id != guild.id:
            await interaction.response.send_message("El servidor ya no está disponible.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Necesitas Administrar canales para confirmar.", ephemeral=True)
            return
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await interaction.response.send_message("Al bot le falta el permiso Administrar canales.", ephemeral=True)
            return
        if getattr(guild, "rules_channel", None) == self.channel:
            await interaction.response.send_message("No se puede recrear el canal de reglas.", ephemeral=True)
            return

        self.finished = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Recreando el canal…", view=self)

        original = self.channel
        replacement = None
        try:
            # Discord clones the channel configuration/overwrites, but cannot copy messages.
            replacement = await original.clone(
                reason=f"/nuke confirmado por {interaction.user} ({interaction.user.id})"
            )
            await replacement.edit(position=original.position, reason="Restaurar posición del canal recreado")
            await original.delete(reason=f"Canal recreado por /nuke de {interaction.user} ({interaction.user.id})")
        except (discord.Forbidden, discord.HTTPException) as exc:
            if replacement is not None:
                try:
                    await replacement.delete(reason="Limpieza tras fallo de /nuke; conservar canal original")
                except (discord.Forbidden, discord.HTTPException):
                    await interaction.followup.send(
                        "Falló la recreación y no pude limpiar el clon. El canal original se conserva; revisa el canal duplicado manualmente.",
                        ephemeral=True,
                    )
                    return
            await interaction.followup.send(
                f"No se pudo recrear el canal; el original se conserva. Revisa permisos de Administrar canales. ({type(exc).__name__})",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✅ Canal recreado: {replacement.mention}. Solo se reemplazó este canal; sus mensajes no se copian.",
            ephemeral=True,
        )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.send_message("Esta acción ya terminó.", ephemeral=True)
            return
        self.finished = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Acción cancelada; no se modificó ningún canal.", view=self)

    async def on_timeout(self):
        self.finished = True
        for item in self.children:
            item.disabled = True


def register_channel_nuke(tree, guild=None):
    if tree.get_command("nuke", guild=guild) is not None:
        return

    @tree.command(name="nuke", description="Recrea un canal de texto; no copia los mensajes", guild=guild)
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(canal="Canal de texto que se recreará; por defecto, el canal actual")
    async def nuke_command(interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Necesitas Administrar canales.", ephemeral=True)
            return
        target = canal or interaction.channel
        if not isinstance(target, discord.TextChannel) or target.guild.id != interaction.guild.id:
            await interaction.response.send_message("Selecciona un canal de texto del mismo servidor.", ephemeral=True)
            return
        if getattr(interaction.guild, "rules_channel", None) == target:
            await interaction.response.send_message("No se puede recrear el canal de reglas.", ephemeral=True)
            return
        bot_member = interaction.guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await interaction.response.send_message("Al bot le falta el permiso Administrar canales.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"⚠️ Se eliminará **#{target.name}** y se creará un clon vacío con su configuración. "
            "El historial de mensajes no se puede conservar. Confirma para continuar.",
            view=NukeConfirmView(interaction.user.id, target),
            ephemeral=True,
        )


def patch_app_file(app_file: Path):
    """Install the nuke command into the clean app entry point, idempotently."""
    source = app_file.read_text(encoding="utf-8")
    import_anchor = "from discord import app_commands\n"
    import_line = "from channel_nuke import register_channel_nuke\n"
    tree_anchor = "tree = app_commands.CommandTree(client)\n"
    register_line = "register_channel_nuke(tree, GUILD)\n"

    if import_line not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el import app_commands para instalar /nuke.")
        source = source.replace(import_anchor, import_anchor + import_line, 1)
    if register_line not in source:
        if tree_anchor not in source:
            raise RuntimeError("No encontré la creación del árbol de comandos para instalar /nuke.")
        source = source.replace(tree_anchor, tree_anchor + register_line, 1)
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file", "register_channel_nuke"]
