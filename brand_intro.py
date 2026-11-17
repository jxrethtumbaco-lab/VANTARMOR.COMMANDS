"""Install the animated Vantarmor brand intro on the public homepage."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def install_brand_intro():
    assets = ROOT / "website" / "assets"
    index = ROOT / "website" / "index.html"
    assets.mkdir(parents=True, exist_ok=True)
    html = index.read_text(encoding="utf-8")
    marker = '<div class="brand-intro-visual"'
    if marker not in html:
        anchor = '<main>'
        if anchor not in html:
            raise RuntimeError("No encontré el bloque principal para añadir la marca animada.")
        visual = '''<div class="brand-intro-visual" aria-hidden="true">
      <div class="brand-intro-vortex"></div>
      <div class="brand-intro-logo"><span>V</span></div>
      <div class="brand-intro-wordmark"></div>
    </div>'''
        html = html.replace(anchor, visual + anchor, 1)

    css_tag = '<link rel="stylesheet" href="/assets/brand-intro.css?v=2">'
    js_tag = '<script src="/assets/brand-intro.js?v=2" defer></script>'
    if css_tag not in html:
        html = html.replace("</head>", f"  {css_tag}\n</head>", 1)
    if js_tag not in html:
        html = html.replace("</body>", f"  {js_tag}\n</body>", 1)
    index.write_text(html, encoding="utf-8")


__all__ = ["install_brand_intro"]
