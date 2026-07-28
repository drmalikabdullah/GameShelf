function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str ?? '';
  return d.innerHTML;
}

function renderThemeSelection() {
  const activeTheme = window.GameShelfTheme?.get() || 'dark';
  document.querySelectorAll('.theme-option').forEach(option => {
    const active = option.dataset.theme === activeTheme;
    option.classList.toggle('active', active);
    option.setAttribute('aria-pressed', String(active));
  });
}

document.querySelectorAll('.theme-option').forEach(option => {
  option.addEventListener('click', () => {
    const selected = window.GameShelfTheme.set(option.dataset.theme);
    renderThemeSelection();
    const label = option.querySelector('b')?.textContent || selected;
    document.getElementById('themeHint').textContent = `${label} theme applied ✓`;
  });
});

renderThemeSelection();

async function loadKeyStatus() {
  const status = document.getElementById('keyStatus');
  const res = await fetch('/api/settings/steamgriddb_key');
  const data = await res.json();
  if (data.configured) {
    status.innerHTML = `<span class="dash-ok">&#10003; Key configured</span> <span style="opacity:0.6">(${escapeHtml(data.source)})</span>`;
  } else {
    status.innerHTML = '<span class="dash-bad">No key configured</span> - GOG cover art still works, Steam/PS3/PS4 art and better GOG matches need a key.';
  }
}

document.getElementById('toggleKeyVisibility').addEventListener('click', () => {
  const input = document.getElementById('f-key');
  const btn = document.getElementById('toggleKeyVisibility');
  const showing = input.type === 'text';
  input.type = showing ? 'password' : 'text';
  btn.textContent = showing ? 'Show' : 'Hide';
});

document.getElementById('saveKeyBtn').addEventListener('click', async () => {
  const input = document.getElementById('f-key');
  const hint = document.getElementById('keyHint');
  const key = input.value.trim();
  if (!key) {
    hint.textContent = 'paste a key first, or use Clear Key to remove one';
    return;
  }
  hint.textContent = 'saving…';
  const res = await fetch('/api/settings/steamgriddb_key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key }),
  });
  if (res.ok) {
    input.value = '';
    hint.textContent = 'saved ✓';
    loadKeyStatus();
  } else {
    hint.textContent = 'error saving key';
  }
});

document.getElementById('clearKeyBtn').addEventListener('click', async () => {
  const hint = document.getElementById('keyHint');
  hint.textContent = 'clearing…';
  const res = await fetch('/api/settings/steamgriddb_key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: '' }),
  });
  if (res.ok) {
    document.getElementById('f-key').value = '';
    hint.textContent = 'cleared ✓';
    loadKeyStatus();
  } else {
    hint.textContent = 'error clearing key';
  }
});

loadKeyStatus();
