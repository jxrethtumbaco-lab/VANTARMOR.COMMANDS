"""Premium, private ticket-image configuration; /ticket-panel publishes the applied style."""
import asyncio
import base64
import io
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from PIL import Image, ImageOps, UnidentifiedImageError

from premium_backup_system import is_premium_user

DATA_DIR = Path(os.getenv("VANTARMOR_DATA_DIR", "."))
STORE = DATA_DIR / "ticket_image_panels.json"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
_STORE_LOCK = threading.RLock()
_BOT = None


def _read_store():
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_store(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = STORE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STORE)


def _get_guild_state(guild_id):
    with _STORE_LOCK:
        return _read_store().get(str(guild_id), {})


def _save_guild_state(guild_id, state):
    with _STORE_LOCK:
        data = _read_store()
        data[str(guild_id)] = state
        _write_store(data)


def _validate_image(raw):
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("La imagen debe pesar como máximo 5 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "GIF", "BMP"}:
                raise ValueError("Formato no compatible. Usa PNG, JPG, WEBP, GIF o BMP.")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("La resolución de la imagen es demasiado grande.")
            image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("El archivo no contiene una imagen válida.") from error


def _as_side_to_side_gif(raw):
    """Turn an image into a smooth, looping GIF that moves left and right."""
    _validate_image(raw)
    width, height, count = 560, 190, 24
    frames = []
    with Image.open(io.BytesIO(raw)) as source:
        source.seek(0)
        art = source.convert("RGBA")
        art.thumbnail((width // 2, height - 20), Image.Resampling.LANCZOS)
        y = (height - art.height) // 2
        for index in range(count):
            phase = index / (count - 1)
            x = round((width - art.width) * (0.5 - 0.5 * __import__("math").cos(phase * 2 * __import__("math").pi)))
            frame = Image.new("RGBA", (width, height), (7, 8, 11, 255))
            frame.alpha_composite(art, (x, y))
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))
    output = io.BytesIO()
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=70, loop=0, optimize=True, disposal=2)
    result = output.getvalue()
    if len(result) > MAX_IMAGE_BYTES:
        raise ValueError("El GIF generado supera el límite de 5 MB. Prueba una imagen más pequeña.")
    return result


def _image_for_state(state):
    encoded = state.get("image_data")
    if not encoded:
        return None, None
    raw = base64.b64decode(encoded, validate=True)
    if state.get("mode") == "gif":
        return _as_side_to_side_gif(raw), "ticket-panel.gif"
    filename = state.get("filename") or "ticket-panel.png"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        filename = "ticket-panel.png"
    return raw, filename


def _make_panel_embed(base, state):
    embed = discord.Embed(
        title=base.get("title", "🎫 Soporte"),
        description=base.get("description", "Pulsa el botón para abrir un ticket privado."),
        color=int(base.get("color", discord.Color.blurple().value)),
    )
    if state.get("enabled") and state.get("image_data"):
        _, filename = _image_for_state(state)
        embed.set_image(url=f"attachment://{filename}")
    return embed


def _make_panel_file(state):
    if not state.get("enabled") or not state.get("image_data"):
        return None
    raw, filename = _image_for_state(state)
    return discord.File(io.BytesIO(raw), filename=filename)


async def apply_ticket_image_to_panel(guild, embed):
    """Apply the saved per-guild style to a new /ticket-panel message."""
    state = _get_guild_state(guild.id)
    if not state:
        return embed, None
    base = {"title": embed.title or "🎫 Soporte", "description": embed.description or "", "color": embed.color.value if embed.color else discord.Color.blurple().value}
    state["panel_base"] = base
    embed = _make_panel_embed(base, state)
    return embed, _make_panel_file(state)


async def save_ticket_panel_reference(guild_id, channel_id, message):
    state = _get_guild_state(guild_id)
    state["panel_channel_id"] = int(channel_id)
    state["panel_message_id"] = int(message.id)
    if message.embeds:
        embed = message.embeds[0]
        state["panel_base"] = {"title": embed.title or "🎫 Soporte", "description": embed.description or "", "color": embed.color.value if embed.color else discord.Color.blurple().value}
    _save_guild_state(guild_id, state)


async def _refresh_published_panel(guild_id, state):
    if _BOT is None or not state.get("panel_channel_id") or not state.get("panel_message_id"):
        return
    channel = _BOT.get_channel(int(state["panel_channel_id"]))
    if channel is None:
        try:
            channel = await _BOT.fetch_channel(int(state["panel_channel_id"]))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
    try:
        message = await channel.fetch_message(int(state["panel_message_id"]))
        embed = _make_panel_embed(state.get("panel_base", {}), state)
        image_file = _make_panel_file(state)
        await message.edit(embed=embed, attachments=[image_file] if image_file else [], allowed_mentions=discord.AllowedMentions.none())
    except (ValueError, OSError, discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
        print(f"No se pudo actualizar el panel de tickets del servidor {guild_id}: {type(error).__name__}")


class ImageSourceSelect(discord.ui.Select):
    def __init__(self, view):
        options = [discord.SelectOption(label="Usar imagen subida", value="upload", default=view.draft.get("source") == "upload")]
        if view.guild.icon:
            options.append(discord.SelectOption(label="Usar icono del servidor", value="guild", default=view.draft.get("source") == "guild"))
        super().__init__(placeholder="Elige la imagen del panel", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction):
        view = self.view
        if self.values[0] == "guild":
            if not interaction.guild or not interaction.guild.icon:
                await interaction.response.send_message("Este servidor no tiene un icono configurado.", ephemeral=True)
                return
            try:
                raw = await interaction.guild.icon.replace(size=512).read()
                _validate_image(raw)
            except (discord.HTTPException, ValueError, OSError) as error:
                await interaction.response.send_message(f"No pude obtener el icono del servidor: {error}", ephemeral=True)
                return
            view.draft.update(image_data=base64.b64encode(raw).decode("ascii"), filename="server-icon.png", source="guild")
        elif view.uploaded_image:
            view.draft.update(image_data=base64.b64encode(view.uploaded_image).decode("ascii"), filename=view.uploaded_filename, source="upload")
        else:
            await interaction.response.send_message("Sube una imagen al ejecutar `/ticket-image` para usar esta opción.", ephemeral=True)
            return
        await view.refresh(interaction)


class ImageModeSelect(discord.ui.Select):
    def __init__(self, view):
        super().__init__(placeholder="Elige el efecto de imagen", min_values=1, max_values=1, options=[
            discord.SelectOption(label="Imagen normal", value="normal", default=view.draft.get("mode") == "normal"),
            discord.SelectOption(label="GIF animado de lado a lado", value="gif", default=view.draft.get("mode") == "gif"),
        ], row=1)

    async def callback(self, interaction):
        self.view.draft["mode"] = self.values[0]
        await self.view.refresh(interaction)


class TicketImageSetupView(discord.ui.View):
    def __init__(self, guild, owner_id, uploaded_image=None, uploaded_filename=None):
        super().__init__(timeout=600)
        self.guild = guild
        self.owner_id = owner_id
        self.uploaded_image = uploaded_image
        self.uploaded_filename = uploaded_filename or "ticket-image.png"
        existing = _get_guild_state(guild.id)
        source = "upload" if uploaded_image else ("guild" if guild.icon else "upload")
        initial = base64.b64encode(uploaded_image).decode("ascii") if uploaded_image else ""
        if not uploaded_image and guild.icon:
            self.draft = {"image_data": existing.get("image_data", ""), "filename": existing.get("filename", "server-icon.png"), "source": existing.get("source", "guild"), "mode": existing.get("mode", "normal"), "enabled": existing.get("enabled", False)}
        else:
            self.draft = {"image_data": initial or existing.get("image_data", ""), "filename": self.uploaded_filename if initial else existing.get("filename", "ticket-image.png"), "source": source, "mode": existing.get("mode", "normal"), "enabled": existing.get("enabled", False)}
        self.applied = False
        self.add_item(ImageSourceSelect(self))
        self.add_item(ImageModeSelect(self))
        apply_button = discord.ui.Button(label="Aplicar cambio", style=discord.ButtonStyle.primary, row=2)
        apply_button.callback = self.apply
        self.add_item(apply_button)
        self.toggle_button = discord.ui.Button(label="🟢 Encender" if not self.draft.get("enabled") else "🔴 Apagar", style=discord.ButtonStyle.success if not self.draft.get("enabled") else discord.ButtonStyle.danger, disabled=True, row=2)
        self.toggle_button.callback = self.toggle
        self.add_item(self.toggle_button)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Solo quien ejecutó `/ticket-image` puede configurar este panel.", ephemeral=True)
            return False
        return True

    def preview_embed(self):
        mode = "GIF animado que se mueve de lado a lado" if self.draft.get("mode") == "gif" else "imagen normal"
        source = "icono del servidor" if self.draft.get("source") == "guild" else "imagen subida"
        embed = discord.Embed(title="🎟️ Configurar imagen de tickets", description=f"Servidor: **{self.guild.name}**\nImagen: **{source}**\nEfecto: **{mode}**\n\nLa configuración se aplicará al próximo `/ticket-panel` y se guardará para este servidor.", color=discord.Color.blurple())
        if self.draft.get("image_data"):
            raw, filename = _image_for_state(self.draft)
            embed.set_image(url=f"attachment://{filename}")
        return embed

    async def refresh(self, interaction):
        try:
            embed = self.preview_embed()
            file = _make_panel_file({**self.draft, "enabled": True}) if self.draft.get("image_data") else None
            await interaction.response.edit_message(embed=embed, attachments=[file] if file else [], view=self)
        except (ValueError, OSError) as error:
            await interaction.response.send_message(str(error), ephemeral=True)

    async def apply(self, interaction):
        if not _is_panel_admin(interaction.user):
            await interaction.response.send_message("Solo el propietario o un administrador puede configurar este panel.", ephemeral=True)
            return
        if not is_premium_user(interaction.user.id):
            await interaction.response.send_message("`/ticket-image` requiere Premium activo en tu cuenta.", ephemeral=True)
            return
        if not self.draft.get("image_data"):
            await interaction.response.send_message("Elige el icono del servidor o sube una imagen al ejecutar el comando.", ephemeral=True)
            return
        state = {**self.draft, "guild_id": self.guild.id, "guild_name": self.guild.name, "created_by": self.owner_id, "updated_at": int(time.time())}
        try:
            _save_guild_state(self.guild.id, state)
        except OSError:
            await interaction.response.send_message("No pude guardar la configuración. Comprueba el volumen `VANTARMOR_DATA_DIR` de Railway.", ephemeral=True)
            return
        self.applied = True
        self.toggle_button.disabled = False
        self.toggle_button.label = "🔴 Apagar" if state.get("enabled") else "🟢 Encender"
        self.toggle_button.style = discord.ButtonStyle.danger if state.get("enabled") else discord.ButtonStyle.success
        await interaction.response.edit_message(content="✅ Cambios aplicados. Usa Encender/Apagar para controlar la imagen del próximo `/ticket-panel`.", embed=self.preview_embed(), view=self)
        await _refresh_published_panel(self.guild.id, state)

    async def toggle(self, interaction):
        if not self.applied:
            await interaction.response.send_message("Primero pulsa **Aplicar cambio**.", ephemeral=True)
            return
        state = _get_guild_state(self.guild.id)
        state["enabled"] = not bool(state.get("enabled"))
        state["updated_at"] = int(time.time())
        try:
            _save_guild_state(self.guild.id, state)
        except OSError:
            await interaction.response.send_message("No pude guardar el estado del panel.", ephemeral=True)
            return
        self.draft["enabled"] = state["enabled"]
        self.toggle_button.label = "🔴 Apagar" if state["enabled"] else "🟢 Encender"
        self.toggle_button.style = discord.ButtonStyle.danger if state["enabled"] else discord.ButtonStyle.success
        await interaction.response.edit_message(content=f"✅ Imagen de tickets {'encendida' if state['enabled'] else 'apagada'}. El estado se aplica también al panel publicado.", embed=self.preview_embed(), view=self)
        await _refresh_published_panel(self.guild.id, state)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


def _is_panel_admin(member):
    return isinstance(member, discord.Member) and (member.id == member.guild.owner_id or member.guild_permissions.administrator)


def register_ticket_image_commands(tree, client):
    global _BOT
    _BOT = client

    @tree.command(name="ticket-image", description="Configura la imagen GIF o normal del panel de tickets Premium")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(foto="Imagen opcional (PNG, JPG, WEBP o GIF; máximo 5 MB)")
    async def ticket_image(interaction: discord.Interaction, foto: Optional[discord.Attachment] = None):
        guild, member = interaction.guild, interaction.user
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message("Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return
        if not _is_panel_admin(member):
            await interaction.response.send_message("Solo el propietario o un administrador puede configurar tickets.", ephemeral=True)
            return
        if not is_premium_user(member.id):
            await interaction.response.send_message("`/ticket-image` requiere Premium activo en tu cuenta.", ephemeral=True)
            return
        raw = None
        filename = None
        if foto:
            if foto.size > MAX_IMAGE_BYTES:
                await interaction.response.send_message("La imagen debe pesar como máximo 5 MB.", ephemeral=True)
                return
            try:
                raw = await foto.read()
                _validate_image(raw)
                filename = Path(foto.filename).name
            except (discord.HTTPException, ValueError, OSError) as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
        view = TicketImageSetupView(guild, member.id, raw, filename)
        try:
            embed = view.preview_embed()
            preview = _make_panel_file({**view.draft, "enabled": True}) if view.draft.get("image_data") else None
        except (ValueError, OSError) as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(embed=embed, view=view, file=preview, ephemeral=True)

    return ticket_image


__all__ = ["register_ticket_image_commands", "apply_ticket_image_to_panel", "save_ticket_panel_reference"]
