(() => {
  const addAdminLink = async () => {
    try {
      const response = await fetch('/api/me', { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) return;
      const session = await response.json();
      if (!session.authenticated || !session.is_admin) return;

      const header = document.querySelector('.topbar');
      if (!header || document.getElementById('adminShortcut')) return;
      const link = document.createElement('a');
      link.id = 'adminShortcut';
      link.href = '/admin';
      link.textContent = 'Administración';
      link.setAttribute('aria-label', 'Abrir panel privado de administración');
      link.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:20;padding:11px 16px;border:1px solid #fff;border-radius:12px;background:#fff;color:#050505;font:700 14px system-ui,sans-serif;text-decoration:none;box-shadow:0 0 18px #fff9';
      document.body.appendChild(link);
    } catch (_) {
      // Do not display privileged navigation if authorization could not be verified.
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addAdminLink, { once: true });
  else addAdminLink();
})();
