const PLATFORM_LABEL = { gog: 'GOG', steam: 'Steam', ps3: 'PS3', ps4: 'PS4' };
const PLATFORM_COLORS = { gog: '#f0a24a', steam: '#43d2ff', ps3: '#7788ff', ps4: '#ed3f9e' };
const STATUS_ORDER = ['backlog', 'playing', 'completed'];
const STATUS_COLORS = { backlog: '#929bad', playing: '#43d2ff', completed: '#63e6a3' };

let charts = {};

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

function histogramHtml(rows, hueClass) {
  const max = Math.max(1, ...rows.map(r => r.count));
  return `<div class="hist-chart ${hueClass}">
    ${rows.map(r => `
      <div class="hist-row">
        <span class="hist-label">${escapeHtml(r.label)}</span>
        <div class="hist-track"><div class="hist-fill" style="width:${(r.count / max * 100).toFixed(1)}%"></div></div>
        <span class="hist-value">${r.count}</span>
      </div>
    `).join('')}
  </div>`;
}

async function loadDashboard() {
  const d = await fetch('/api/dashboard').then(r => r.json());
  const o = d.overall;

  // Update metric cards
  document.getElementById('totalGames').textContent = o.total;
  document.getElementById('totalStorage').textContent = o.size_human;
  document.getElementById('foldersLinked').textContent = o.folders_linked;
  document.getElementById('missingFolders').textContent = o.missing;
  document.getElementById('actuallyInstalled').textContent = d.playable;
  document.getElementById('installedBreakdown').textContent =
    `${d.platforms.steam.playable} Steam · ${d.platforms.gog.playable} GOG`;
  document.getElementById('idsVerified').textContent = d.ids_verified;
  document.getElementById('ratedCount').textContent = d.rated_count;
  if (d.avg_rating) {
    document.getElementById('avgRating').textContent = `avg ${d.avg_rating}/10`;
  }
  document.getElementById('recentlyAdded').textContent = d.recently_added_7d;
  document.getElementById('trashCount').textContent = `${d.trash_count}/50`;

  // Initialize charts
  initStatusChart(o.by_status);
  initPlatformChart(d.platforms);

  // Load other sections
  await loadPlatformCards(d.platforms);
  await loadBuildStatus();
  const insights = await loadInsights();
  if (insights) {
    initActivityChart(insights.added_by_month);
    renderHistograms(insights);
  }
  await loadGameLists();
  loadMissingFolders();
}

function initStatusChart(byStatus) {
  const ctx = document.getElementById('statusChart').getContext('2d');
  if (charts.status) charts.status.destroy();

  const plugin = {
    id: 'glassBackground',
    beforeDatasetsDraw(chart) {
      const {ctx: canvasCtx, chartArea: {left, top, width, height}} = chart;
      canvasCtx.fillStyle = 'rgba(5, 8, 14, 0.18)';
      canvasCtx.fillRect(left, top, width, height);
    }
  };

  charts.status = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Backlog', 'Playing', 'Completed'],
      datasets: [{
        data: [byStatus.backlog, byStatus.playing, byStatus.completed],
        backgroundColor: STATUS_ORDER.map(s => STATUS_COLORS[s]),
        borderColor: 'transparent',
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#8f98aa', font: { size: 12 }, padding: 16, usePointStyle: true, pointStyle: 'circle' }
        }
      }
    },
    plugins: [plugin]
  });
}

function initPlatformChart(platforms) {
  const ctx = document.getElementById('platformChart').getContext('2d');
  if (charts.platform) charts.platform.destroy();

  const keys = ['gog', 'steam', 'ps3', 'ps4'];
  const counts = keys.map(k => platforms[k].total);

  const plugin = {
    id: 'glassBackground',
    beforeDatasetsDraw(chart) {
      const {ctx: canvasCtx, chartArea: {left, top, width, height}} = chart;
      canvasCtx.fillStyle = 'rgba(5, 8, 14, 0.18)';
      canvasCtx.fillRect(left, top, width, height);
    }
  };

  charts.platform = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: keys.map(k => PLATFORM_LABEL[k]),
      datasets: [{
        label: 'Games',
        data: counts,
        backgroundColor: keys.map(k => PLATFORM_COLORS[k] + '80'),
        borderColor: keys.map(k => PLATFORM_COLORS[k]),
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.055)' }, ticks: { color: '#8f98aa' }, border: { display: false } },
        y: { grid: { display: false }, ticks: { color: '#8f98aa' }, border: { display: false } }
      }
    },
    plugins: [plugin]
  });
}

async function loadPlatformCards(platforms) {
  const section = document.getElementById('platformCardsSection');
  if (!section) return;

  const html = ['gog', 'steam', 'ps3', 'ps4'].map(key => {
    const p = platforms[key];
    const showPlayable = key === 'gog' || key === 'steam';
    return `
      <div class="platform-card">
        <div class="platform-title">${PLATFORM_LABEL[key]} Shelf</div>
        ${statusBarHtml(p.by_status, p.total)}
        <div class="status-legend">${statusLegendHtml(p.by_status)}</div>
        <div class="platform-meta">
          <span>${p.total} games · ${p.size_human}</span>
          <span class="${p.missing ? 'dash-bad' : 'dash-ok'}">${p.folders_linked} linked${p.missing ? `, ${p.missing} missing` : ''}</span>
        </div>
        ${showPlayable ? `
        <div class="platform-meta" style="border-top: none; margin-top: 8px; padding-top: 0;">
          <span>Actually installed</span>
          <span class="${p.playable ? 'dash-ok' : 'dash-bad'}">${p.playable}/${p.total}</span>
        </div>` : ''}
      </div>
    `;
  }).join('');

  section.innerHTML = `<div class="platform-grid">${html}</div>`;
}

function initActivityChart(addedByMonth) {
  const ctx = document.getElementById('activityChart').getContext('2d');
  if (charts.activity) charts.activity.destroy();

  const plugin = {
    id: 'glassBackground',
    beforeDatasetsDraw(chart) {
      const {ctx: canvasCtx, chartArea: {left, top, width, height}} = chart;
      canvasCtx.fillStyle = 'rgba(5, 8, 14, 0.18)';
      canvasCtx.fillRect(left, top, width, height);
    }
  };

  charts.activity = new Chart(ctx, {
    type: 'line',
    data: {
      labels: addedByMonth.map(m => {
        const [year, month] = m.label.split('-');
        return new Date(year, parseInt(month) - 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
      }),
      datasets: [{
        label: 'Games Added',
        data: addedByMonth.map(m => m.count),
        borderColor: '#43d2ff',
        backgroundColor: 'rgba(67, 210, 255, 0.08)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#ed3f9e',
        pointBorderColor: '#080b12',
        pointBorderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#8f98aa' }, border: { display: false } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#8f98aa' }, border: { display: false }, beginAtZero: true }
      }
    },
    plugins: [plugin]
  });
}

function renderHistograms(data) {
  const sizeDiv = document.getElementById('sizeDistributionChart');
  const ratingDiv = document.getElementById('ratingDistributionChart');

  if (sizeDiv) {
    sizeDiv.innerHTML = histogramHtml(data.size_histogram, 'hue-teal');
  }
  if (ratingDiv) {
    ratingDiv.innerHTML = histogramHtml(data.rating_histogram, 'hue-gold');
  }
}

async function loadBuildStatus() {
  const b = await fetch('/api/build_status').then(r => r.json());
  const section = document.getElementById('buildStatusSection');

  section.innerHTML = `
    <div class="list-title">🏗️ Build Status - GOG Shelf</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px;">
      <div style="background:rgba(100,255,100,0.2);padding:16px;border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#64ff64;">${b.up_to_date}</div>
        <div style="font-size:12px;color:#aaa;">Up to date</div>
      </div>
      <div style="background:rgba(255,150,100,0.2);padding:16px;border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#ff9500;">${b.outdated}</div>
        <div style="font-size:12px;color:#aaa;">Outdated</div>
      </div>
      <div style="background:rgba(150,150,150,0.2);padding:16px;border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#aaa;">${b.unverified}</div>
        <div style="font-size:12px;color:#aaa;">Unverified</div>
      </div>
    </div>
    ${b.outdated ? `
    <button class="close-btn" id="toggleOutdatedBtn" style="margin-bottom:16px;">
      ⚠ View outdated games (${b.outdated})
    </button>
    <div id="outdatedList" class="list-card" style="display:none;margin-bottom:16px;">
      <div class="list-title">⚠️ Outdated Games</div>
      ${b.outdated_list.map(g => `
        <div class="outdated-row">
          <div class="outdated-cover" style="background-image:url('${escapeHtml(g.cover_url || '')}?t=${encodeURIComponent(g.updated_at || '')}')"></div>
          <div style="flex:1;">
            <div style="font-weight:500;">${escapeHtml(g.title)}</div>
            <div style="font-size:12px;color:#999;">${g.current_build} <span class="build-arrow">→</span> ${g.latest_build}</div>
          </div>
        </div>
      `).join('')}
    </div>` : ''}
    ${b.unverified ? `
    <button class="close-btn" id="toggleUnverifiedBtn" style="margin-bottom:16px;">
      ❓ View unverified games (${b.unverified})
    </button>
    <div id="unverifiedList" class="list-card" style="display:none;margin-bottom:16px;">
      <div class="list-title">❓ Unverified Games</div>
      ${b.unverified_list.map(g => `
        <div class="outdated-row">
          <div class="outdated-cover" style="background-image:url('${escapeHtml(g.cover_url || '')}')"></div>
          <div style="flex:1;">
            <div style="font-weight:500;">${escapeHtml(g.title)}</div>
            <div style="font-size:12px;color:#999;">${g.reason} · GOG ID: ${g.gog_id}</div>
          </div>
        </div>
      `).join('')}
    </div>` : ''}
    ${b.not_comparable ? `<div class="save-hint" style="margin-top:10px;">+ ${b.not_comparable} use old version format (can't compare)</div>` : ''}
  `;

  if (b.outdated) {
    document.getElementById('toggleOutdatedBtn').addEventListener('click', () => {
      const list = document.getElementById('outdatedList');
      const btn = document.getElementById('toggleOutdatedBtn');
      const open = list.style.display !== 'none';
      list.style.display = open ? 'none' : '';
      btn.textContent = open ? `⚠ View outdated games (${b.outdated})` : `▲ Hide outdated games`;
    });
  }

  if (b.unverified) {
    document.getElementById('toggleUnverifiedBtn').addEventListener('click', () => {
      const list = document.getElementById('unverifiedList');
      const btn = document.getElementById('toggleUnverifiedBtn');
      const open = list.style.display !== 'none';
      list.style.display = open ? 'none' : '';
      btn.textContent = open ? `❓ View unverified games (${b.unverified})` : `▲ Hide unverified games`;
    });
  }
}

async function loadInsights() {
  const d = await fetch('/api/dashboard/insights').then(r => r.json());
  const section = document.getElementById('insightsSection');

  if (!section) return d;

  section.innerHTML = `
    <div class="list-title">📈 Library Insights</div>
    <div style="margin-top:16px;">
      <div style="margin-bottom:16px;">
        <div style="font-size:12px;color:#aaa;margin-bottom:8px;">STORAGE BY PLATFORM</div>
        ${(d.storage_by_platform || []).map(p => `
          <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(100,150,255,0.2);font-size:13px;">
            <span>${PLATFORM_LABEL[p.platform]}</span>
            <span style="color:#64c8ff;">${p.size_human}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  return d;
}

async function loadGameLists() {
  const data = await fetch('/api/dashboard/lists').then(r => r.json());

  // Top Rated
  const topRatedDiv = document.getElementById('topRatedList');
  if (topRatedDiv) {
    topRatedDiv.innerHTML = (data.top_rated || []).map(g => `
      <div class="list-row">
        <div style="flex:1;">
          <div style="font-weight:500;">${escapeHtml(g.title)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="color:#ffd700;">★ ${g.rating}/10</span>
          <span style="font-size:12px;color:#64c8ff;">${PLATFORM_LABEL[g.platform]}</span>
        </div>
      </div>
    `).join('') || '<div style="color:#aaa;font-size:12px;padding:8px;">No rated games yet</div>';
  }

  // Largest Installs
  const largestDiv = document.getElementById('largestList');
  if (largestDiv) {
    largestDiv.innerHTML = (data.largest || []).map(g => `
      <div class="list-row">
        <div style="flex:1;">
          <div style="font-weight:500;">${escapeHtml(g.title)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="color:#64ff64;">${g.size_human}</span>
          <span style="font-size:12px;color:#64c8ff;">${PLATFORM_LABEL[g.platform]}</span>
        </div>
      </div>
    `).join('') || '<div style="color:#aaa;font-size:12px;padding:8px;">No games found</div>';
  }

  // Recently Added
  const recentDiv = document.getElementById('recentList');
  if (recentDiv) {
    recentDiv.innerHTML = (data.recently_added || []).map(g => `
      <div class="list-row">
        <div style="flex:1;">
          <div style="font-weight:500;">${escapeHtml(g.title)}</div>
          <div style="font-size:12px;color:#999;">${g.added_at}</div>
        </div>
        <span style="font-size:12px;color:#64c8ff;">${PLATFORM_LABEL[g.platform]}</span>
      </div>
    `).join('') || '<div style="color:#aaa;font-size:12px;padding:8px;">No games yet</div>';
  }
}

function loadMissingFolders() {
  const scanBtn = document.getElementById('scanMissingFoldersBtn');
  const updateBtn = document.getElementById('updateInstalledBtn');
  const refreshSizesBtn = document.getElementById('refreshSizesBtn');
  const statusDiv = document.getElementById('scanStatus');
  const resultsDiv = document.getElementById('scanResults');

  scanBtn.addEventListener('click', async () => {
    scanBtn.disabled = true;
    scanBtn.textContent = '⏳ Scanning…';
    statusDiv.textContent = 'Checking all game folders on disk...';
    statusDiv.classList.add('working');

    try {
      const res = await fetch('/api/scan/missing-folders');
      const data = await res.json();

      scanBtn.disabled = false;
      scanBtn.textContent = 'Scan for missing folders';
      statusDiv.classList.remove('working');

      if (data.missing_count === 0) {
        statusDiv.textContent = `✓ All ${data.total_games} game folders found on disk!`;
        statusDiv.classList.add('dash-ok');
        resultsDiv.style.display = 'none';
      } else {
        statusDiv.textContent = `⚠ ${data.missing_count} of ${data.total_games} folders missing (${data.missing_percentage}%)`;
        statusDiv.classList.add('dash-bad');

        const rows = data.missing_games.map(g => `
          <div class="list-row">
            <div style="flex:1;">
              <div style="font-weight:500;">${escapeHtml(g.title)}</div>
              <div style="font-size:12px;color:var(--muted);">${escapeHtml(g.folder_path || g.reason)}</div>
            </div>
            <span style="font-size:12px;color:#64c8ff;">${PLATFORM_LABEL[g.platform]}</span>
          </div>
        `).join('');

        resultsDiv.innerHTML = `<div style="margin-top:16px;">${rows}</div>`;
        resultsDiv.style.display = '';
      }
    } catch (e) {
      scanBtn.disabled = false;
      scanBtn.textContent = 'Scan for missing folders';
      statusDiv.classList.remove('working');
      statusDiv.textContent = `Error scanning folders: ${e.message}`;
      statusDiv.classList.add('dash-bad');
    }
  });

  updateBtn.addEventListener('click', async () => {
    if (!confirm('Check every saved path and clear paths that no longer exist?')) return;
    updateBtn.disabled = true;
    updateBtn.textContent = '⏳ Updating…';
    statusDiv.className = 'save-hint working';
    statusDiv.innerHTML = `
      <div class="install-scan-feedback" role="status" aria-live="polite">
        <div class="install-scan-heading"><span class="install-scan-spinner"></span><span id="installScanMessage">Checking saved game paths</span></div>
        <div class="install-scan-progress"><span></span></div>
        <div class="install-scan-elapsed" id="installScanElapsed">Elapsed: 0s</div>
      </div>`;
    const startedAt = Date.now();
    let phase = 0;
    const phases = [
      'Checking saved game paths',
      'Testing folders and executables',
      'Recalculating installed games',
    ];
    const progressTimer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      const elapsedNode = document.getElementById('installScanElapsed');
      const messageNode = document.getElementById('installScanMessage');
      if (elapsedNode) elapsedNode.textContent = `Elapsed: ${elapsed}s`;
      if (messageNode && elapsed > 0 && elapsed % 3 === 0) {
        phase = (phase + 1) % phases.length;
        messageNode.textContent = phases[phase];
      }
    }, 1000);

    try {
      const res = await fetch('/api/scan/update-installed', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);

      document.getElementById('actuallyInstalled').textContent = data.installed_count;
      document.getElementById('installedBreakdown').textContent =
        `${data.installed_by_platform.steam || 0} Steam · ${data.installed_by_platform.gog || 0} GOG`;
      document.getElementById('foldersLinked').textContent = data.folders_linked;
      document.getElementById('missingFolders').textContent = data.missing_folders;
      statusDiv.className = 'save-hint dash-ok';
      statusDiv.textContent = `✓ ${data.installed_count} games installed (${data.installed_by_platform.steam || 0} Steam · ${data.installed_by_platform.gog || 0} GOG); ${data.updated_count} records updated, ${data.moved_to_backlog} moved to backlog.${data.unavailable_paths ? ` ${data.unavailable_paths} paths skipped because their drive is unavailable.` : ''}`;

      const rows = data.updated_games.map(game => `
        <div class="list-row">
          <div style="flex:1;">
            <div style="font-weight:500;">${escapeHtml(game.title)}</div>
            <div style="font-size:12px;color:var(--muted);">${game.changes.map(escapeHtml).join(' · ')}</div>
          </div>
          <span style="font-size:12px;color:#64c8ff;">${PLATFORM_LABEL[game.platform]}</span>
        </div>
      `).join('');
      resultsDiv.innerHTML = rows
        ? `<div style="margin-top:16px;">${rows}</div>`
        : '<div class="save-hint" style="margin-top:16px;">No stale paths found.</div>';
      resultsDiv.style.display = '';
    } catch (e) {
      statusDiv.className = 'save-hint dash-bad';
      statusDiv.textContent = `Error updating installed games: ${e.message}`;
    } finally {
      clearInterval(progressTimer);
      updateBtn.disabled = false;
      updateBtn.textContent = 'Update installed games';
    }
  });

  refreshSizesBtn.addEventListener('click', async () => {
    refreshSizesBtn.disabled = true;
    refreshSizesBtn.textContent = '⏳ Calculating…';
    statusDiv.className = 'save-hint working';
    statusDiv.innerHTML = `
      <div class="install-scan-feedback" role="status" aria-live="polite">
        <div class="install-scan-heading"><span class="install-scan-spinner"></span><span>Calculating game sizes on disk</span></div>
        <div class="install-scan-progress"><span></span></div>
        <div class="install-scan-elapsed" id="sizeScanElapsed">Elapsed: 0s</div>
      </div>`;
    const startedAt = Date.now();
    const progressTimer = setInterval(() => {
      const elapsedNode = document.getElementById('sizeScanElapsed');
      if (elapsedNode) elapsedNode.textContent = `Elapsed: ${Math.floor((Date.now() - startedAt) / 1000)}s`;
    }, 1000);

    try {
      const res = await fetch('/api/scan/refresh-sizes', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);

      await loadDashboard();
      statusDiv.className = 'save-hint dash-ok';
      statusDiv.textContent = `✓ Checked ${data.scanned_count} game folders; ${data.updated_count} sizes changed. Library size: ${data.total_size_human}.${data.missing_count ? ` ${data.missing_count} missing folders skipped.` : ''}${data.unavailable_count ? ` ${data.unavailable_count} folders skipped because their drive is unavailable.` : ''}`;
      const rows = data.updated_games.map(game => `
        <div class="list-row">
          <div style="flex:1;">
            <div style="font-weight:500;">${escapeHtml(game.title)}</div>
            <div style="font-size:12px;color:var(--muted);">${escapeHtml(game.old_size_human)} → ${escapeHtml(game.new_size_human)}</div>
          </div>
          <span style="font-size:12px;color:#64c8ff;">${PLATFORM_LABEL[game.platform]}</span>
        </div>
      `).join('');
      resultsDiv.innerHTML = rows
        ? `<div style="margin-top:16px;">${rows}</div>`
        : '<div class="save-hint" style="margin-top:16px;">All reachable game sizes were already current.</div>';
      resultsDiv.style.display = '';
    } catch (e) {
      statusDiv.className = 'save-hint dash-bad';
      statusDiv.textContent = `Error refreshing game sizes: ${e.message}`;
    } finally {
      clearInterval(progressTimer);
      refreshSizesBtn.disabled = false;
      refreshSizesBtn.textContent = 'Refresh game sizes';
    }
  });
}

// Handle gamelist upload
document.getElementById('uploadGamelistBtn').addEventListener('click', () => {
  document.getElementById('gamelistUpload').click();
});

document.getElementById('gamelistUpload').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const btn = document.getElementById('uploadGamelistBtn');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = '⏳ Uploading…';

  try {
    const formData = new FormData();
    formData.append('gamelist', file);

    const res = await fetch('/api/build_status/upload', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();

    if (res.ok) {
      btn.textContent = '✓ Uploaded!';
      alert(`Build check complete:\n\n✓ Updated: ${data.updated} games\n⊙ Skipped: ${data.skipped} games\n📊 Total: ${data.total_games} games\n\nOutdated games: ${data.outdated_count || 0}`);

      // Reload dashboard to show updated build status
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } else {
      btn.textContent = '❌ Error';
      alert('Error uploading gamelist: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    btn.textContent = '❌ Error';
    alert('Failed to upload: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
    e.target.value = '';
  }
});

loadDashboard();
