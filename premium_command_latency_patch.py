"""Keep slow Premium command handlers within Discord's interaction deadline."""
from pathlib import Path


TICKET_MARKER = "        # VANTARMOR_TICKET_IMAGE_DEFER_V1\n"


def patch_ticket_image_system(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if TICKET_MARKER in source:
        return

    start = source.find("        raw = None\n", source.find("async def ticket_image("))
    end = source.find("\n    return ticket_image", start)
    if start < 0 or end < 0:
        raise RuntimeError("No encontré el cuerpo de /ticket-image para responder antes del timeout.")

    replacement = '''        # Acknowledge now; reading and validating uploaded images may take longer than Discord's 3s deadline.
        await interaction.response.defer(ephemeral=True, thinking=True)
        # VANTARMOR_TICKET_IMAGE_DEFER_V1
        raw = None
        filename = None
        if foto:
            if foto.size > MAX_IMAGE_BYTES:
                await interaction.followup.send("La imagen debe pesar como máximo 5 MB.", ephemeral=True)
                return
            try:
                raw = await foto.read()
                _validate_image(raw)
                filename = Path(foto.filename).name
            except (discord.HTTPException, ValueError, OSError) as error:
                await interaction.followup.send(str(error), ephemeral=True)
                return
        view = TicketImageSetupView(guild, member.id, raw, filename)
        try:
            embed = view.preview_embed()
            preview = _make_panel_file({**view.draft, "enabled": True}) if view.draft.get("image_data") else None
        except (ValueError, OSError) as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await interaction.followup.send(embed=embed, view=view, file=preview, ephemeral=True)
'''
    source = source[:start] + replacement + source[end:]

    old_refresh = '''    async def refresh(self, interaction):
        try:
            embed = self.preview_embed()
            file = _make_panel_file({**self.draft, "enabled": True}) if self.draft.get("image_data") else None
            await interaction.response.edit_message(embed=embed, attachments=[file] if file else [], view=self)
        except (ValueError, OSError) as error:
            await interaction.response.send_message(str(error), ephemeral=True)
'''
    new_refresh = '''    async def refresh(self, interaction):
        try:
            # GIF rendering can be CPU-heavy; defer component interactions first.
            await interaction.response.defer()
            embed = self.preview_embed()
            file = _make_panel_file({**self.draft, "enabled": True}) if self.draft.get("image_data") else None
            await interaction.edit_original_response(embed=embed, attachments=[file] if file else [], view=self)
        except (ValueError, OSError) as error:
            if interaction.response.is_done():
                await interaction.followup.send(str(error), ephemeral=True)
            else:
                await interaction.response.send_message(str(error), ephemeral=True)
'''
    if old_refresh in source:
        source = source.replace(old_refresh, new_refresh, 1)

    path.write_text(source, encoding="utf-8")


def patch_backup_command(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    marker = "    # VANTARMOR_BACKUP_DEFER_V1\n"
    if marker in source:
        return
    old = "    await save_server_snapshot(guild)\n    await interaction.response.send_message("
    new = "    await interaction.response.defer(ephemeral=True, thinking=True)\n    # VANTARMOR_BACKUP_DEFER_V1\n    await save_server_snapshot(guild)\n    await interaction.followup.send("
    if old not in source:
        raise RuntimeError("No encontré /seguridad-copia para confirmar la interacción antes de guardar.")
    app_file.write_text(source.replace(old, new, 1), encoding="utf-8")


__all__ = ["patch_ticket_image_system", "patch_backup_command"]
