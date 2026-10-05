/**
 * app.js — Semantic Sentinel Command Center
 * Handles:
 *   - Clean 4-tab navigation (Dashboard, Detection, Alerts, Settings)
 *   - Video source switching (Demo clips, Uploaded video, Live webcam)
 *   - Explicit playback controls (Start Analysis, Pause, Stop, Restart)
 *   - Pixel-perfect normalized restricted zone drawing
 *   - High-contrast Semantic Alert Feed (Primary Output)
 *   - Decoupled, efficient polling (Low UI overhead, zero video lag)
 */

// ── State ─────────────────────────────────────────────────────────────────────
let activeTab = 'dashboard';
let currentVideoState = 'STANDBY';
let isPaused = false;
let isDrawingZone = false;
let drawnPoints = []; // Normalized points [[nx, ny], ...]
let activeDemoName = 'fence.mp4';
let currentSeverityFilter = 'ALL';
let allAlertsList = [];

// ── Init on DOM Load ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  startClock();
  setupCanvasEvents();
  
  // Initial data fetch
  fetchStatus();
  fetchAlerts();
  fetchVideoState();
  loadSettings();

  // Decoupled intervals (Separating high-freq video from low-freq stats)
  setInterval(fetchStatus, 3500);      // Status & KPIs every 3.5s
  setInterval(fetchAlerts, 2500);      // Semantic alerts every 2.5s
  setInterval(fetchVideoState, 1000);   // Live telemetry every 1s
});

// ── Clock (Indian Standard Time - IST) ─────────────────────────────────────────
function startClock() {
  function tick() {
    const now = new Date();
    const istString = now.toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    const el = document.getElementById('clockDisplay');
    if (el) el.textContent = `${istString} IST`;
  }
  tick();
  setInterval(tick, 1000);
}

// ── Tab Navigation ────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.dataset.tab;
      activeTab = targetTab;

      document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const pane = document.getElementById('pane-' + targetTab);
      if (pane) pane.classList.add('active');

      if (targetTab === 'detection') {
        setTimeout(syncCanvasSize, 100);
      }
    });
  });
}

// ── System Status & KPIs ──────────────────────────────────────────────────────
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const d = await res.json();

    // 4 KPI Cards
    setText('dashPersons', d.video_state?.persons_count || 0);
    setText('dashObjects', d.video_state?.objects_count || 0);
    setText('dashAlerts', d.active_alerts || 0);
    setText('dashCritical', d.critical_events || 0);

    // Nav badge
    setText('navAlertCount', d.active_alerts || 0);

    // Risk Breakdown
    setText('riskCountCritical', d.critical_events || 0);
    setText('riskCountHigh', d.high_events || 0);
    setText('riskCountMedium', d.medium_events || 0);
    setText('riskCountLow', d.low_events || 0);

    // Bandwidth Visual
    setText('bwSavedPct', (d.bandwidth_saved_pct || 99.98) + '% SAVED');
    setText('rawMbText', (d.raw_bytes_mb || 45.0) + ' MB');
    setText('semanticKbText', (d.semantic_bytes_kb || 0.18) + ' KB');
  } catch (err) {
    // Backend briefly restarting
  }
}

// ── Live Video Telemetry ──────────────────────────────────────────────────────
async function fetchVideoState() {
  try {
    const res = await fetch('/api/video/state');
    const d = await res.json();

    currentVideoState = d.state || 'STANDBY';
    const chip = document.getElementById('analysisStateChip');
    const btnPause = document.getElementById('btnPauseResume');
    const btnStart = document.getElementById('btnStartAnalysis');

    if (chip) {
      chip.textContent = currentVideoState;
      chip.className = 'status-chip ' + currentVideoState.toLowerCase();
    }

    if (currentVideoState === 'ANALYZING') {
      isPaused = false;
      if (btnPause) btnPause.textContent = '⏸ PAUSE';
      if (btnStart) btnStart.textContent = '▶ ANALYZING';
    } else if (currentVideoState === 'PAUSED') {
      isPaused = true;
      if (btnPause) btnPause.textContent = '▶ RESUME';
    } else {
      isPaused = false;
      if (btnPause) btnPause.textContent = '⏸ PAUSE';
      if (btnStart) btnStart.textContent = '▶ START ANALYSIS';
    }

    // Telemetry display beside video
    setText('fpsDisplay', (d.fps || 25) + ' FPS');
    setText('statPersons', d.persons_count || 0);
    setText('statObjects', d.objects_count || 0);
    setText('statAlerts', d.active_alerts_count || 0);

    // Active tracks list
    renderTracksList(d.tracks || []);

    // Latest Alert Box update
    if (d.latest_alert) {
      renderLatestAlert(d.latest_alert);
    }
  } catch (err) {}
}

function renderTracksList(tracks) {
  const container = document.getElementById('tracksList');
  if (!container) return;

  if (tracks.length === 0) {
    container.innerHTML = '<div class="track-empty-note">No objects currently in view</div>';
    return;
  }

  container.innerHTML = tracks.map(t => {
    const isInside = t.state === 'ENTERED' || t.state === 'INSIDE';
    const stateTag = isInside ? `[ZONE INTRUSION ${t.dwell}s]` : `[${t.state}]`;
    const rowClass = isInside ? 'track-row inside' : 'track-row';
    return `
      <div class="${rowClass}">
        <span>#${String(t.id).padStart(2, '0')} ${t.class.toUpperCase()}</span>
        <span>${stateTag}</span>
      </div>
    `;
  }).join('');
}

function renderLatestAlert(alert) {
  const box = document.getElementById('latestAlertBox');
  const badge = document.getElementById('latestAlertBadge');
  const timeEl = document.getElementById('latestAlertTime');
  const titleEl = document.getElementById('latestAlertTitle');
  const objEl = document.getElementById('latestAlertObject');
  const reasonEl = document.getElementById('latestAlertReason');

  if (!box || !alert) return;

  const sev = (alert.severity || 'LOW').toUpperCase();
  badge.textContent = sev;
  badge.className = 'la-badge ' + sev.toLowerCase();
  box.className = 'latest-alert-box ' + sev.toLowerCase();

  timeEl.textContent = (alert.timestamp || '').slice(11, 19) || 'Just now';
  titleEl.textContent = alert.event_type ? alert.event_type.replace(/_/g, ' ') : 'Security Event';
  objEl.textContent = `Track #${alert.track_id} (${alert.object_class || 'object'})`;
  reasonEl.textContent = alert.explanation || alert.message || 'Suspicious motion identified.';
}

// ── Semantic Alerts Feed & Table ──────────────────────────────────────────────
async function fetchAlerts() {
  try {
    const res = await fetch('/api/alerts?limit=50');
    const d = await res.json();
    allAlertsList = d.alerts || [];

    renderDashboardAlertFeed(allAlertsList);
    renderAlertsTable(allAlertsList);
  } catch (err) {}
}

function renderDashboardAlertFeed(alerts) {
  const feed = document.getElementById('dashAlertFeed');
  if (!feed) return;

  if (!alerts || alerts.length === 0) {
    feed.innerHTML = '<div class="empty-state">Standby. No verified alerts detected.</div>';
    return;
  }

  feed.innerHTML = alerts.slice(0, 15).map(a => {
    const sev = (a.severity || 'LOW').toUpperCase();
    const eventName = a.event_type ? a.event_type.replace(/_/g, ' ') : 'EVENT';
    const timeStr = (a.timestamp || '').slice(11, 19) || '--:--:--';
    const reasonText = a.explanation || a.message || 'Contextual perimeter breach.';
    const objText = `Track #${a.track_id} &bull; ${a.object_class || 'target'}`;

    return `
      <div class="alert-card ${sev.toLowerCase()}">
        <div class="alert-card-top">
          <span class="severity-pill ${sev.toLowerCase()}">${sev}</span>
          <span class="alert-time">${timeStr}</span>
        </div>
        <div class="alert-headline">${eventName}</div>
        <div class="alert-reason">${reasonText}</div>
        <div class="alert-meta-bar">
          <span class="meta-item">${objText}</span>
          <span class="meta-item">Zone: <strong>${a.zone_name || 'Restricted Sector'}</strong></span>
          <span class="meta-item">Payload: <strong>${a.alert_payload_bytes || 180} B</strong></span>
        </div>
      </div>
    `;
  }).join('');
}

// ── Alerts Tab Table Rendering & Filtering ────────────────────────────────────
function renderAlertsTable(alerts) {
  const tbody = document.getElementById('alertsTableBody');
  if (!tbody) return;

  let filtered = alerts;
  if (currentSeverityFilter !== 'ALL') {
    filtered = filtered.filter(a => (a.severity || '').toUpperCase() === currentSeverityFilter);
  }

  const query = (document.getElementById('alertTableSearch')?.value || '').toLowerCase().trim();
  if (query) {
    filtered = filtered.filter(a => {
      const hay = `${a.event_type} ${a.object_class} ${a.track_id} ${a.explanation} ${a.severity}`.toLowerCase();
      return hay.includes(query);
    });
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-table-cell">No alerts matching filter criteria.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(a => {
    const sev = (a.severity || 'LOW').toUpperCase();
    const timeStr = (a.timestamp || '').slice(11, 19) || '--:--:--';
    return `
      <tr>
        <td><span class="severity-pill ${sev.toLowerCase()}">${sev}</span></td>
        <td><strong>${a.event_type ? a.event_type.replace(/_/g, ' ') : 'EVENT'}</strong></td>
        <td>${a.object_class || 'unknown'}</td>
        <td><span style="font-family: var(--font-mono); color: var(--accent-cyan);">#${a.track_id}</span></td>
        <td style="font-family: var(--font-mono); color: var(--text-dim);">${timeStr}</td>
        <td>${a.explanation || a.message || 'Perimeter safety rule triggered.'}</td>
      </tr>
    `;
  }).join('');
}

function setSeverityFilter(sev, btn) {
  currentSeverityFilter = sev;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderAlertsTable(allAlertsList);
}

function filterAlertTable() {
  renderAlertsTable(allAlertsList);
}

function exportAlerts(format) {
  window.open(`/api/export/${format}`, '_blank');
}

// ── Video Controls (Phase 3 & Phase 2) ────────────────────────────────────────
async function startAnalysis() {
  try {
    const res = await fetch('/api/video/start', { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      showToast('AI Detection & Tracking Started.', 'ok');
      fetchVideoState();
    }
  } catch (e) {
    showToast('Failed to start analysis.', 'err');
  }
}

async function togglePause() {
  const endpoint = isPaused ? '/api/video/resume' : '/api/video/pause';
  try {
    const res = await fetch(endpoint, { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      isPaused = !isPaused;
      showToast(isPaused ? 'Video Analysis PAUSED.' : 'Video Analysis RESUMED.', 'ok');
      fetchVideoState();
    }
  } catch (e) {}
}

async function stopAnalysis() {
  try {
    const res = await fetch('/api/video/stop', { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      showToast('Video Analysis Stopped & Reset.', 'warn');
      fetchVideoState();
    }
  } catch (e) {}
}

async function restartAnalysis() {
  try {
    const res = await fetch('/api/video/restart', { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      showToast('Restarted from beginning.', 'ok');
      fetchVideoState();
    }
  } catch (e) {}
}

// ── Video Source Switching (Phase 3) ──────────────────────────────────────────
async function setLiveCamera() {
  try {
    const res = await fetch('/api/video/source', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_type: 'live', camera_index: 0 })
    });
    const d = await res.json();
    if (d.success) {
      setActiveSourceButton('btnSrcLive');
      setText('currentSourceFilename', 'Live Webcam #0');
      showToast('Switched to Live Camera. Click [ START ANALYSIS ] to run.', 'ok');
      refreshVideoFeed();
      fetchVideoState();
    }
  } catch (e) {
    showToast('Could not open live camera.', 'err');
  }
}

function toggleDemoDropdown() {
  const menu = document.getElementById('demoMenu');
  if (menu) menu.classList.toggle('open');
}

async function selectDemoVideo(clipName, description) {
  const menu = document.getElementById('demoMenu');
  if (menu) menu.classList.remove('open');
  activeDemoName = clipName;

  try {
    const res = await fetch('/api/video/source', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_type: 'demo', demo_name: clipName })
    });
    const d = await res.json();
    if (d.success) {
      setActiveSourceButton('btnDemoDropdown');
      setText('activeDemoLabel', `Demo: ${clipName}`);
      setText('currentSourceFilename', `${clipName} (${description})`);
      showToast(`Selected: ${clipName}. Click [ START ANALYSIS ] to begin.`, 'ok');
      refreshVideoFeed();
      fetchVideoState();
    }
  } catch (e) {
    showToast('Failed to select demo video.', 'err');
  }
}

async function handleVideoUpload(input) {
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append('video', file);

  showToast(`Uploading ${file.name}...`, 'info');

  try {
    const res = await fetch('/api/upload_video', {
      method: 'POST',
      body: formData
    });
    const d = await res.json();
    if (d.success) {
      setActiveSourceButton('btnSrcUpload');
      setText('currentSourceFilename', `Uploaded: ${d.filename}`);
      showToast(d.message || 'Video uploaded! Click [ START ANALYSIS ].', 'ok');
      refreshVideoFeed();
      fetchVideoState();
    } else {
      showToast(d.error || 'Upload failed.', 'err');
    }
  } catch (e) {
    showToast('Upload error.', 'err');
  }
}

function setActiveSourceButton(activeBtnId) {
  document.getElementById('btnSrcLive')?.classList.remove('active');
  document.getElementById('btnSrcUpload')?.classList.remove('active');
  document.getElementById('btnDemoDropdown')?.classList.remove('active');
  document.getElementById(activeBtnId)?.classList.add('active');
}

function refreshVideoFeed() {
  const img = document.getElementById('liveVideo');
  if (img) {
    img.src = '/api/video_feed?t=' + Date.now();
  }
}

// ── Restricted Zone Drawing (Phase 6 Coordinate Normalization) ────────────────
function setupCanvasEvents() {
  const canvas = document.getElementById('zoneCanvas');
  const img = document.getElementById('liveVideo');
  if (!canvas || !img) return;

  canvas.addEventListener('click', onCanvasClick);
  canvas.addEventListener('dblclick', onCanvasDblClick);
  canvas.addEventListener('mousemove', onCanvasMouseMove);
  window.addEventListener('resize', syncCanvasSize);
}

function syncCanvasSize() {
  const canvas = document.getElementById('zoneCanvas');
  const img = document.getElementById('liveVideo');
  if (!canvas || !img) return;

  // Align canvas pixel-for-pixel and position over the video image
  canvas.style.top = img.offsetTop + 'px';
  canvas.style.left = img.offsetLeft + 'px';
  canvas.style.width = (img.clientWidth || 640) + 'px';
  canvas.style.height = (img.clientHeight || 360) + 'px';
  canvas.width = img.clientWidth || 640;
  canvas.height = img.clientHeight || 360;
  redrawZoneCanvas();
}

function toggleZoneDrawing() {
  isDrawingZone = !isDrawingZone;
  drawnPoints = [];
  const btn = document.getElementById('btnDrawZone');
  const canvas = document.getElementById('zoneCanvas');
  const hint = document.getElementById('drawingHint');

  if (isDrawingZone) {
    canvas?.classList.add('active');
    btn?.classList.add('drawing');
    if (hint) hint.style.display = 'block';
    showToast('Click points on the video to define the zone. Double-click to close.', 'info');
  } else {
    canvas?.classList.remove('active');
    btn?.classList.remove('drawing');
    if (hint) hint.style.display = 'none';
    redrawZoneCanvas();
  }
}

let hoverNormPoint = null;
function onCanvasMouseMove(e) {
  if (!isDrawingZone || drawnPoints.length === 0) {
    hoverNormPoint = null;
    return;
  }
  const canvas = document.getElementById('zoneCanvas');
  const rect = canvas.getBoundingClientRect();
  const nx = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const ny = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
  hoverNormPoint = [nx, ny];
  redrawZoneCanvas();
}

function onCanvasClick(e) {
  if (!isDrawingZone) return;
  const canvas = document.getElementById('zoneCanvas');
  const rect = canvas.getBoundingClientRect();
  const nx = Number(Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)).toFixed(4));
  const ny = Number(Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)).toFixed(4));

  drawnPoints.push([nx, ny]);
  redrawZoneCanvas();
}

async function onCanvasDblClick(e) {
  if (!isDrawingZone || drawnPoints.length < 3) return;
  drawnPoints.pop(); // Remove extra click from dblclick

  const finalPolygon = [...drawnPoints];
  drawnPoints = [];
  isDrawingZone = false;

  const btn = document.getElementById('btnDrawZone');
  const canvas = document.getElementById('zoneCanvas');
  const hint = document.getElementById('drawingHint');
  canvas?.classList.remove('active');
  btn?.classList.remove('drawing');
  if (hint) hint.style.display = 'none';

  redrawZoneCanvas();

  try {
    const res = await fetch('/api/zones', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        polygon: finalPolygon,
        zone_name: 'Custom Restricted Zone'
      })
    });
    const d = await res.json();
    if (d.success) {
      showToast('Restricted Zone Saved & Active!', 'ok');
    }
  } catch (err) {
    showToast('Failed to save restricted zone.', 'err');
  }
}

async function autoDetectZone() {
  try {
    showToast('Analyzing scene geometry & perimeter...', 'info');
    const res = await fetch('/api/zones/autodetect', { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      drawnPoints = [];
      redrawZoneCanvas();
      showToast(`⚡ Restricted Zone Auto-Configured: ${d.zone_name}`, 'ok');
    }
  } catch (e) {
    showToast('Failed to auto-detect zone.', 'err');
  }
}

async function clearZone() {
  drawnPoints = [];
  redrawZoneCanvas();
  try {
    await fetch('/api/zones/clear', { method: 'POST' });
    showToast('Restricted Zone Cleared.', 'warn');
  } catch (e) {}
}

function redrawZoneCanvas() {
  const canvas = document.getElementById('zoneCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (drawnPoints.length > 0) {
    ctx.beginPath();
    ctx.moveTo(drawnPoints[0][0] * w, drawnPoints[0][1] * h);
    for (let i = 1; i < drawnPoints.length; i++) {
      ctx.lineTo(drawnPoints[i][0] * w, drawnPoints[i][1] * h);
    }
    if (hoverNormPoint) {
      ctx.lineTo(hoverNormPoint[0] * w, hoverNormPoint[1] * h);
    }
    ctx.strokeStyle = '#00d4ff';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw vertex dots
    drawnPoints.forEach((p, idx) => {
      ctx.beginPath();
      ctx.arc(p[0] * w, p[1] * h, 5, 0, Math.PI * 2);
      ctx.fillStyle = idx === 0 ? '#ef4444' : '#00d4ff';
      ctx.fill();
    });
  }
}

// ── Settings (Phase 9) ────────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const d = await res.json();
    if (d.confidence !== undefined) {
      const confRange = document.getElementById('confRange');
      if (confRange) confRange.value = d.confidence;
      setText('confVal', parseFloat(d.confidence).toFixed(2));
    }
    if (d.loiter_seconds !== undefined) {
      const loiterRange = document.getElementById('loiterRange');
      if (loiterRange) loiterRange.value = d.loiter_seconds;
      setText('loiterVal', d.loiter_seconds + 's');
    }
    if (d.cooldown_seconds !== undefined) {
      const cooldownRange = document.getElementById('cooldownRange');
      if (cooldownRange) cooldownRange.value = d.cooldown_seconds;
      setText('cooldownVal', d.cooldown_seconds + 's');
    }
  } catch (e) {}
}

async function saveSettings() {
  const conf = parseFloat(document.getElementById('confRange')?.value || 0.40);
  const loiter = parseFloat(document.getElementById('loiterRange')?.value || 10);
  const cooldown = parseFloat(document.getElementById('cooldownRange')?.value || 6);

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        confidence: conf,
        loiter_seconds: loiter,
        cooldown_seconds: cooldown
      })
    });
    const d = await res.json();
    if (d.success) {
      const msg = document.getElementById('settingsSaveMsg');
      if (msg) {
        msg.textContent = 'Settings saved successfully!';
        setTimeout(() => { msg.textContent = ''; }, 3000);
      }
      showToast('Settings saved and applied.', 'ok');
    }
  } catch (e) {
    showToast('Failed to save settings.', 'err');
  }
}

// ── Manual Scenario Injection (Phase 13 Demo Reliability) ────────────────────
async function injectScenario(scenario) {
  try {
    const res = await fetch('/api/simulate/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario })
    });
    const d = await res.json();
    if (d.success) {
      showToast(`Injected: ${scenario.replace(/_/g, ' ').toUpperCase()}`, 'ok');
      fetchAlerts();
      fetchVideoState();
      fetchStatus();
    }
  } catch (e) {}
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function showToast(msg, type = 'info') {
  const stack = document.getElementById('toastStack');
  if (!stack) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  stack.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    setTimeout(() => t.remove(), 300);
  }, 3200);
}
