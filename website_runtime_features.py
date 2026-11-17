"""Install website guild filtering, statistics assets, and live Discord status hooks."""
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

import guild_profile_settings
import web_server

_STATUS_LOCK = threading.RLock()
_STATUS = {"online": False, "servers": 0, "slash_commands": 0}
_STATS_FEATURES = [
    "Anti-Raid y alertas de seguridad",
    "Anti-Nuke con modo pánico manual",
    "Anti-Bot y lista autorizada",
    "Filtro de cuentas nuevas",
    "Moderación y bloqueo de canales",
    "Tickets, registros y copias de seguridad",
]


def set_bot_status(online, guild_count=0, command_count=0):
    with _STATUS_LOCK:
        _STATUS.update(online=bool(online), servers=max(0, int(guild_count)), slash_commands=max(0, int(command_count)))


def _bot_present_guilds(guilds):
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ValueError("El bot no está configurado en este servicio.")
    present = []
    for guild in guilds:
        guild_id = str(guild.get("id", ""))
        if not guild_id.isdecimal():
            continue
        try:
            guild_profile_settings._discord_json(f"/guilds/{guild_id}", token=token)
            present.append(guild)
        except HTTPError as error:
            if error.code not in (403, 404):
                raise
    return present


def _manageable_guilds(session):
    guilds = web_server.discord_request("/users/@me/guilds", token=session["access_token"])
    return [guild for guild in guilds if guild.get("owner") or int(guild.get("permissions", "0")) & (0x8 | 0x20)]


def install_website_api(handler_class):
    """Serve manageable invite targets separately from bot-installed settings guilds."""
    previous_get = handler_class.do_GET

    def do_get(self):
        path = urlparse(self.path).path
        if path in ("/api/guilds", "/api/settings/guilds"):
            session = self.get_session()
            if not session:
                return self.send_json({"error": "inicia_sesion"}, 401)
            try:
                manageable = _manageable_guilds(session)
                if path == "/api/settings/guilds":
                    guilds = _bot_present_guilds(manageable)
                    return self.send_json({"guilds": [{"id": g["id"], "name": g["name"]} for g in guilds]})
                installed = {g["id"] for g in _bot_present_guilds(manageable)}
                return self.send_json({"guilds": [{"id": g["id"], "name": g["name"], "bot_installed": g["id"] in installed} for g in manageable]})
            except (HTTPError, URLError, OSError, ValueError, TypeError):
                return self.send_error_json("No se pudieron cargar tus servidores de Discord.", 502)

        if path == "/api/stats":
            from premium_store import public_stats
            stats = public_stats()
            with _STATUS_LOCK:
                status = dict(_STATUS)
            stats.update(bot_online=status["online"], servers=status["servers"], slash_commands=status["slash_commands"], security_features=_STATS_FEATURES)
            return self.send_json(stats)
        return previous_get(self)

    handler_class.do_GET = do_get


def install_bot_status_hooks(app_file):
    """Patch app.py so website status reflects Discord gateway readiness."""
    source = app_file.read_text(encoding="utf-8")
    marker = "# VANTARMOR_WEBSITE_STATUS_HOOKS_V1"
    if marker in source:
        return
    import_anchor = "from discord import app_commands\n"
    if "import website_runtime_features\n" not in source:
        if import_anchor not in source:
            raise RuntimeError("No encontré el bloque de imports de app.py para el estado web.")
        source = source.replace(import_anchor, import_anchor + "import website_runtime_features\n", 1)
    ready_anchor = '    print(f"Conectado como {client.user}")\n'
    ready_status = "    website_runtime_features.set_bot_status(True, len(client.guilds), len(tree.get_commands()))\n"
    if ready_anchor not in source:
        raise RuntimeError("No encontré on_ready para actualizar el estado de la web.")
    if ready_status not in source:
        source = source.replace(ready_anchor, ready_anchor + ready_status, 1)
    run_anchor = "client.run(TOKEN)\n"
    if run_anchor not in source:
        raise RuntimeError("No encontré client.run para conectar el estado web.")
    hooks = (
        "@client.event\nasync def on_disconnect():\n"
        "    website_runtime_features.set_bot_status(False, len(client.guilds), len(tree.get_commands()))\n\n\n"
        "@client.event\nasync def on_resumed():\n"
        "    website_runtime_features.set_bot_status(True, len(client.guilds), len(tree.get_commands()))\n\n\n"
        f"{marker}\n"
    )
    source = source.replace(run_anchor, hooks + run_anchor, 1)
    app_file.write_text(source, encoding="utf-8")


def install_website_assets():
    index_file = os.path.join(os.path.dirname(__file__), "website", "index.html")
    try:
        with open(index_file, encoding="utf-8") as file:
            html = file.read()
    except OSError:
        return
    css = '<link rel="stylesheet" href="/assets/stats.css">'
    script = '<script src="/assets/stats.js" defer></script>'
    if css not in html:
        html = html.replace("</head>", f"  {css}\n</head>", 1)
    if script not in html:
        html = html.replace("</body>", f"  {script}\n</body>", 1)
    with open(index_file, "w", encoding="utf-8") as file:
        file.write(html)


def install_dynamic_tab_support(app_js):
    app_js.parent.mkdir(parents=True, exist_ok=True)
    if not app_js.exists():
        app_js.write_text("""
document.addEventListener('DOMContentLoaded', () => {
  const menuToggle = document.getElementById('menu-toggle');
  const nav = document.getElementById('nav');
  if (menuToggle && nav) {
    menuToggle.addEventListener('click', () => {
      const expanded = menuToggle.getAttribute('aria-expanded') === 'true';
      menuToggle.setAttribute('aria-expanded', String(!expanded));
      nav.classList.toggle('open', !expanded);
    });
  }

  const accountCard = document.getElementById('profile-card');
  const getText = (value, fallback) => value ?? fallback;

  fetch('/api/stats').then((res) => res.ok ? res.json() : null).then((stats) => {
    if (!stats) return;
    const online = document.querySelector('#estado .online');
    if (online) online.textContent = stats.bot_online ? 'Operativo' : 'Sin conexión';
  }).catch(() => {});

  fetch('/api/me').then((res) => {
    if (!res.ok) return;
    return res.json();
  }).then((session) => {
    if (!session || !session.authenticated || !accountCard) return;
    const avatar = document.getElementById('profile-avatar') || accountCard.querySelector('.avatar');
    const name = document.getElementById('profile-name');
    if (avatar) avatar.textContent = getText(session.user.name, 'User').slice(0, 1).toUpperCase();
    if (name) name.textContent = getText(session.user.name, 'Usuario');
  }).catch(() => {});
});
""".strip() + "\n", encoding="utf-8")
        return
    source = app_js.read_text(encoding="utf-8")
    source = source.replace('const tabSections = [...document.querySelectorAll("main > section[id]")];', 'const getTabSections = () => [...document.querySelectorAll("main > section[id]")];')
    source = source.replace('  const active = tabSections.find((section) => section.id === id) || tabSections[0];', '  const tabSections = getTabSections();\n  const active = tabSections.find((section) => section.id === id) || tabSections[0];')
    if "window.activateTab = activateTab;" not in source:
        source = source.replace("function toast(message) {", "window.activateTab = activateTab;\n\nfunction toast(message) {", 1)
    source = source.replace('const result = await api("/api/guilds");', 'const result = await api("/api/settings/guilds");')
    source = source.replace('const result = await api("/api/settings/guilds");', 'const result = await api("/api/settings/guilds");')
    marker = "// VANTARMOR_INVITE_AFTER_LOGIN_V1"
    if marker not in source:
        source = source.replace(
            "function setupPremiumKeyClaim() {",
            marker + "\nfunction setupPremiumKeyClaim() {",
            1,
        )
        configure_anchor = "  select?.addEventListener(\"change\", () => {\n"
        source = source.replace(
            configure_anchor,
            configure_anchor + "    const headerInvite = document.querySelector('header a[href=\"/auth/discord\"]');\n",
            1,
        )
        change_anchor = "    button.href = url.toString();\n"
        source = source.replace(
            change_anchor,
            change_anchor + "    if (headerInvite && headerInvite.dataset.authenticated === \"true\") headerInvite.href = button.href;\n",
            1,
        )
        auth_anchor = '  if (accountActions) accountActions.innerHTML = \'<a class="button secondary button-small" href="/auth/logout">Cerrar sesión</a>\';\n'
        auth_code = '''  const headerInvite = document.querySelector('header a[href="/auth/discord"]');
  const inviteButton = $("#invite-button");
  if (headerInvite) {
    headerInvite.textContent = "Invitar bot";
    headerInvite.dataset.authenticated = "true";
    headerInvite.href = inviteButton?.href || "/#invitar";
    headerInvite.target = "_blank";
    headerInvite.rel = "noopener";
  }
'''
        source = source.replace(auth_anchor, auth_anchor + auth_code, 1)
    app_js.write_text(source, encoding="utf-8")


__all__ = ["install_bot_status_hooks", "install_dynamic_tab_support", "install_website_api", "install_website_assets", "set_bot_status"]
