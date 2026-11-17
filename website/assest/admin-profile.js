(() => {
  const form = document.getElementById('guild-profile-form');
  if (!form) return;

  const $ = (id) => document.getElementById(id);
  const select = $('guild-select');
  const nickname = $('bot-nickname');
  const fileInput = $('bot-avatar');
  const preview = $('avatar-preview');
  const status = $('guild-profile-status');
  const saveButton = $('save-guild-profile');
  let csrf = '';

  const showStatus = (text, error = false) => {
    status.textContent = text;
    status.classList.toggle('error', error);
    status.classList.toggle('success', !error);
  };
  const api = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.message || `Error HTTP ${response.status}`);
    return data;
  };
  const readImage = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('No se pudo leer la imagen.'));
    reader.readAsDataURL(file);
  });

  const loadGuilds = async () => {
    try {
      const session = await api('/api/me');
      if (!session.authenticated || !session.is_admin) {
        select.replaceChildren(new Option('Inicia sesión como administrador', ''));
        showStatus('Inicia sesión con una cuenta administradora para editar el perfil del bot.', true);
        return;
      }
      csrf = session.csrf || '';
      const result = await api('/api/settings/guilds');
      select.replaceChildren(new Option(result.guilds.length ? 'Selecciona un servidor' : 'No hay servidores elegibles', ''));
      result.guilds.forEach((guild) => select.add(new Option(guild.name, guild.id)));
      if (result.guilds.length) showStatus('Elige el servidor y personaliza el apodo o la imagen del bot.');
      else showStatus('No hay servidores que administres donde Vantarmor esté conectado.', true);
    } catch (error) {
      select.replaceChildren(new Option('No se pudieron cargar servidores', ''));
      showStatus(error.message === 'Error HTTP 401' ? 'Tu sesión expiró. Vuelve a iniciar sesión.' : error.message, true);
    }
  };

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file) {
      preview.hidden = true;
      preview.removeAttribute('src');
      return;
    }
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type) || file.size > 2 * 1024 * 1024) {
      fileInput.value = '';
      preview.hidden = true;
      showStatus('Selecciona PNG, JPG, WEBP o GIF de máximo 2 MB.', true);
      return;
    }
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!csrf) return showStatus('Inicia sesión como administrador para guardar cambios.', true);
    if (!select.value) return showStatus('Selecciona un servidor primero.', true);
    saveButton.disabled = true;
    showStatus('Guardando cambios…');
    try {
      const file = fileInput.files?.[0];
      const avatar = file ? await readImage(file) : '';
      const result = await api('/api/settings/guild-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ guild_id: select.value, nickname: nickname.value.trim(), avatar_url: avatar }),
      });
      showStatus(`${result.message} El cambio solo afecta este servidor.`);
      fileInput.value = '';
      preview.hidden = true;
      preview.removeAttribute('src');
    } catch (error) {
      showStatus(error.message, true);
    } finally {
      saveButton.disabled = false;
    }
  });

  loadGuilds();
})();
