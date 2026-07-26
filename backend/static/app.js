const PLATFORM = window.APP_PLATFORM || 'gog';
const state = { status: 'all', q: '', sort: 'title', games: [], activeId: null };

const PRESET_CASE_COLORS = [
  '#a85a5a', '#d4823c', '#c9a227', '#5aa968',
  '#4a9aa0', '#2f8fd4', '#5a6fd4', '#9163d6', '#c9629c', '#8a8a8a', '#1a1a1a',
];

function hexToHsl(hex) {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      default: h = (r - g) / d + 4;
    }
    h /= 6;
  }
  return [h * 360, s * 100, l * 100];
}

function hslToHex(h, s, l) {
  s /= 100; l /= 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;
  let r, g, b;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  const toHex = v => Math.round((v + m) * 255).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function caseShades(hex) {
  // Flat - no highlight/shadow gradient, just the exact picked/detected
  // color on every part of the case.
  return { c1: hex, c2: hex, c3: hex, c4: hex };
}

function caseColorFor(g) {
  return g.case_color_override || g.case_color || '#2f8fd4';
}

function pickColorFromCoverClick(e) {
  const img = e.target;
  const rect = img.getBoundingClientRect();
  const x = Math.min(
    img.naturalWidth - 1,
    Math.max(0, Math.floor((e.clientX - rect.left) * (img.naturalWidth / rect.width)))
  );
  const y = Math.min(
    img.naturalHeight - 1,
    Math.max(0, Math.floor((e.clientY - rect.top) * (img.naturalHeight / rect.height)))
  );
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  let pixel;
  try {
    pixel = ctx.getImageData(x, y, 1, 1).data;
  } catch (err) {
    return;
  }
  const hex = '#' + [pixel[0], pixel[1], pixel[2]].map(v => v.toString(16).padStart(2, '0')).join('');
  document.querySelectorAll('#colorPicker .color-swatch').forEach(b => b.classList.remove('active'));
  const customInput = document.getElementById('f-custom-color');
  if (customInput) customInput.value = hex;
  saveField('case_color_override', hex);
}

async function fetchGames() {
  const params = new URLSearchParams({ platform: PLATFORM, status: state.status, q: state.q, sort: state.sort });
  const res = await fetch('/api/games?' + params.toString());
  state.games = await res.json();
  render();
}

async function fetchStats() {
  const res = await fetch('/api/stats?platform=' + encodeURIComponent(PLATFORM));
  const s = await res.json();
  document.getElementById('stats').innerHTML =
    `<span><b>${s.total_games}</b> games</span><span><b>${s.total_size_human}</b> total</span>`;

  const bar = document.getElementById('summaryBar');
  if (bar) {
    if (PLATFORM === 'gog') {
      bar.innerHTML = `
        <span class="stat-ok">🆔 <b>${s.ids_verified}</b> GOG IDs verified</span>
        <span class="stat-ok">📁 <b>${s.folders_linked}</b> folders linked</span>
        <span class="stat-bad">⚠️ <b>${s.folders_missing}</b> folders missing</span>
      `;
    } else if (PLATFORM === 'steam') {
      bar.innerHTML = `
        <span class="stat-ok">📁 <b>${s.folders_linked}</b> folders linked</span>
        <span class="stat-bad">⚠️ <b>${s.folders_missing}</b> folders missing</span>
      `;
    } else {
      bar.innerHTML = '';
    }
  }
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str ?? '';
  return d.innerHTML;
}

function starString(rating) {
  if (!rating) return '';
  const filled = Math.round(rating / 2);
  return '★'.repeat(filled) + '☆'.repeat(5 - filled);
}

function coverUrl(g) {
  if (!g.cover_url) return '';
  return g.cover_url + '?t=' + encodeURIComponent(g.updated_at || '');
}

function heroUrl(g) {
  if (!g.hero_url) return '';
  return g.hero_url + '?t=' + encodeURIComponent(g.updated_at || '');
}

function statusDotInfo(g) {
  const folderOk = !!(g.folder_path && g.folder_path.trim());
  let buildOutdated = false;
  if (g.gog_id && g.latest_build && /^\d+$/.test(g.gog_id) && /^\d+$/.test(String(g.latest_build))) {
    buildOutdated = parseInt(g.gog_id, 10) < parseInt(g.latest_build, 10);
  }
  if (folderOk && !buildOutdated) return { cls: 'dot-green', title: 'Up to date - folder linked' };
  if (folderOk && buildOutdated) return { cls: 'dot-red', title: `Build outdated (installed ${g.gog_id}, latest ${g.latest_build})` };
  if (!folderOk && !buildOutdated) return { cls: 'dot-yellow', title: 'No folder linked' };
  return { cls: 'dot-purple', title: `No folder linked and build outdated (installed ${g.gog_id}, latest ${g.latest_build})` };
}

function idLineText(g) {
  if (g.platform !== 'gog') return g.platform === 'steam' ? `Steam backup · ${g.size_human}` : g.size_human;
  const parts = [];
  parts.push(g.gog_id ? `Build ${escapeHtml(g.gog_id)}` : 'no build version detected');
  parts.push(g.gog_catalog_id ? `GOG ID ${escapeHtml(g.gog_catalog_id)}` : 'GOG ID not verified');
  parts.push(g.size_human);
  return parts.join(' · ');
}

function render() {
  const grid = document.getElementById('grid');
  const empty = document.getElementById('emptyMsg');
  if (state.games.length === 0) {
    grid.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';
  grid.innerHTML = state.games.map(g => {
    const dot = statusDotInfo(g);
    const shades = caseShades(caseColorFor(g));
    const caseVars = `--case-c1:${shades.c1};--case-c2:${shades.c2};--case-c3:${shades.c3};--case-c4:${shades.c4};`;
    return `
    <div class="card" onclick="openModal(${g.id})">
      <div class="cover" style="${caseVars}">
        <div class="cover-art" ${g.cover_url ? `style="background-image:url('${escapeHtml(coverUrl(g))}')"` : ''}></div>
      </div>
      <div class="card-body">
        <div class="card-title" title="${escapeHtml(g.title)}"><span class="status-dot ${dot.cls}" title="${escapeHtml(dot.title)}"></span>${(g.platform === 'gog' || g.platform === 'steam') && !g.folder_path ? `<span class="folder-missing" title="No folder linked">⚠️</span>` : ''}${escapeHtml(g.title)}${g.release_date ? ` <span class="release-year">(${escapeHtml(g.release_date)})</span>` : ''}</div>
        ${g.platform === 'gog' && g.gog_id ? `<div class="card-build" title="Build version">Build ${escapeHtml(g.gog_id)}</div>` : ''}
        <div class="card-meta">
          <span>${g.size_human}</span>
          ${g.rating ? `<span class="stars">${starString(g.rating)}</span>` : ''}
        </div>
        <div><span class="status-pill ${g.status}">${g.status}</span></div>
      </div>
    </div>
  `;
  }).join('');
}

function openModal(idOrGame) {
  const g = typeof idOrGame === 'object' ? idOrGame : state.games.find(x => x.id === idOrGame);
  if (!g) return;
  state.activeId = g.id;
  const modal = document.getElementById('modal');
  modal.innerHTML = `
    ${g.hero_url ? `<div id="f-hero-banner" class="hero-banner" style="background-image:url('${escapeHtml(heroUrl(g))}')"></div>` : '<div id="f-hero-banner"></div>'}

    <h2>${escapeHtml(g.title)}${g.release_date ? ` <span class="release-year">(${escapeHtml(g.release_date)})</span>` : ''}</h2>
    <div class="id-line">${idLineText(g)}</div>

    ${g.cover_url ? `<img id="f-cover-preview" src="${escapeHtml(coverUrl(g))}" style="width:110px;border-radius:6px;margin-bottom:16px;display:block;cursor:crosshair;" title="Click anywhere on this image to use that color for the case">` : '<div id="f-cover-preview"></div>'}

    <div class="field">
      <label>Case Color <span style="opacity:0.6">(click anywhere on the cover art above to use that color, or pick one below - "A" uses the color detected from the cover art)</span></label>
      <div class="color-picker" id="colorPicker">
        <button type="button" class="color-swatch auto-swatch ${!g.case_color_override ? 'active' : ''}" data-color="" style="background:${g.case_color || '#2f8fd4'}" title="Auto (detected from cover art)">A</button>
        ${PRESET_CASE_COLORS.map(c => `<button type="button" class="color-swatch ${g.case_color_override === c ? 'active' : ''}" data-color="${c}" style="background:${c}" title="${c}"></button>`).join('')}
        <input type="color" class="color-swatch-custom" id="f-custom-color" value="${g.case_color_override || g.case_color || '#2f8fd4'}" title="Custom color">
      </div>
    </div>

    <div class="field">
      <label>Title <span style="opacity:0.6">(or paste a SteamGridDB game URL to fix cover art)</span></label>
      <input type="text" id="f-title" value="${escapeHtml(g.title)}">
    </div>

    ${g.platform === 'gog' ? `
    <div class="field">
      <label>Build Version <span style="opacity:0.6">(your own folder-derived reference number)</span></label>
      <input type="text" id="f-gogid" value="${escapeHtml(g.gog_id || '')}">
    </div>
    ` : ''}

    <div class="field">
      <label>Folder Path <span style="opacity:0.6">(size is calculated from this automatically)</span></label>
      <div style="display:flex; gap:8px;">
        <input type="text" id="f-folderpath" style="flex:1;" value="${escapeHtml(g.folder_path || '')}" placeholder="e.g. E:\\Games\\Aragami 2">
        <button type="button" class="close-btn" id="openFolderBtn" ${g.folder_path ? '' : 'disabled'} title="${g.folder_path ? 'Open this folder' : 'No folder linked'}">Open Folder</button>
      </div>
    </div>

    <div class="field">
      <label>Size ${g.folder_path ? '<span style="opacity:0.6">(auto-calculated from Folder Path)</span>' : '<span style="opacity:0.6">(e.g. 25G, 500M, 1.5T)</span>'}</label>
      <input type="text" id="f-size" value="${escapeHtml(g.size_human)}" ${g.folder_path ? 'readonly' : ''}>
    </div>

    ${g.platform === 'gog' || g.platform === 'steam' ? `
    <div class="field">
      <label>Executable Path <span style="opacity:0.6">(lets the Play button launch the game)</span></label>
      <div style="display:flex; gap:8px;">
        <input type="text" id="f-exepath" style="flex:1;" value="${escapeHtml(g.exe_path || '')}" placeholder="e.g. E:\\Games\\Aragami 2\\Aragami2.exe">
        <button type="button" class="close-btn" id="playBtn" ${g.exe_path ? '' : 'disabled'} title="${g.exe_path ? 'Launch this game' : 'No executable set'}">▶ Play</button>
      </div>
    </div>
    ` : ''}

    <div class="field">
      <label>Status</label>
      <select id="f-status">
        ${['backlog','playing','completed','abandoned'].map(s =>
          `<option value="${s}" ${g.status===s?'selected':''}>${s[0].toUpperCase()+s.slice(1)}</option>`).join('')}
      </select>
    </div>

    <div class="field">
      <label>Rating</label>
      <div class="rating-row" id="f-rating" data-value="${g.rating || 0}">
        ${[2,4,6,8,10].map(v => `<button data-v="${v}" class="${g.rating >= v ? 'filled':''}">★</button>`).join('')}
      </div>
    </div>

    <div class="field">
      <label>Tags <span style="opacity:0.6">(comma-separated)</span></label>
      <input type="text" id="f-tags" value="${escapeHtml(g.tags || '')}" placeholder="rpg, coop, favorite...">
    </div>

    <div class="field">
      <label>Notes</label>
      <textarea id="f-notes" placeholder="Any notes...">${escapeHtml(g.notes || '')}</textarea>
    </div>

    ${g.platform === 'gog' && (g.developer || g.genres) ? `
    <div class="field">
      ${g.developer ? `<div class="save-hint" style="margin-bottom:6px;">${escapeHtml(g.developer)}</div>` : ''}
      ${g.genres ? `<div class="genre-pills">${g.genres.split(',').map(t => `<span class="genre-pill">${escapeHtml(t.trim())}</span>`).join('')}</div>` : ''}
    </div>
    ` : ''}

    ${g.platform === 'gog' && g.description ? `
    <div class="field">
      <label>Story</label>
      <p class="story-text">${escapeHtml(g.description)}</p>
    </div>
    ` : ''}

    ${g.platform === 'gog' ? `
    <div class="field" id="screenshotsBlock" style="display:none;">
      <label>Screenshots</label>
      <div class="screenshot-grid" id="screenshotGrid"></div>
    </div>
    ` : ''}

    <div class="modal-actions">
      <div style="display:flex; gap:10px;">
        <button class="close-btn" onclick="closeModal()">Done</button>
        <button class="delete-btn" id="deleteBtn">Delete</button>
      </div>
      <span class="save-hint" id="saveHint"></span>
    </div>
  `;

  document.querySelectorAll('#f-rating button').forEach(btn => {
    btn.addEventListener('click', () => {
      const v = parseInt(btn.dataset.v);
      const current = parseInt(document.getElementById('f-rating').dataset.value);
      const newVal = current === v ? 0 : v;
      document.getElementById('f-rating').dataset.value = newVal;
      document.querySelectorAll('#f-rating button').forEach(b => {
        b.classList.toggle('filled', parseInt(b.dataset.v) <= newVal);
      });
      saveField('rating', newVal || null);
    });
  });

  document.querySelectorAll('#colorPicker .color-swatch').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#colorPicker .color-swatch').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      saveField('case_color_override', btn.dataset.color || null);
    });
  });
  document.getElementById('f-custom-color').addEventListener('change', e => {
    document.querySelectorAll('#colorPicker .color-swatch').forEach(b => b.classList.remove('active'));
    saveField('case_color_override', e.target.value);
  });
  const coverPreviewImg = document.getElementById('f-cover-preview');
  if (coverPreviewImg && coverPreviewImg.tagName === 'IMG') {
    coverPreviewImg.addEventListener('click', pickColorFromCoverClick);
  }

  document.getElementById('f-title').addEventListener('blur', e => {
    const val = e.target.value.trim();
    if (val && val !== g.title) saveField('title', val, 'looking up cover art…');
  });
  document.getElementById('f-size').addEventListener('blur', e => {
    const val = e.target.value.trim();
    if (val && val !== g.size_human) saveField('size_human', val);
  });
  const gogIdInput = document.getElementById('f-gogid');
  if (gogIdInput) {
    gogIdInput.addEventListener('blur', e => {
      const val = e.target.value.trim();
      if (val !== (g.gog_id || '')) saveField('gog_id', val);
    });
  }
  document.getElementById('f-folderpath').addEventListener('blur', e => {
    const val = e.target.value.trim();
    if (val !== (g.folder_path || '')) saveField('folder_path', val, 'calculating folder size…');
  });
  document.getElementById('openFolderBtn').addEventListener('click', async () => {
    const hint = document.getElementById('saveHint');
    const res = await fetch(`/api/games/${state.activeId}/open_folder`, { method: 'POST' });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      hint.textContent = data.error || 'error opening folder';
    }
  });
  const exePathInput = document.getElementById('f-exepath');
  if (exePathInput) {
    exePathInput.addEventListener('blur', e => {
      const val = e.target.value.trim();
      if (val !== (g.exe_path || '')) saveField('exe_path', val);
    });
  }
  const playBtn = document.getElementById('playBtn');
  if (playBtn) {
    playBtn.addEventListener('click', async () => {
      const hint = document.getElementById('saveHint');
      const res = await fetch(`/api/games/${state.activeId}/play`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        hint.textContent = data.error || 'error launching game';
      } else {
        hint.textContent = 'launched ✓';
      }
    });
  }
  document.getElementById('deleteBtn').addEventListener('click', function() {
    if (this.dataset.armed === '1') {
      deleteGame(g.id);
    } else {
      this.dataset.armed = '1';
      this.textContent = 'Confirm delete?';
      this.classList.add('armed');
    }
  });

  document.getElementById('f-status').addEventListener('change', e => saveField('status', e.target.value));
  document.getElementById('f-tags').addEventListener('blur', e => saveField('tags', e.target.value));
  document.getElementById('f-notes').addEventListener('blur', e => saveField('notes', e.target.value));

  document.getElementById('overlay').classList.add('open');

  if (g.platform === 'gog') loadScreenshots(g.id);
}

async function loadScreenshots(gameId) {
  const shots = await fetch(`/api/games/${gameId}/screenshots`).then(r => r.json());
  if (shots.length === 0) return;
  const block = document.getElementById('screenshotsBlock');
  const grid = document.getElementById('screenshotGrid');
  if (!block || !grid) return; // modal moved on before this resolved
  grid.innerHTML = shots.map(url => `
    <a href="${escapeHtml(url)}" target="_blank" rel="noopener">
      <img src="${escapeHtml(url)}" loading="lazy" alt="Screenshot">
    </a>
  `).join('');
  block.style.display = '';
}

async function saveField(field, value, savingMessage) {
  const hint = document.getElementById('saveHint');
  hint.textContent = savingMessage || 'saving…';
  const res = await fetch(`/api/games/${state.activeId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ [field]: value })
  });
  if (res.ok) {
    const updated = await res.json();
    const idx = state.games.findIndex(g => g.id === state.activeId);
    // mutate in place (not state.games[idx] = updated) so the `g` closure
    // captured by openModal's field listeners stays live - otherwise a
    // second edit to the same field in one modal session compares against
    // a stale pre-save value and can silently no-op.
    if (idx >= 0) Object.assign(state.games[idx], updated);
    hint.textContent = 'saved ✓';
    render();
    if (field === 'title') {
      const h2 = document.querySelector('#modal h2');
      if (h2) h2.textContent = updated.title;
      const preview = document.getElementById('f-cover-preview');
      if (preview && updated.cover_url) {
        if (preview.tagName === 'IMG') {
          preview.src = coverUrl(updated);
        } else {
          preview.outerHTML = `<img id="f-cover-preview" src="${escapeHtml(coverUrl(updated))}" style="width:110px;border-radius:6px;margin-bottom:16px;display:block;">`;
        }
      }
      const hero = document.getElementById('f-hero-banner');
      if (hero && updated.hero_url) {
        hero.classList.add('hero-banner');
        hero.style.backgroundImage = `url('${heroUrl(updated)}')`;
      }
    }
    if (field === 'title' || field === 'gog_id') {
      const idLine = document.querySelector('#modal .id-line');
      if (idLine) idLine.textContent = idLineText(updated);
    }
    if (field === 'folder_path') {
      const sizeField = document.getElementById('f-size');
      if (sizeField) {
        sizeField.value = updated.size_human;
        sizeField.toggleAttribute('readonly', !!updated.folder_path);
      }
      const sizeLabel = document.querySelector('label[for=""]') || sizeField?.previousElementSibling;
      if (sizeLabel) {
        sizeLabel.innerHTML = updated.folder_path
          ? 'Size <span style="opacity:0.6">(auto-calculated from Folder Path)</span>'
          : 'Size <span style="opacity:0.6">(e.g. 25G, 500M, 1.5T)</span>';
      }
      const openBtn = document.getElementById('openFolderBtn');
      if (openBtn) {
        openBtn.disabled = !updated.folder_path;
        openBtn.title = updated.folder_path ? 'Open this folder' : 'No folder linked';
      }
    }
    if (field === 'exe_path') {
      const playBtn = document.getElementById('playBtn');
      if (playBtn) {
        playBtn.disabled = !updated.exe_path;
        playBtn.title = updated.exe_path ? 'Launch this game' : 'No executable set';
      }
      const statusSelect = document.getElementById('f-status');
      if (statusSelect) statusSelect.value = updated.status;
    }
  } else {
    hint.textContent = 'error saving';
  }
}

function closeModal() {
  document.getElementById('overlay').classList.remove('open');
  fetchStats();
}

async function deleteGame(id) {
  const hint = document.getElementById('saveHint');
  hint.textContent = 'deleting…';
  const res = await fetch(`/api/games/${id}`, { method: 'DELETE' });
  if (res.ok) {
    state.games = state.games.filter(g => g.id !== id);
    document.getElementById('overlay').classList.remove('open');
    render();
    fetchStats();
  } else {
    hint.textContent = 'error deleting';
  }
}

function openAddModal() {
  state.activeId = null;
  const modal = document.getElementById('modal');
  modal.innerHTML = `
    <h2>Add Game</h2>
    <div class="field">
      <label>Title <span style="opacity:0.6">(or paste a SteamGridDB game URL)</span></label>
      <input type="text" id="new-title" placeholder="Game title, or https://www.steamgriddb.com/game/...">
    </div>
    <div class="modal-actions">
      <button class="close-btn" onclick="closeModal()">Cancel</button>
      <button class="close-btn" id="addBtn">Add</button>
    </div>
    <div class="save-hint" id="saveHint" style="margin-top:10px;"></div>
  `;
  document.getElementById('addBtn').addEventListener('click', submitAddGame);
  document.getElementById('new-title').addEventListener('keydown', e => {
    if (e.key === 'Enter') submitAddGame();
  });
  document.getElementById('overlay').classList.add('open');
  document.getElementById('new-title').focus();
}

async function submitAddGame() {
  const input = document.getElementById('new-title');
  const title = input.value.trim();
  if (!title) return;
  const hint = document.getElementById('saveHint');
  hint.textContent = 'adding & looking up cover art…';
  const res = await fetch('/api/games', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, platform: PLATFORM })
  });
  if (res.ok) {
    document.getElementById('overlay').classList.remove('open');
    await fetchGames();
    await fetchStats();
  } else {
    hint.textContent = 'error adding game';
  }
}

async function openTrashModal() {
  state.activeId = null;
  const modal = document.getElementById('modal');
  modal.innerHTML = `
    <h2>Trash</h2>
    <div class="save-hint" style="margin-bottom:14px;">Deleted games are kept here until the 50 most recent - restoring brings back all its data and art.</div>
    <div id="trashList"></div>
    <div class="modal-actions">
      <button class="close-btn" onclick="closeModal()">Close</button>
    </div>
  `;
  document.getElementById('overlay').classList.add('open');

  const list = document.getElementById('trashList');
  list.innerHTML = '<div class="save-hint">loading…</div>';
  const deleted = await fetch('/api/deleted_games').then(r => r.json());
  const relevant = deleted.filter(g => g.platform === PLATFORM);
  if (relevant.length === 0) {
    list.innerHTML = '<div class="save-hint">Nothing deleted on this shelf yet.</div>';
    return;
  }
  list.innerHTML = relevant.map(g => `
    <div class="field" style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
      <div style="min-width:0;">
        <div style="font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(g.title)}</div>
        <div class="save-hint">${g.size_human} · deleted ${escapeHtml((g.deleted_at || '').split(' ')[0] || '')}</div>
      </div>
      <button class="close-btn" data-restore="${g.id}">Restore</button>
    </div>
  `).join('');
  list.querySelectorAll('[data-restore]').forEach(btn => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Restoring…';
      const res = await fetch(`/api/deleted_games/${btn.dataset.restore}/restore`, { method: 'POST' });
      if (res.ok) {
        await fetchGames();
        await fetchStats();
        openTrashModal();
      } else {
        btn.disabled = false;
        btn.textContent = 'Restore';
      }
    });
  });
}

document.getElementById('addGameBtn').addEventListener('click', openAddModal);
document.getElementById('trashBtn').addEventListener('click', openTrashModal);

// ==================== Search all shelves ====================
// A series like "assassin" or "batman" spans multiple platforms, so this
// searches /api/games with platform=all (already supported server-side)
// instead of the per-shelf search box, and lets you open/edit a result
// in place without leaving the current shelf.
const PLATFORM_LABEL = { gog: 'GOG', steam: 'Steam', ps3: 'PS3', ps4: 'PS4' };

function openSearchAllModal() {
  state.activeId = null;
  const modal = document.getElementById('modal');
  modal.innerHTML = `
    <h2>Search All Shelves</h2>
    <div class="field">
      <input type="text" id="searchAllInput" placeholder="e.g. assassin, batman, crash..." autocomplete="off">
    </div>
    <div id="searchAllResults"></div>
    <div class="modal-actions">
      <button class="close-btn" onclick="closeModal()">Close</button>
    </div>
  `;
  document.getElementById('overlay').classList.add('open');
  document.getElementById('searchAllResults').innerHTML =
    '<div class="save-hint">Type a series or title - matches across every shelf.</div>';

  const input = document.getElementById('searchAllInput');
  input.focus();
  let debounceTimer;
  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => runSearchAll(input.value.trim()), 200);
  });
}

async function runSearchAll(q) {
  const results = document.getElementById('searchAllResults');
  if (!results) return; // modal was closed while the debounce was pending
  if (!q) {
    results.innerHTML = '<div class="save-hint">Type a series or title - matches across every shelf.</div>';
    return;
  }
  results.innerHTML = '<div class="save-hint">searching…</div>';
  const params = new URLSearchParams({ platform: 'all', status: 'all', q, sort: 'title' });
  const games = await fetch('/api/games?' + params.toString()).then(r => r.json());
  if (!document.getElementById('searchAllResults')) return; // modal closed while awaiting
  if (games.length === 0) {
    results.innerHTML = '<div class="save-hint">No matches.</div>';
    return;
  }
  results.innerHTML = games.map(g => `
    <div class="search-result-row" data-open="${g.id}">
      <div class="search-result-cover" ${g.cover_url ? `style="background-image:url('${escapeHtml(coverUrl(g))}')"` : ''}></div>
      <div style="min-width:0; flex:1;">
        <div class="search-result-title">${escapeHtml(g.title)}</div>
        <div class="save-hint">${PLATFORM_LABEL[g.platform] || g.platform} · ${g.size_human}</div>
      </div>
      <span class="status-pill ${g.status}">${g.status}</span>
    </div>
  `).join('');
  results.querySelectorAll('[data-open]').forEach(row => {
    row.addEventListener('click', () => {
      const g = games.find(x => x.id === parseInt(row.dataset.open));
      if (g) openModal(g);
    });
  });
}

if (document.getElementById('searchAllBtn')) {
  document.getElementById('searchAllBtn').addEventListener('click', openSearchAllModal);
}

// ==================== Big Picture mode ====================
// A console-style carousel: scroll through covers with arrow keys or a
// connected gamepad's d-pad/stick, the focused game zooms in and shows a
// Play prompt. Gamepad state has to be polled every frame (there's no
// "gamepadmoved" event), so this only runs while the overlay is open.
const bp = { games: [], allGames: [], filter: 'all', index: 0, gamepadLoop: null, stickWasNeutral: true, cardStep: 192, backdropFront: 'A' };

function bpApplyFilter() {
  bp.games = bp.filter === 'all' ? bp.allGames
    : bp.filter === 'installed' ? bp.allGames.filter(g => !!g.folder_path)
    : bp.allGames.filter(g => g.status === bp.filter);
  bp.index = 0;
  renderBigPictureStage();
}

function bpCardHtml(g, i) {
  const cover = g.cover_url ? `background-image:url('${escapeHtml(coverUrl(g))}');` : '';
  const borderColor = caseColorFor(g);
  const d = i - bp.index;
  let extra = '';
  if (d !== 0) {
    const angle = Math.max(-40, Math.min(40, -d * 10));
    const z = -Math.min(Math.abs(d), 6) * 18;
    const scale = Math.max(0.66, 0.8 - Math.abs(d) * 0.02);
    extra = `transform: scale(${scale}) rotateY(${angle}deg) translateZ(${z}px);`;
  }
  return `<div class="bp-card ${i === bp.index ? 'focused' : ''}" style="${cover}border:4px solid ${borderColor};${extra}" data-i="${i}"></div>`;
}

function bpUpdateBackdrop(g) {
  // Crossfade between two stacked layers: paint the hidden one with the
  // new image first, then swap which layer is visible so the transition
  // opacity actually animates instead of snapping.
  const img = g && (g.hero_url ? heroUrl(g) : (g.cover_url ? coverUrl(g) : null));
  const front = document.getElementById(bp.backdropFront === 'A' ? 'bpBackdropA' : 'bpBackdropB');
  const back = document.getElementById(bp.backdropFront === 'A' ? 'bpBackdropB' : 'bpBackdropA');
  if (img) {
    back.style.backgroundImage = `url('${img}')`;
    back.classList.add('visible');
  } else {
    back.classList.remove('visible');
  }
  front.classList.remove('visible');
  bp.backdropFront = bp.backdropFront === 'A' ? 'B' : 'A';
}

function renderBigPictureStage() {
  const stage = document.getElementById('bpStage');
  stage.innerHTML = bp.games.map((g, i) => bpCardHtml(g, i)).join('');
  stage.style.transform = `translateX(${-bp.index * bp.cardStep}px)`;
  stage.querySelectorAll('.bp-card').forEach(card => {
    card.addEventListener('click', () => {
      const i = parseInt(card.dataset.i);
      if (i === bp.index) openBpDetail();
      else bpMove(i - bp.index);
    });
  });

  const g = bp.games[bp.index];
  bpUpdateBackdrop(g);
  // Set hero image as background on stagewrap
  const stagewrap = document.getElementById('bpStage').parentElement;
  if (g && g.hero_url) {
    stagewrap.style.backgroundImage = `url('${escapeHtml(heroUrl(g))}')`;
  } else if (g && g.cover_url) {
    stagewrap.style.backgroundImage = `url('${escapeHtml(coverUrl(g))}')`;
  } else {
    stagewrap.style.backgroundImage = 'none';
  }

  // Add game logo/title overlay on hero background (top-right)
  const bpOverlay = document.getElementById('bpOverlay');
  let logoOverlay = document.getElementById('bpLogoOverlay');
  if (!logoOverlay) {
    logoOverlay = document.createElement('div');
    logoOverlay.id = 'bpLogoOverlay';
    logoOverlay.className = 'bp-logo-overlay';
    bpOverlay.appendChild(logoOverlay);
  }
  if (g) {
    if (g.logo_url) {
      // Display official SteamGridDB logo
      logoOverlay.innerHTML = `<img src="${escapeHtml(g.logo_url)}" alt="${escapeHtml(g.title)} logo" class="bp-logo-image">`;
    } else {
      // Fallback to stylized game title text
      logoOverlay.innerHTML = `<div class="bp-title-overlay-text">${escapeHtml(g.title)}</div>`;
    }
    logoOverlay.style.display = 'flex';
  } else {
    logoOverlay.style.display = 'none';
  }
  const info = document.getElementById('bpInfo');
  if (!g) {
    info.innerHTML = '<div class="save-hint">No games on this shelf yet.</div>';
    return;
  }
  const canPlay = !!g.exe_path;
  const devLine = g.developer ? ` · ${escapeHtml(g.developer)}` : '';
  const genrePills = g.genres
    ? `<div class="bp-genres">${g.genres.split(',').map(t => `<span class="bp-genre-pill">${escapeHtml(t.trim())}</span>`).join('')}</div>`
    : '';
  info.innerHTML = `
    <h2>${escapeHtml(g.title)}${g.release_date ? ` <span class="release-year">(${escapeHtml(g.release_date)})</span>` : ''}</h2>
    <div class="bp-meta">${g.size_human}${g.rating ? ' · ' + starString(g.rating) : ''} · <b>${g.status}</b>${devLine}</div>
    ${genrePills}
    <button class="bp-play-btn" id="bpPlayBtn" ${canPlay ? '' : 'disabled'}>${canPlay ? '▶ Play' : 'No executable set'}</button>
    ${g.platform === 'gog' && g.description ? `<p class="bp-story">${escapeHtml(g.description)}</p>` : ''}
    ${g.platform === 'gog' ? '<div class="bp-shots" id="bpShots"></div>' : ''}
  `;
  document.getElementById('bpPlayBtn').addEventListener('click', bpPlay);
  if (g.platform === 'gog') loadBpScreenshots(g.id);
}

let bpShotsAbort = null;

async function loadBpScreenshots(gameId) {
  // Abort whatever screenshot request is still in flight first - without
  // this, rapidly holding the arrow key/d-pad queues up one fetch per game
  // flown past, and the browser's per-host connection limit makes them
  // resolve one at a time long after you've actually stopped moving, so
  // the game you land on can sit with no thumbnails for many seconds.
  if (bpShotsAbort) bpShotsAbort.abort();
  const controller = new AbortController();
  bpShotsAbort = controller;

  let shots;
  try {
    shots = await fetch(`/api/games/${gameId}/screenshots`, { signal: controller.signal }).then(r => r.json());
  } catch (e) {
    return; // aborted, or a transient network error - just leave the strip empty
  }
  // the focused game may have changed while this was in flight
  if (bp.games[bp.index]?.id !== gameId) return;
  const strip = document.getElementById('bpShots');
  if (!strip || shots.length === 0) return;
  strip.innerHTML = shots.map(url => `<img src="${escapeHtml(url)}" loading="lazy" alt="">`).join('');
}

function bpMove(delta) {
  if (bp.games.length === 0) return;
  bp.index = Math.max(0, Math.min(bp.games.length - 1, bp.index + delta));
  renderBigPictureStage();
}

let bpDetailShotsAbort = null;

function openBpDetail() {
  const g = bp.games[bp.index];
  if (!g) return;
  const canPlay = !!g.exe_path;
  const genrePills = g.genres
    ? g.genres.split(',').map(t => `<span class="genre-pill">${escapeHtml(t.trim())}</span>`).join('')
    : '';
  const ratingPill = g.rating ? `<span class="genre-pill">${starString(g.rating)}</span>` : '';
  document.getElementById('bpDetailInner').innerHTML = `
    <div class="bp-detail-hero">
      ${g.cover_url ? `<img src="${escapeHtml(coverUrl(g))}" alt="${escapeHtml(g.title)} cover">` : ''}
      <div class="bp-detail-title">
        <h2>${escapeHtml(g.title)}${g.release_date ? ` <span class="release-year">(${escapeHtml(g.release_date)})</span>` : ''}</h2>
        <div class="bp-detail-sub">${g.developer ? escapeHtml(g.developer) + ' · ' : ''}${idLineText(g)}</div>
        <div class="bp-detail-chips">${genrePills}${ratingPill}</div>
        <div class="bp-detail-statline">
          <span>Status <b>${g.status}</b></span>
          <span>Size <b>${g.size_human}</b></span>
        </div>
        <button class="bp-play-btn" id="bpDetailPlayBtn" ${canPlay ? '' : 'disabled'}>${canPlay ? '▶ Play' : 'No executable set'}</button>
      </div>
    </div>
    ${g.description ? `
    <div class="bp-detail-section">
      <div class="bp-detail-section-title">Story</div>
      <p class="bp-detail-story">${escapeHtml(g.description)}</p>
    </div>` : ''}
    <div class="bp-detail-section" id="bpDetailShotsSection" style="display:none;">
      <div class="bp-detail-section-title">Screenshots</div>
      <div class="screenshot-grid" id="bpDetailShots"></div>
    </div>
  `;
  const playBtn = document.getElementById('bpDetailPlayBtn');
  if (playBtn) playBtn.addEventListener('click', bpPlay);
  document.getElementById('bpDetail').classList.add('open');
  document.getElementById('bpDetail').scrollTop = 0;
  loadBpDetailScreenshots(g.id);
}

async function loadBpDetailScreenshots(gameId) {
  if (bpDetailShotsAbort) bpDetailShotsAbort.abort();
  const controller = new AbortController();
  bpDetailShotsAbort = controller;

  let shots;
  try {
    shots = await fetch(`/api/games/${gameId}/screenshots`, { signal: controller.signal }).then(r => r.json());
  } catch (e) {
    return;
  }
  if (bp.games[bp.index]?.id !== gameId) return;
  const section = document.getElementById('bpDetailShotsSection');
  const grid = document.getElementById('bpDetailShots');
  if (!section || !grid || shots.length === 0) return;
  grid.innerHTML = shots.map((url, i) => `<img src="${escapeHtml(url)}" loading="lazy" alt="" data-i="${i}">`).join('');
  grid.querySelectorAll('img').forEach(img => {
    img.addEventListener('click', () => openBpLightbox(shots, parseInt(img.dataset.i)));
  });
  section.style.display = '';
}

const bpLightbox = { shots: [], index: 0 };

function openBpLightbox(shots, index) {
  bpLightbox.shots = shots;
  bpLightbox.index = index;
  renderBpLightbox();
  document.getElementById('bpLightbox').classList.add('open');
}

function renderBpLightbox() {
  document.getElementById('bpLightboxImg').src = bpLightbox.shots[bpLightbox.index];
  document.getElementById('bpLightboxCount').textContent = `${bpLightbox.index + 1} / ${bpLightbox.shots.length}`;
}

function bpLightboxNav(delta) {
  const n = bpLightbox.shots.length;
  bpLightbox.index = (bpLightbox.index + delta + n) % n;
  renderBpLightbox();
}

function closeBpLightbox() {
  document.getElementById('bpLightbox').classList.remove('open');
}

function closeBpDetail() {
  document.getElementById('bpDetail').classList.remove('open');
  if (bpDetailShotsAbort) bpDetailShotsAbort.abort();
}

async function bpPlay() {
  const g = bp.games[bp.index];
  if (!g || !g.exe_path) return;
  const btn = document.getElementById('bpPlayBtn');
  btn.textContent = 'Launching…';
  const res = await fetch(`/api/games/${g.id}/play`, { method: 'POST' });
  btn.textContent = res.ok ? '▶ Launched ✓' : 'Error launching';
  if (res.ok) {
    setTimeout(() => { if (bp.games[bp.index]?.id === g.id) btn.textContent = '▶ Play'; }, 1500);
  }
}

function bpKeydown(e) {
  if (document.getElementById('bpLightbox').classList.contains('open')) {
    if (e.key === 'Escape') { e.preventDefault(); closeBpLightbox(); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); bpLightboxNav(-1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); bpLightboxNav(1); }
    return; // detail/carousel navigation is paused while the lightbox is open
  }
  if (document.getElementById('bpDetail').classList.contains('open')) {
    if (e.key === 'Escape') { e.preventDefault(); closeBpDetail(); }
    return; // carousel navigation is paused while the detail view is open
  }
  if (e.key === 'ArrowLeft') { e.preventDefault(); bpMove(-1); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); bpMove(1); }
  else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); bpPlay(); }
  else if (e.key === 'Escape') { e.preventDefault(); closeBigPicture(); }
}

function bpPollGamepad() {
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  const pad = pads && pads[0];
  if (pad) {
    const stickX = pad.axes[0] || 0;
    const dpadLeft = pad.buttons[14] && pad.buttons[14].pressed;
    const dpadRight = pad.buttons[15] && pad.buttons[15].pressed;
    const active = stickX < -0.5 || dpadLeft ? -1 : (stickX > 0.5 || dpadRight ? 1 : 0);
    if (active !== 0 && bp.stickWasNeutral) {
      bpMove(active);
      bp.stickWasNeutral = false;
    } else if (active === 0) {
      bp.stickWasNeutral = true;
    }
    if (pad.buttons[0] && pad.buttons[0].pressed && !bp.aWasPressed) bpPlay();
    bp.aWasPressed = pad.buttons[0] && pad.buttons[0].pressed;
    if (pad.buttons[1] && pad.buttons[1].pressed && !bp.bWasPressed) closeBigPicture();
    bp.bWasPressed = pad.buttons[1] && pad.buttons[1].pressed;
  }
  bp.gamepadLoop = requestAnimationFrame(bpPollGamepad);
}

async function openBigPicture() {
  // Big Picture has its own filter tabs, independent of the main grid's
  // search/status filter, so it always loads the full unfiltered shelf.
  bp.filter = 'all';
  document.querySelectorAll('#bpFilters .tab').forEach(t => t.classList.toggle('active', t.dataset.bpfilter === 'all'));
  const params = new URLSearchParams({ platform: PLATFORM, status: 'all', q: '', sort: 'title' });
  bp.allGames = await fetch('/api/games?' + params.toString()).then(r => r.json());
  document.getElementById('bpOverlay').classList.add('open');
  bpApplyFilter();
  document.addEventListener('keydown', bpKeydown);
  bp.stickWasNeutral = true;
  bpPollGamepad();
}

function closeBigPicture() {
  document.getElementById('bpOverlay').classList.remove('open');
  document.removeEventListener('keydown', bpKeydown);
  if (bp.gamepadLoop) cancelAnimationFrame(bp.gamepadLoop);
  if (bpShotsAbort) bpShotsAbort.abort();
  closeBpLightbox();
  closeBpDetail();
  document.getElementById('bpBackdropA').classList.remove('visible');
  document.getElementById('bpBackdropB').classList.remove('visible');
  bp.backdropFront = 'A';
}

if (document.getElementById('bigPictureBtn')) {
  document.getElementById('bigPictureBtn').addEventListener('click', openBigPicture);
  document.getElementById('bpExitBtn').addEventListener('click', closeBigPicture);
  document.getElementById('bpPrevBtn').addEventListener('click', () => bpMove(-1));
  document.getElementById('bpNextBtn').addEventListener('click', () => bpMove(1));
  document.getElementById('bpOverlay').addEventListener('click', e => {
    if (e.target.id === 'bpOverlay') closeBigPicture();
  });
  document.querySelectorAll('#bpFilters .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#bpFilters .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      bp.filter = tab.dataset.bpfilter;
      bpApplyFilter();
    });
  });
  document.getElementById('bpDetailClose').addEventListener('click', closeBpDetail);
  document.getElementById('bpLightboxClose').addEventListener('click', closeBpLightbox);
  document.getElementById('bpLightboxPrev').addEventListener('click', () => bpLightboxNav(-1));
  document.getElementById('bpLightboxNext').addEventListener('click', () => bpLightboxNav(1));
  document.getElementById('bpLightbox').addEventListener('click', e => {
    if (e.target.id === 'bpLightbox') closeBpLightbox();
  });
}

document.getElementById('overlay').addEventListener('click', e => {
  if (e.target.id === 'overlay') closeModal();
});

document.getElementById('search').addEventListener('input', e => {
  state.q = e.target.value;
  fetchGames();
});

document.getElementById('sort').addEventListener('change', e => {
  state.sort = e.target.value;
  fetchGames();
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    state.status = tab.dataset.status;
    fetchGames();
  });
});

fetchGames();
fetchStats();

// Remove the 3D Museum link and label
(function removeMuseum() {
  document.querySelectorAll('a[href*="/museum"]').forEach(link => {
    console.log('Removing museum link:', link.outerHTML);
    link.remove();
  });
  const label = document.getElementById('bpMuseumLabel');
  if (label) {
    console.log('Removing museum label');
    label.remove();
  }
})();

// Force hide backdrops - remove those light circles
(function hideBackdrops() {
  const style = document.createElement('style');
  style.textContent = `
    #bpBackdropA { display: none !important; }
    #bpBackdropB { display: none !important; }
    .bp-backdrop-scrim { display: none !important; }
  `;
  document.head.appendChild(style);
})();
