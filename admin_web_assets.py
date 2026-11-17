from pathlib import Path


ADMIN_CSS = r'''
.admin-shell { width: min(1120px, calc(100% - 36px)); margin: 0 auto; padding: 48px 0 80px; }
.admin-heading { margin: 0 0 28px; }
.admin-heading h1 { font-size: clamp(38px, 6vw, 64px); }
.admin-heading p:last-child { max-width: 700px; }
.admin-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.admin-panel { margin: 0 0 18px; padding: 24px; border: 1px solid rgba(255,255,255,.14); border-radius: 17px; background: linear-gradient(145deg, rgba(20,20,22,.96), rgba(8,8,9,.96)); box-shadow: 0 0 28px rgba(255,255,255,.055); }
.admin-panel h2 { font-size: 24px; }
.admin-form { display: grid; gap: 9px; margin-top: 18px; }
.admin-form label { margin-top: 4px; color: #eee; font-size: 13px; font-weight: 600; }
.admin-form input:not([type=checkbox]), .admin-form select { width: 100%; min-height: 43px; padding: 10px 12px; border: 1px solid rgba(255,255,255,.18); border-radius: 9px; background: #09090a; color: #fff; }
.admin-form input:focus, .admin-form select:focus { outline: 1px solid #69efff; border-color: #69efff; }
.admin-form input[type=file] { padding: 8px; }
.check-label { display: flex; align-items: center; gap: 9px; }
.check-label input { accent-color: #69efff; }
.admin-status { min-height: 22px; color: #b9ffdc; }
.admin-status.error { color: #ffaaaa; }
.key-result { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 16px; }
.key-result code { max-width: 100%; overflow-wrap: anywhere; padding: 10px; border: 1px solid rgba(105,239,255,.25); border-radius: 8px; color: #d7faff; }
.danger { border-color: rgba(255,100,100,.42); }
.users-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
th, td { padding: 11px 9px; border-bottom: 1px solid rgba(255,255,255,.1); white-space: nowrap; }
th { color: #69efff; }
.guild-profile-panel { margin-top: 20px; }
.guild-profile-form { max-width: 680px; }
.guild-profile-form .hint { margin: 0; font-size: 12px; }
#avatar-preview { width: 96px; height: 96px; object-fit: cover; border: 1px solid rgba(105,239,255,.45); border-radius: 16px; }
@media (max-width: 600px) { .admin-shell { padding-top: 30px; } .admin-panel { padding: 18px; } .users-heading { align-items: flex-start; flex-direction: column; } }
'''


def install_admin_styles():
    path = Path(__file__).resolve().parent / "website" / "assets" / "admin.css"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ADMIN_CSS.strip() + "\n", encoding="utf-8")


__all__ = ["install_admin_styles"]
