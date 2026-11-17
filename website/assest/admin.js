const byId = (id) => document.getElementById(id);
let csrf = '';
let people = [];
async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || data.message || `Error HTTP ${response.status}`);
  return data;
}
function showStatus(text, error = false) { const el = byId('status'); el.textContent = text; el.classList.toggle('error', error); }
function filteredUsers() { const query = byId('user-search').value.trim().toLocaleLowerCase(); return people.filter((u) => `${u.name || ''} ${u.username || ''} ${u.id}`.toLocaleLowerCase().includes(query)); }
function renderUsers() {
  const selected = byId('user-select').value; const visible = filteredUsers(); const select = byId('user-select');
  select.replaceChildren(new Option(visible.length ? 'Elige una cuenta' : 'No hay coincidencias', ''));
  visible.forEach((user) => select.add(new Option(`${user.name || user.username || 'Usuario'} · ${user.id}${user.premium ? ' · Premium' : ''}`, user.id)));
  if (visible.some((user) => user.id === selected)) select.value = selected;
  const tbody = byId('users'); tbody.replaceChildren();
  visible.forEach((user) => { const row = document.createElement('tr'); const expiry = user.expires_at == null ? (user.premium ? 'Permanente' : '—') : new Date(user.expires_at * 1000).toLocaleString(); [user.name || '—', user.username ? `@${user.username}` : '—', user.id, user.premium ? 'Activo' : 'No activo', expiry].forEach((value) => { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }); tbody.append(row); });
  if (!visible.length) { const row = document.createElement('tr'); const cell = document.createElement('td'); cell.colSpan = 5; cell.textContent = people.length ? 'No hay coincidencias.' : 'Aún no hay usuarios registrados.'; row.append(cell); tbody.append(row); }
}
async function loadUsers() { const result = await api('/api/admin/users'); people = result.users; renderUsers(); }
async function postAdmin(url, payload) { return api(url, { method: 'POST', headers: { 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }); }
async function init() { try { const me = await api('/api/me'); if (!me.is_admin) { byId('denied').hidden = false; return; } csrf = me.csrf; byId('dashboard').hidden = false; await loadUsers(); } catch (_) { byId('login').hidden = false; } }
byId('key-form').addEventListener('submit', async (event) => { event.preventDefault(); try { const r = await postAdmin('/api/admin/keys/generate', { days: Number(byId('key-days').value) }); byId('generated-key').textContent = r.key; byId('key-result').hidden = false; showStatus(`Key de ${r.days} días generada. Cópiala y guárdala; no se volverá a mostrar.`); } catch (e) { showStatus(e.message, true); } });
byId('copy-key').addEventListener('click', async () => { try { await navigator.clipboard.writeText(byId('generated-key').textContent); showStatus('Key copiada.'); } catch { showStatus('No se pudo copiar automáticamente.', true); } });
byId('user-search').addEventListener('input', renderUsers);
byId('permanent').addEventListener('change', (event) => { byId('grant-days').disabled = event.target.checked; });
byId('grant-form').addEventListener('submit', async (event) => { event.preventDefault(); try { const r = await postAdmin('/api/admin/grant', { user_id: byId('user-select').value, permanent: byId('permanent').checked, days: Number(byId('grant-days').value) }); showStatus(r.message); await loadUsers(); } catch (e) { showStatus(e.message, true); } });
byId('revoke-user').addEventListener('click', async () => { const id = byId('user-select').value; if (!id) return showStatus('Selecciona primero una cuenta registrada.', true); if (!confirm('¿Seguro que quieres quitar el Premium de esta cuenta?')) return; try { const r = await postAdmin('/api/admin/revoke', { user_id: id }); showStatus(r.message); await loadUsers(); } catch (e) { showStatus(e.message, true); } });
byId('revoke-key-form').addEventListener('submit', async (event) => { event.preventDefault(); const key = byId('revoke-key').value.trim(); if (!key) return showStatus('Introduce la key que quieres revocar.', true); if (!confirm('Se eliminará esta key y, si ya fue canjeada, se quitará el acceso que concedió. ¿Continuar?')) return; try { const r = await postAdmin('/api/admin/keys/revoke', { key }); showStatus(r.message); byId('revoke-key').value = ''; await loadUsers(); } catch (e) { showStatus(e.message, true); } });
byId('refresh').addEventListener('click', () => loadUsers().then(() => showStatus('Lista actualizada.')).catch((e) => showStatus(e.message, true)));
init();
