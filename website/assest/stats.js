(() => {
  const refresh = async () => {
    try {
      const response = await fetch('/api/stats', { headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const stats = await response.json();
      const section = document.getElementById('estado');
      if (!section) return;
      const labels = [...section.querySelectorAll('.stats article')];
      for (const card of labels) {
        const label = card.querySelector('span')?.textContent?.trim().toLowerCase() || '';
        const value = card.querySelector('strong');
        if (!value) continue;
        if (label.includes('estado')) {
          value.textContent = stats.bot_online ? '● Operativo' : '● Sin conexión';
          value.classList.toggle('online', !!stats.bot_online);
        } else if (label.includes('servidor')) value.textContent = String(stats.servers ?? 0);
        else if (label.includes('comando')) value.textContent = String(stats.slash_commands ?? 0);
        else if (label.includes('usuario')) value.textContent = String(stats.website_users ?? 0);
      }
    } catch (_) {
      // The public page remains usable if the optional stats endpoint is unavailable.
    }
  };
  refresh();
  window.setInterval(refresh, 60000);
})();
