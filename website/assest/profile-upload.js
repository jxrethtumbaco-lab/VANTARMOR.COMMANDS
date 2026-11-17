(() => {
  const form = document.getElementById('guild-profile-form');
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  const select = $('guild-profile-select'); const status = $('guild-profile-status'); const fileInput = $('bot-avatar'); const preview = $('avatar-preview'); const saveButton = $('save-guild-profile');
  let csrf = '';
  const setStatus = (message, error = false) => { status.textContent = message; status.classList.toggle('error', error); status.classList.toggle('success', !error); };
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.message || `Error HTTP ${response.status}`);
    return data;
  };
  const load = async () => {
    try {
      const session = await request('/api/me'); csrf = session.csrf || '';
      if (!session.authenticated) { select.replaceChildren(new Option('Inicia sesión primero', '')); return; }
      const data = await request('/api/settings/guilds');
      select.replaceChildren(new Option(data.guilds.length ? 'Selecciona un servidor' : 'Sin servidores disponibles', ''));
      data.guilds.forEach((guild) => select.add(new Option(guild.name, guild.id)));
      if (!data.guilds.length) setStatus('El bot debe estar conectado y necesitas ser administrador del servidor.', true);
    } catch (error) { select.replaceChildren(new Option('No se pudieron cargar servidores', '')); setStatus(error.message, true); }
  };
  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (!file) { preview.hidden = true; preview.removeAttribute('src'); return; }
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type) || file.size > 2 * 1024 * 1024) {
      fileInput.value = ''; preview.hidden = true; setStatus('Usa PNG, JPG, WEBP o GIF de máximo 2 MB.', true); return;
    }
    preview.src = URL.createObjectURL(file); preview.hidden = false;
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!csrf) { setStatus('Inicia sesión para guardar la configuración.', true); return; }
    if (!select.value) { setStatus('Selecciona un servidor válido.', true); return; }
    saveButton.disabled = true; setStatus('Guardando cambios…');
    try {
      let avatar = '';
      const file = fileInput.files[0];
      if (file) avatar = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('No se pudo leer la imagen.')); reader.readAsDataURL(file); });
      const result = await request('/api/settings/guild-profile', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ guild_id: select.value, nickname: $('bot-nickname').value.trim(), avatar_url: avatar }) });
      setStatus(`${result.message} Esta configuración es gratuita.`); fileInput.value = ''; preview.hidden = true; preview.removeAttribute('src');
    } catch (error) { setStatus(error.message, true); }
    finally { saveButton.disabled = false; }
  });
  load();
})();
