const PLATFORM_LABEL = { gog: 'GOG', steam: 'Steam', ps3: 'PS3', ps4: 'PS4' };
const PLATFORM_COLORS = { gog: '#ff9500', steam: '#1b9fff', ps3: '#1b5eff', ps4: '#ff1b6d' };
const STATUS_ORDER = ['backlog', 'playing', 'completed', 'abandoned'];
const STATUS_COLORS = { backlog: '#ff9500', playing: '#64ff64', completed: '#1b9fff', abandoned: '#aaa' };

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

async function loadDashboard() {
  const d = await fetch('/api/dashboard').then(r => r.json());
  const o = d.overall;

  // Update metric cards
  document.getElementById('totalGames').textContent = o.total;
  document.getElementById('totalStorage').textContent = o.size_human;
  document.getElementById('foldersLinked').textContent = o.folders_linked;
  document.getElementById('missingFolders').textContent = o.missing;

  // Initialize charts
  initStatusChart(o.by_status);
  initPlatformChart(d.platforms);

  // Load other sections
  await loadBuildStatus();
  const insights = await loadInsights();
  if (insights) {
    initActivityChart(insights.added_by_month);
  }
  await loadGameLists();
  loadMissingFolders();
}

function initStatusChart(byStatus) {
  const ctx = document.getElementById('statusChart').getContext('2d');
  if (charts.status) charts.status.destroy();

  charts.status = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Backlog', 'Playing', 'Completed', 'Abandoned'],
      datasets: [{
        data: [byStatus.backlog, byStatus.playing, byStatus.completed, byStatus.abandoned],
        backgroundColor: ['#ff9500', '#64ff64', '#1b9fff', '#666'],
        borderColor: 'transparent',
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#aaa', font: { size: 12 }, padding: 16 }
        }
      }
    }
  });
}

function initPlatformChart(platforms) {
  const ctx = document.getElementById('platformChart').getContext('2d');
  if (charts.platform) charts.platform.destroy();

  const keys = ['gog', 'steam', 'ps3', 'ps4'];
  const counts = keys.map(k => platforms[k].total);

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
        x: { grid: { color: 'rgba(100, 150, 255, 0.1)' }, ticks: { color: '#aaa' } },
        y: { grid: { display: false }, ticks: { color: '#aaa' } }
      }
    }
  });
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
    ${statusBarHtml({ backlog: b.up_to_date, playing: b.outdated, completed: b.unverified, abandoned: 0 }, b.up_to_date + b.outdated + b.unverified)}
    <div class="status-legend" style="margin-top:12px;">
      <span class="leg-backlog">${b.up_to_date} Up to date</span>
      <span class="leg-playing">${b.outdated} Outdated</span>
      <span class="leg-completed">${b.unverified} Unverified</span>
    </div>
  `;
}

function initActivityChart(addedByMonth) {
  const ctx = document.getElementById('activityChart').getContext('2d');
  if (charts.activity) charts.activity.destroy();

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
        borderColor: '#64c8ff',
        backgroundColor: 'rgba(100, 200, 255, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#64c8ff',
        pointBorderColor: '#000000',
        pointBorderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { grid: { color: 'rgba(100, 150, 255, 0.1)' }, ticks: { color: '#aaa' } },
        y: { grid: { color: 'rgba(100, 150, 255, 0.1)' }, ticks: { color: '#aaa' }, beginAtZero: true }
      }
    }
  });
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
      alert(`Build check complete:\n\n✓ Updated: ${data.updated} games\n⊙ Skipped: ${data.skipped} games\n📊 Total: ${data.total_games} games\n\nOutdated games: ${data.outdated_count}`);

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
