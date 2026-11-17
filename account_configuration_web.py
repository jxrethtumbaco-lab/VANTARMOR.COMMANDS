from pathlib import Path
import json
import urllib.parse


def install_account_configuration_styles():
    css = '''.account-settings { margin-top: 30px; padding: 24px; border: 1px solid rgba(255,255,255,.15); border-radius: 16px; background: rgba(15,15,17,.88); box-shadow: 0 0 24px rgba(255,255,255,.05); }\n.account-settings h3 { margin-top: 0; }\n.account-settings form { display: grid; gap: 10px; max-width: 650px; }\n.account-settings label { margin-top: 6px; color: #eee; font-size: 13px; font-weight: 600; }\n.account-settings input:not([type=file]), .account-settings select { min-height: 44px; padding: 10px 12px; color: #fff; background: #09090a; border: 1px solid rgba(255,255,255,.18); border-radius: 9px; }\n.account-settings input:focus, .account-settings select:focus { outline: 1px solid #69efff; border-color: #69efff; }\n.account-settings small { color: #aaa; }\n.account-settings #avatar-preview { width: 96px; height: 96px; object-fit: cover; border: 1px solid rgba(105,239,255,.45); border-radius: 14px; }\n.account-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }\n.account-admin-heading { margin-top: 30px; }\n.form-status.error { color: #ffaaaa; } .form-status.success { color: #b9ffdc; }\n'''
    path = Path(__file__).resolve().parent / "website" / "assets" / "account-settings.css"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(css, encoding="utf-8")
    index = path.parent.parent / "index.html"
    html = index.read_text(encoding="utf-8")
    link = '<link rel="stylesheet" href="/assets/account-settings.css">'
    if link not in html:
        html = html.replace('</head>', f'  {link}\n</head>', 1)
        index.write_text(html, encoding="utf-8")


def install_account_configuration(handler_class):
    """Serve the account image script; configuration stays free for server admins."""
    previous_get = handler_class.do_GET
    index_path = Path(__file__).resolve().parent / "website" / "index.html"
    script_tag = '<script src="/assets/profile-upload.js" defer></script>'

    def do_get(self):
        if urllib.parse.urlparse(self.path).path not in ('/', '/index.html'):
            return previous_get(self)
        try:
            html = index_path.read_text(encoding='utf-8')
        except OSError:
            return previous_get(self)
        if script_tag not in html:
            html = html.replace('</body>', f'  {script_tag}\n</body>', 1)
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    handler_class.do_GET = do_get


__all__ = ['install_account_configuration', 'install_account_configuration_styles']
