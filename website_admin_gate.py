"""Inject a private admin shortcut only for authorized users; admin route stays server-guarded."""
from pathlib import Path
from urllib.parse import urlparse


def install_admin_entry(handler_class):
    previous_get = handler_class.do_GET
    index_path = Path(__file__).resolve().parent / "website" / "index.html"
    entry_script = '<script src="/assets/admin-entry.js" defer></script>'

    def do_get(self):
        if urlparse(self.path).path not in ("/", "/index.html"):
            return previous_get(self)
        try:
            html = index_path.read_text(encoding="utf-8")
        except OSError:
            return previous_get(self)
        if entry_script not in html:
            html = html.replace("</body>", f"  {entry_script}\n</body>", 1)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    handler_class.do_GET = do_get
