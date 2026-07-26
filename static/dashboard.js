const PLATFORM_LABEL = { gog: 'GOG', steam: 'Steam', ps3: 'PS3', ps4: 'PS4' };
const STATUS_ORDER = ['backlog', 'playing', 'completed', 'abandoned'];

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str ?? '';
  return d.innerHTML;
}

function statusBarHtml(byStatus, total) {
  if (!total) return '<div class="status-bar"></div>';
  const segs = STATUS_ORDER.map(s => {
    const n = byStatus[s] || 0;
    const pct = (n / total * 100).toFixed(2);
    return `<span class="seg-${s}" style="width:${pct}%"></span>`;
  }).join('');
  return `<div class="status-bar">${segs}</div>`;
}

function statusLegendHtml(byStatus) {
  return STATUS_ORDER.map(s =>
    `<span class="leg-${s}">${byStatus[s] || 0} ${s[0].toUpperCase() + s.slice(1)}</span>`
  ).join('');
}

// Simple horizontal-bar histogram: one row per bucket, all bars scaled to
// the row with the largest value so relative magnitude reads at a glance.
// `hueClass` picks one consistent fill color per chart (never a rainbow -
// these are single-series magnitude charts, not multi-series identity).
function histogramHtml(rows, hueClass, valueFmt) {
  const max = Math.max(1, ...rows.map(r => r.count));
  const fmt = valueFmt || (r => r.count);
  return `
    <div class="hist-chart">
      ${rows.map(r => `
        <div class="hist-row" title="${escapeHtml(r.label)}: ${fmt(r)}">
          <span class="hist-label">${escapeHtml(r.label)}</span>
          <div class="hist-track"><div class="hist-fill ${hueClass}" style="width:${(r.count / max * 100).toFixed(1)}%"></div></div>
          <span class="hist-value">${fmt(r)}</span>
        </div>
      `).join('')}
    </div>
  `;
}

async function loadInsights() {
  const d = await fetch('/api/dashboard/insights').then(r => r.json());
  const section = document.getElementById('insightsSection');
  if (!section) return;

  const storageRows = d.storage_by_platform.map(p => ({
    label: PLATFORM_LABEL[p.platform], count: p.size_bytes, human: p.size_human,
  }));

  section.innerHTML = `
    <div class="dash-section-title">Library insights</div>
    <div class="dash-lists">
      <div class="dash-list-card">
        <div class="dash-section-title" style="font-size:13px;">Storage by shelf</div>
        ${histogramHtml(storageRows, 'hue-gold', r => r.human)}
      </div>
      <div class="dash-list-card">
        <div class="dash-section-title" style="font-size:13px;">Install size distribution</div>
        ${histogramHtml(d.size_histogram, 'hue-teal')}
      </div>
      <div class="dash-list-card">
        <div class="dash-section-title" style="font-size:13px;">Rating distribution</div>
        ${histogramHtml(d.rating_histogram, 'hue-gold')}
      </div>
    </div>
    <div class="dash-list-card" style="margin-top:16px;">
      <div class="dash-section-title" style="font-size:13px;">Added to the library, last 12 months</div>
      ${histogramHtml(d.added_by_month, 'hue-teal')}
    </div>
  `;
}

function platformCardHtml(key, p) {
  // "Folder linked" just means the installer/backup files are known to sit
  // somewhere on disk - most of this library is offline installers, not
  // extracted/installed games. "Installed" (has an executable set) is the
  // real signal, and only means something for GOG/Steam - PS3/PS4 have no
  // launchable executable through this app at all.
  const showPlayable = key === 'gog' || key === 'steam';
  return `
    <div class="dash-platform-card">
      <h3>${PLATFORM_LABEL[key]}</h3>
      ${statusBarHtml(p.by_status, p.total)}
      <div class="dash-meta-row">
        <span>${p.total} games · ${p.size_human}</span>
        <span class="${p.missing ? 'dash-bad' : 'dash-ok'}">${p.folders_linked} folder${p.folders_linked === 1 ? '' : 's'} linked${p.missing ? `, ${p.missing} missing` : ''}</span>
      </div>
      ${showPlayable ? `
      <div class="dash-meta-row">
        <span>Actually installed</span>
        <span class="${p.playable ? 'dash-ok' : 'dash-bad'}">${p.playable} / ${p.total} have an executable set</span>
      </div>` : ''}
    </div>
  `;
}

function listCardHtml(title, rows, metaFn) {
  const body = rows.length
    ? rows.map(r => `
        <div class="dash-list-row">
          <span class="dlr-title" title="${escapeHtml(r.title)}">${escapeHtml(r.title)} <span style="color:var(--muted)">· ${PLATFORM_LABEL[r.platform] || r.platform}</span></span>
          <span class="dlr-meta">${metaFn(r)}</span>
        </div>
      `).join('')
    : '<div class="save-hint">Nothing yet.</div>';
  return `<div class="dash-list-card"><div class="dash-section-title">${title}</div>${body}</div>`;
}

function buildStatusBarHtml(b) {
  const total = b.up_to_date + b.outdated + b.unverified;
  if (!total) return '<div class="build-bar"></div>';
  const seg = (n, cls) => `<span class="${cls}" style="width:${(n / total * 100).toFixed(2)}%"></span>`;
  return `<div class="build-bar">${seg(b.up_to_date, 'seg-uptodate')}${seg(b.outdated, 'seg-outdated')}${seg(b.unverified, 'seg-unverified')}</div>`;
}

function outdatedRowHtml(g) {
  const cover = g.cover_url ? `style="background-image:url('${escapeHtml(g.cover_url)}?t=${encodeURIComponent(g.updated_at || '')}')"` : '';
  return `
    <div class="dash-list-row outdated-row">
      <div class="outdated-cover" ${cover}></div>
      <span class="dlr-title" title="${escapeHtml(g.title)}">${escapeHtml(g.title)}</span>
      <span class="dlr-meta">${g.current_build} <span class="build-arrow">&rarr;</span> <b class="dash-bad">${g.latest_build}</b></span>
    </div>
  `;
}

async function loadBuildStatus(afterMessage) {
  const b = await fetch('/api/build_status').then(r => r.json());
  const section = document.getElementById('buildStatusSection');
  if (!section) return;

  section.innerHTML = `
    <div class="dash-section-title-row">
      <div class="dash-section-title">Build status - GOG shelf</div>
      <div>
        <input type="file" id="gamelistFile" accept=".txt" style="display:none;">
        <button class="close-btn" id="uploadGamelistBtn">📤 Upload game list</button>
      </div>
    </div>
    <div id="gamelistUploadHint" class="save-hint upload-hint" style="margin-bottom:10px;">${escapeHtml(afterMessage || '')}</div>
    <div class="dash-tiles">
      <div class="dash-tile ok"><div class="dash-value">${b.up_to_date}</div><div class="dash-label">Up to date</div></div>
      <div class="dash-tile ${b.outdated ? 'bad' : 'ok'}"><div class="dash-value">${b.outdated}</div><div class="dash-label">Outdated</div></div>
      <div class="dash-tile"><div class="dash-value">${b.unverified}</div><div class="dash-label">Unverified</div></div>
    </div>
    ${buildStatusBarHtml(b)}
    <div class="status-legend">
      <span class="leg-uptodate">${b.up_to_date} Up to date</span>
      <span class="leg-outdated">${b.outdated} Outdated</span>
      <span class="leg-unverified">${b.unverified} Unverified</span>
    </div>
    ${b.not_comparable ? `<div class="save-hint" style="margin-top:10px;">+ ${b.not_comparable} more use an old version-numbering convention (e.g. 2.1.0.17) instead of a GOG build id, so they can't be compared against this list at all - not counted above.</div>` : ''}
    <button class="close-btn" id="toggleOutdatedBtn" style="margin-top:14px;" ${b.outdated ? '' : 'disabled'}>
      ${b.outdated ? `⚠ View outdated games (${b.outdated})` : 'No outdated games'}
    </button>
    <div id="outdatedList" class="dash-list-card" style="display:none; margin-top:14px;">
      ${b.outdated_list.map(outdatedRowHtml).join('') || '<div class="save-hint">Nothing outdated.</div>'}
    </div>
  `;

  const toggleBtn = document.getElementById('toggleOutdatedBtn');
  const list = document.getElementById('outdatedList');
  if (toggleBtn && b.outdated) {
    toggleBtn.addEventListener('click', () => {
      const open = list.style.display !== 'none';
      list.style.display = open ? 'none' : '';
      toggleBtn.textContent = open ? `⚠ View outdated games (${b.outdated})` : `▲ Hide outdated games`;
    });
  }

  const uploadBtn = document.getElementById('uploadGamelistBtn');
  const fileInput = document.getElementById('gamelistFile');
  const hint = document.getElementById('gamelistUploadHint');
  uploadBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    uploadBtn.disabled = true;
    uploadBtn.classList.add('working');
    uploadBtn.textContent = '⏳ Comparing…';
    hint.classList.add('working');
    hint.textContent = `reading ${file.name} and comparing every game - this takes a few seconds…`;

    const formData = new FormData();
    formData.append('gamelist', file);
    try {
      const res = await fetch('/api/build_status/upload', { method: 'POST', body: formData });
      const data = await res.json();
      fileInput.value = '';
      if (!res.ok) {
        uploadBtn.disabled = false;
        uploadBtn.classList.remove('working');
        uploadBtn.textContent = '📤 Upload game list';
        hint.classList.remove('working');
        hint.textContent = data.error || 'error reading that file';
        return;
      }
      await loadBuildStatus(
        `✓ ${data.parsed_entries} entries parsed - ${data.updated} games matched, ${data.skipped} left unverified.`
      );
    } catch (e) {
      fileInput.value = '';
      uploadBtn.disabled = false;
      uploadBtn.classList.remove('working');
      uploadBtn.textContent = '📤 Upload game list';
      hint.classList.remove('working');
      hint.textContent = 'upload failed - is the app still running?';
    }
  });
}

async function loadDashboard() {
  const main = document.getElementById('dashMain');
  const d = await fetch('/api/dashboard').then(r => r.json());
  const o = d.overall;

  main.innerHTML = `
    <section>
      <div class="dash-tiles">
        <div class="dash-tile gold"><div class="dash-value">${o.total}</div><div class="dash-label">Total games</div></div>
        <div class="dash-tile"><div class="dash-value">${o.size_human}</div><div class="dash-label">Total library size</div></div>
        <div class="dash-tile ok"><div class="dash-value">${o.folders_linked}</div><div class="dash-label">Folders linked (installer/backup on disk)</div></div>
        <div class="dash-tile ${o.missing ? 'bad' : 'ok'}"><div class="dash-value">${o.missing}</div><div class="dash-label">Missing folders</div></div>
        <div class="dash-tile gold"><div class="dash-value">${d.playable}</div><div class="dash-label">Actually installed (executable set, GOG+Steam)</div></div>
        <div class="dash-tile"><div class="dash-value">${d.ids_verified}</div><div class="dash-label">GOG IDs verified</div></div>
      </div>
    </section>

    <section>
      <div class="dash-section-title">Status breakdown - all shelves</div>
      ${statusBarHtml(o.by_status, o.total)}
      <div class="status-legend">${statusLegendHtml(o.by_status)}</div>
    </section>

    <section>
      <div class="dash-section-title">By shelf</div>
      <div class="dash-platform-grid">
        ${['gog', 'steam', 'ps3', 'ps4'].map(k => platformCardHtml(k, d.platforms[k])).join('')}
      </div>
    </section>

    <section id="buildStatusSection">
      <div class="save-hint">loading build status…</div>
    </section>

    <section>
      <div class="dash-tiles">
        <div class="dash-tile"><div class="dash-value">${d.rated_count}</div><div class="dash-label">Rated games${d.avg_rating ? ` · avg ${d.avg_rating}` : ''}</div></div>
        <div class="dash-tile"><div class="dash-value">${d.recently_added_7d}</div><div class="dash-label">Added in the last 7 days</div></div>
        <div class="dash-tile"><div class="dash-value">${d.trash_count}</div><div class="dash-label">In trash (of 50 max)</div></div>
      </div>
    </section>

    <section>
      <div class="dash-lists">
        ${listCardHtml('Top rated', d.top_rated, r => '★'.repeat(Math.round(r.rating / 2)))}
        ${listCardHtml('Largest installs', d.largest, r => r.size_human)}
        ${listCardHtml('Recently added', d.recent, r => (r.added_at || '').split(' ')[0])}
      </div>
    </section>

    <section id="insightsSection">
      <div class="save-hint">loading insights…</div>
    </section>
  `;

  loadBuildStatus();
  loadInsights();
}

loadDashboard();
