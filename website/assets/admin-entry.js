(() => {
  async function addAdminShortcut() {
    try {
      const response = await fetch('/api/me', {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok) return;
      const session = await response.json();
      if (!session.authenticated || !session.is_admin) return;

      const account = document.getElementById('cuenta');
      if (!account || document.getElementById('adminShortcut')) return;
      const card = document.createElement('article');
      card.className = 'card';
      card.style.marginTop = '16px';
      card.innerHTML = '<h3>Administración privada</h3><p class="muted">Gestiona keys y accesos Premium de usuarios.</p><a id="adminShortcut" class="button" href="/admin">Abrir panel de administración →</a>';
      account.appendChild(card);
    } catch (_) {
      // Fail closed: hide the admin entry if permission cannot be verified.
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addAdminShortcut, {once: true});
  else addAdminShortcut();
})();
