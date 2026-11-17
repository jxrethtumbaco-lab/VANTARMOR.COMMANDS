from pathlib import Path

IMPORT_LINE = "from ticket_image_system import register_ticket_image_commands\n"
REGISTER_LINE = "register_ticket_image_commands(tree, client)\n"
PANEL_IMPORT = "from ticket_image_system import apply_ticket_image_to_panel, save_ticket_panel_reference\n"
PANEL_SEND = "        await canal.send(embed=embed, view=TicketPanelView())\n"
PANEL_REPLACEMENT = '''        embed, image_file = await apply_ticket_image_to_panel(interaction.guild, embed)
        try:
            panel_message = await canal.send(embed=embed, view=TicketPanelView(), file=image_file) if image_file else await canal.send(embed=embed, view=TicketPanelView())
            await save_ticket_panel_reference(interaction.guild.id, canal.id, panel_message)
        except (discord.Forbidden, discord.HTTPException) as error:
            await interaction.response.send_message(f"No pude enviar el panel: {error}", ephemeral=True)
            return
'''


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    import_anchor = "from discord import app_commands\n"
    if IMPORT_LINE not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el punto de importación de app_commands en app.py.")
        source = source.replace(import_anchor, import_anchor + IMPORT_LINE, 1)
    if PANEL_IMPORT not in source:
        source = source.replace(IMPORT_LINE, IMPORT_LINE + PANEL_IMPORT, 1)
    tree_anchor = "tree = app_commands.CommandTree(client)\n"
    if REGISTER_LINE not in source:
        if tree_anchor not in source:
            raise RuntimeError("No encontré la creación del árbol de comandos en app.py.")
        source = source.replace(tree_anchor, tree_anchor + REGISTER_LINE, 1)
    if PANEL_SEND in source:
        source = source.replace(PANEL_SEND, PANEL_REPLACEMENT, 1)
    elif "await apply_ticket_image_to_panel(interaction.guild, embed)" not in source:
        raise RuntimeError("No encontré el envío del panel `/ticket-panel` para aplicar el estilo configurado.")
    app_file.write_text(source, encoding="utf-8")


__all__ = ["patch_app_file"]
