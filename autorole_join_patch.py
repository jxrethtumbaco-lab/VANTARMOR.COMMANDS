"""Provide the join-event anchor expected by the welcome/backup installer."""
from pathlib import Path

EVENT_MARKER = "# VANTARMOR_AUTOROLE_JOIN_HANDLER_V1"
EVENT_ANCHOR = "@client.event\nasync def on_message(message):\n"

JOIN_HANDLER = '''# VANTARMOR_AUTOROLE_JOIN_HANDLER_V1
@client.event
async def on_member_join(member):
    role = get_role(member.guild, "autorole")
    if role is None:
        return
    bot_member = member.guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_roles or role >= bot_member.top_role:
        print(f"No se pudo aplicar autorol en {member.guild.id}: revisa Administrar roles y jerarquía.")
        return
    try:
        await member.add_roles(role, reason="Autorol configurado del servidor")
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"No se pudo aplicar autorol a {member.id} en {member.guild.id}: {type(error).__name__}: {error}")


'''


def patch_app_file(app_file: Path) -> None:
    source = app_file.read_text(encoding="utf-8")
    if EVENT_MARKER in source or "async def on_member_join(member):" in source:
        return
    if EVENT_ANCHOR not in source:
        raise RuntimeError("No encontré dónde instalar el evento de entrada en app.py.")
    source = source.replace(EVENT_ANCHOR, JOIN_HANDLER + EVENT_ANCHOR, 1)
    app_file.write_text(source, encoding="utf-8")
