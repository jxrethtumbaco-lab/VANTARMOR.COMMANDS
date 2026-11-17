(() => {
  let csrf = '';
  const $ = (id) => document.getElementById(id);
  const setStatus = (text, ok = false) => {
    $('status').textContent = text;
    $('status').style.color = ok ? 'var(--green)' : 'var(--muted)';
  };
  const request = async (path, body) => {
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
      body: JSON.stringify(body)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.message || `Error HTTP ${response.status}`);
    return data;
  };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  async function loadUsers() {
    const body = $('usersBody');
    body.innerHTML = '<tr><td colspan="5">Cargando usuarios…</td></tr>';
    try {
      const response = await fetch('/api/admin/users', {cache:'no-store', credentials:'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'No se pudo cargar la tabla.');
      const users = data.users || [];
      if (!users.length) { body.innerHTML = '<tr><td colspan="5">Todavía no hay usuarios registrados en la web.</td></tr>'; return; }
      body.innerHTML = users.map((user) => {
        const premium = Boolean(user.premium);
        const expiry = user.expires_at ? new Date(Number(user.expires_at) * 1000).toLocaleString('es') : (premium ? 'Permanente' : '—');
        const name = user.name || user.username || 'Usuario Discord';
        return `<tr><td>${escapeHtml(name)}</td><td><code>${escapeHtml(user.id)}</code></td><td><span class="badge ${premium?'':'no'}">${premium?'Premium':'Free'}</span></td><td>${escapeHtml(expiry)}</td><td>${premium?`<button class="button danger small" data-revoke-user="${escapeHtml(user.id)}">Revocar</button>`:'—'}</td></tr>`;
      }).join('');
      body.querySelectorAll('[data-revoke-user]').forEach((button) => button.addEventListener('click', async () => {
        if (!confirm(`¿Revocar Premium al usuario ${button.dataset.revokeUser}?`)) return;
        try { await request('/api/admin/revoke', {user_id: button.dataset.revokeUser}); setStatus('Acceso Premium revocado.', true); await loadUsers(); }
        catch (error) { setStatus(error.message); }
      }));
    } catch (error) { body.innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`; }
  }

  async function init() {
    try {
      const response = await fetch('/api/me', {cache:'no-store', credentials:'same-origin'});
      const session = await response.json();
      $('loading').classList.add('hidden');
      if (!response.ok || !session.authenticated || !session.is_admin) { $('denied').classList.remove('hidden'); return; }
      csrf = session.csrf || '';
      $('dashboard').classList.remove('hidden');
      await loadUsers();
    } catch (_) {
      $('loading').textContent = 'No se pudo verificar la sesión. Inicia sesión con Discord y vuelve a entrar.';
    }
  }

  $('generateForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try { const data = await request('/api/admin/keys/generate', {days:Number($('keyDays').value)}); $('generatedKey').textContent = `Key generada (${data.days} días): ${data.key}`; setStatus('Key creada correctamente. Cópiala ahora; no se vuelve a mostrar.', true); }
    catch (error) { setStatus(error.message); }
  });
  $('grantPermanent').addEventListener('change', () => { $('grantDays').disabled = $('grantPermanent').checked; });
  $('grantForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try { await request('/api/admin/grant', {user_id:$('grantUser').value.trim(), permanent:$('grantPermanent').checked, days:Number($('grantDays').value)}); setStatus('Premium concedido correctamente.', true); $('grantUser').value=''; await loadUsers(); }
    catch (error) { setStatus(error.message); }
  });
  $('revokeKeyForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try { const data = await request('/api/admin/keys/revoke', {key:$('revokeKey').value.trim()}); setStatus(data.message || 'Key revocada.', true); $('revokeKey').value=''; await loadUsers(); }
    catch (error) { setStatus(error.message); }
  });
  $('revokeUserForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try { await request('/api/admin/revoke', {user_id:$('revokeUser').value.trim()}); setStatus('Acceso Premium revocado.', true); $('revokeUser').value=''; await loadUsers(); }
    catch (error) { setStatus(error.message); }
  });
  $('refresh').addEventListener('click', loadUsers);
  init();
})();
