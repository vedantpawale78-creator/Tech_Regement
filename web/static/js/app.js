/**
 * app.js — Semantic Sentinel Command Center
 * Features:
 *   - 5-tab navigation: Dashboard, Detection, Alerts, Analyzer, Settings
 *   - Edge AI video processing, tracking, and normalized restricted zone drawing
 *   - High-contrast Semantic Alert Feed with explainable risk scores and packet inspector
 *   - Alert lifecycle operations: NEW -> ACKNOWLEDGED -> RESOLVED
 *   - Tactical 2D situation canvas with live coordinate mapping
 *   - Chronological threat trend progression and track inspector
 *   - Resilient Communication Mode Simulator (NORMAL / LIMITED / OFFLINE) with queue syncing
 *   - Directly measured communication efficiency & Edge AI health monitoring
 *   - Canonical demo scenarios: Normal Patrol, Restricted Breach, Loitering Escalation
 */

// ── State ─────────────────────────────────────────────────────────────────────
let activeTab = 'dashboard';
let currentVideoState = 'STANDBY';
let isPaused = false;
let isDrawingZone = false;
let drawnPoints = []; // Normalized points [[nx, ny], ...]
let activeDemoName = 'fence.mp4';
let currentSeverityFilter = 'ALL';
let currentStatusFilter = 'ALL';
let allAlertsList = [];
let lastLatestAlertTimestamp = null;
let currentModalAlertId = null;
let activeCommMode = 'NORMAL';
let latestTelemetryZones = [];
let latestTelemetryTracks = [];

// ── Init on DOM Load ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  startClock();
  setupCanvasEvents();

  // Initial data fetches
  fetchStatus();
  fetchAlerts();
  fetchVideoState();
  fetchCommMode();
  fetchCommEfficiency();
  fetchEdgeHealth();
  loadSettings();

  // Polling intervals
  setInterval(fetchStatus, 3500);          // Status & KPIs
  setInterval(fetchAlerts, 2500);          // Semantic alerts
  setInterval(fetchVideoState, 1000);       // Live telemetry
  setInterval(fetchCommMode, 3000);        // Comm mode & queue depth
  setInterval(fetchCommEfficiency, 4000);  // Measured bandwidth stats
  setInterval(fetchEdgeHealth, 2500);      // CPU/RAM/FPS telemetry
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
      } else if (targetTab === 'analyzer') {
        setTimeout(() => {
          renderTacticalCanvas(latestTelemetryTracks, latestTelemetryZones);
          fetchOfflineQueue();
        }, 100);
      }
    });
  });
}

// ── System Status & KPIs ──────────────────────────────────────────────────────
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const d = await res.json();

    const urgentCount = (d.urgent_alerts_count !== undefined) ? d.urgent_alerts_count : (d.active_alerts || 0);

    // 4 Primary KPI Cards
    setText('dashPersons', d.video_state?.persons_count || 0);
    setText('dashObjects', d.video_state?.objects_count || 0);
    setText('dashAlerts', urgentCount);
    setText('dashCritical', d.run_critical_count ?? 0);

    // Nav badge - ONLY Critical and High alerts, refreshed after every run of video
    setText('navAlertCount', urgentCount);

    // Risk Breakdown
    setText('riskCountCritical', d.critical_events || 0);
    setText('riskCountHigh', d.high_events || 0);
    setText('riskCountMedium', d.medium_events || 0);
    setText('riskCountLow', d.low_events || 0);

    // Comm mode sync
    if (d.comm_mode) {
      updateCommModeUI(d.comm_mode, d.offline_queue_size || 0);
    }
  } catch (err) {}
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
      if (btnPause) btnPause.textContent = '⏸ Pause';
      if (btnStart) btnStart.textContent = '▶ Analyzing';
    } else if (currentVideoState === 'PAUSED') {
      isPaused = true;
      if (btnPause) btnPause.textContent = '▶ Resume';
    } else {
      isPaused = false;
      if (btnPause) btnPause.textContent = '⏸ Pause';
      if (btnStart) btnStart.textContent = '▶ Start Analysis';
    }

    // Telemetry display beside video
    setText('fpsDisplay', (d.fps || 25) + ' FPS');
    setText('statPersons', d.persons_count || 0);
    setText('statObjects', d.objects_count || 0);

    // Alert count beside alerts: ONLY Critical & High, refreshed after every run of video
    const runUrgent = (d.run_urgent_count !== undefined) ? d.run_urgent_count : (d.active_alerts_count || 0);
    setText('statAlerts', runUrgent);
    setText('navAlertCount', runUrgent);
    setText('dashAlerts', runUrgent);

    // Save for tactical map
    latestTelemetryZones = d.zones || [];
    latestTelemetryTracks = d.tracks || [];

    // Active tracks list
    renderTracksList(d.tracks || []);

    // Update track selector options in Analyzer tab
    updateTrackSelectorOptions(d.tracks || []);

    // Tactical 2D map update if Analyzer is active
    if (activeTab === 'analyzer') {
      renderTacticalCanvas(latestTelemetryTracks, latestTelemetryZones);
    }

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
    container.innerHTML = '<div class="track-empty-note">No active tracks in view</div>';
    return;
  }

  container.innerHTML = tracks.map(t => {
    const inZone = t.state === 'INSIDE' || t.state === 'ENTERED';
    const badgeCls = inZone ? 'threat' : 'safe';
    const dwellStr = inZone && t.dwell > 0 ? ` &bull; ${t.dwell}s` : '';
    return `
      <div class="track-item ${badgeCls}">
        <span class="track-id-badge">#${t.id}</span>
        <span class="track-class">${(t.class || 'object').toUpperCase()}</span>
        <span class="track-conf">${Math.round((t.conf || 0.8) * 100)}%</span>
        <span class="track-state ${badgeCls}">${t.state}${dwellStr}</span>
      </div>
    `;
  }).join('');
}

function updateTrackSelectorOptions(tracks) {
  const sel = document.getElementById('trackSelector');
  if (!sel) return;

  const currentVal = sel.value;
  const knownIds = new Set();
  Array.from(sel.options).forEach(opt => knownIds.add(opt.value));

  // Add tracks from live video
  tracks.forEach(t => {
    const tid = String(t.id);
    if (!knownIds.has(tid)) {
      const opt = document.createElement('option');
      opt.value = tid;
      opt.textContent = `Track #${tid} (${t.class || 'target'})`;
      sel.appendChild(opt);
      knownIds.add(tid);
    }
  });

  // Always ensure demo track 525 is present
  if (!knownIds.has('525')) {
    const opt = document.createElement('option');
    opt.value = '525';
    opt.textContent = 'Track #525 (Demo Intruder)';
    sel.appendChild(opt);
  }

  if (currentVal && knownIds.has(currentVal)) {
    sel.value = currentVal;
  }
}

function renderLatestAlert(alert) {
  const box = document.getElementById('latestAlertBox');
  const badge = document.getElementById('latestAlertBadge');
  const title = document.getElementById('latestAlertTitle');
  const obj = document.getElementById('latestAlertObject');
  const reason = document.getElementById('latestAlertReason');
  const time = document.getElementById('latestAlertTime');

  if (!box || !badge || !title || !obj || !reason || !time) return;

  const sev = (alert.severity || 'LOW').toUpperCase();
  badge.textContent = sev;
  badge.className = 'la-badge ' + sev.toLowerCase();

  title.textContent = alert.event_title || (alert.event_type || 'EVENT').replace(/_/g, ' ');
  obj.textContent = `Track #${alert.track_id} &bull; ${(alert.object_class || 'object').toUpperCase()}`;
  reason.textContent = alert.explanation || alert.message || 'Perimeter activity verified.';
  time.textContent = (alert.timestamp || '').slice(11, 19) || '--:--:--';

  if (sev === 'CRITICAL' || sev === 'HIGH') {
    box.classList.add('threat-active');
  } else {
    box.classList.remove('threat-active');
  }
}

// ── Semantic Alert Feed & Alerts Table ─────────────────────────────────────────
async function fetchAlerts() {
  try {
    const res = await fetch('/api/alerts?limit=60');
    const d = await res.json();
    allAlertsList = d.alerts || [];

    if (allAlertsList.length > 0) {
      const latest = allAlertsList[0];
      if (lastLatestAlertTimestamp !== null && latest.timestamp !== lastLatestAlertTimestamp) {
        const isHighSev = (latest.severity === 'Critical' || latest.severity === 'High');
        showToast('🚨 THREAT VERIFIED: ' + (latest.event_type || '').replace(/_/g, ' '), isHighSev ? 'err' : 'warn');
      }
      lastLatestAlertTimestamp = latest.timestamp;
    }

    renderDashboardAlertFeed(allAlertsList);
    renderAlertsTable(allAlertsList);
  } catch (err) {}
}

function renderDashboardAlertFeed(alerts) {
  const feed = document.getElementById('dashAlertFeed');
  if (!feed) return;

  if (!alerts || alerts.length === 0) {
    feed.innerHTML = '<div class="empty-state">Standby &mdash; monitoring active sector. Verified events will appear here.</div>';
    return;
  }

  feed.innerHTML = alerts.slice(0, 15).map(a => {
    const sev = (a.severity || 'LOW').toUpperCase();
    const eventName = a.event_type ? a.event_type.replace(/_/g, ' ') : 'EVENT';
    const timeStr = (a.timestamp || '').slice(11, 19) || '--:--:--';
    const statement = a.semantic_message || a.explanation || a.message || 'Contextual boundary interaction verified.';
    const objText = `Track #${a.track_id} &bull; ${(a.object_class || 'target').toUpperCase()}`;
    const eventId = a.event_id || `SS-${String(a.id || 0).padStart(5, '0')}`;
    const riskScore = parseInt(a.risk_score || 0, 10);

    let riskColor = '#10b981';
    if (riskScore >= 75) riskColor = '#dc2626';
    else if (riskScore >= 50) riskColor = '#f59e0b';

    return `
      <div class="alert-card ${sev.toLowerCase()}">
        <div class="alert-card-header-row">
          <div style="display: flex; align-items: center; gap: 0.4rem;">
            <span class="alert-event-id">${eventId}</span>
            <span class="severity-pill ${sev.toLowerCase()}">${sev}</span>
          </div>
          <span class="alert-time">${timeStr}</span>
        </div>
        <div class="alert-headline">${eventName}</div>
        <div class="alert-reason">${statement}</div>

        <div class="alert-risk-bar-container">
          <span class="risk-score-text" style="color: ${riskColor};">Risk: ${riskScore}/100</span>
          <div class="risk-bar-track">
            <div class="risk-bar-inner" style="width: ${riskScore}%; background: ${riskColor};"></div>
          </div>
          <button class="btn-packet-open" onclick="openPacketModal(${a.id})">🔍 VIEW PACKET</button>
        </div>

        <div class="alert-meta-bar">
          <span class="meta-item">${objText}</span>
          <span class="meta-item">Zone: <strong>${a.zone_name || 'Restricted Sector'}</strong></span>
          <span class="meta-item">Size: <strong>${a.alert_payload_bytes || 180} B</strong></span>
        </div>
      </div>
    `;
  }).join('');
}

function renderAlertsTable(alerts) {
  const tbody = document.getElementById('alertsTableBody');
  if (!tbody) return;

  let filtered = alerts;
  if (currentSeverityFilter !== 'ALL') {
    filtered = filtered.filter(a => (a.severity || '').toUpperCase() === currentSeverityFilter);
  }

  if (currentStatusFilter !== 'ALL') {
    filtered = filtered.filter(a => (a.alert_status || 'NEW').toUpperCase() === currentStatusFilter);
  }

  const query = (document.getElementById('alertTableSearch')?.value || '').toLowerCase().trim();
  if (query) {
    filtered = filtered.filter(a => {
      const hay = `${a.event_id || ''} ${a.event_type || ''} ${a.object_class || ''} ${a.track_id || ''} ${a.explanation || ''} ${a.severity || ''} ${a.alert_status || ''}`.toLowerCase();
      return hay.includes(query);
    });
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-table-cell">No alerts matching filter criteria.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(a => {
    const sev = (a.severity || 'LOW').toUpperCase();
    const timeStr = (a.timestamp || '').slice(11, 19) || '--:--:--';
    const eventId = a.event_id || `SS-${String(a.id || 0).padStart(5, '0')}`;
    const status = (a.alert_status || 'NEW').toUpperCase();
    const riskScore = parseInt(a.risk_score || 0, 10);

    let statusPillClass = 'new';
    if (status === 'ACKNOWLEDGED') statusPillClass = 'acknowledged';
    if (status === 'RESOLVED') statusPillClass = 'resolved';

    let actionButtons = `
      <button class="btn-tbl-action" onclick="openPacketModal(${a.id})">Packet</button>
    `;
    if (status === 'NEW') {
      actionButtons = `
        <button class="btn-tbl-action ack" onclick="acknowledgeAlert(${a.id})">Ack</button>
        <button class="btn-tbl-action resolve" onclick="resolveAlert(${a.id})">Resolve</button>
        ${actionButtons}
      `;
    } else if (status === 'ACKNOWLEDGED') {
      actionButtons = `
        <button class="btn-tbl-action resolve" onclick="resolveAlert(${a.id})">Resolve</button>
        ${actionButtons}
      `;
    }

    return `
      <tr>
        <td><span class="severity-pill ${sev.toLowerCase()}">${sev}</span></td>
        <td><strong style="font-family: var(--font-mono); color: var(--brand); font-size: 0.72rem;">${eventId}</strong></td>
        <td><strong>${(a.event_type || 'EVENT').replace(/_/g, ' ')}</strong></td>
        <td>${a.object_class || 'target'} <span style="font-family: var(--font-mono); color: var(--text-muted); font-size: 0.65rem;">#${a.track_id}</span></td>
        <td><span style="font-family: var(--font-mono); font-weight: 700; font-size: 0.75rem;">${riskScore}</span><span style="font-size:0.6rem; color:var(--text-muted);">/100</span></td>
        <td style="font-family: var(--font-mono); color: var(--text-dim); font-size: 0.72rem;">${timeStr}</td>
        <td><span class="lifecycle-pill ${statusPillClass}">${status}</span></td>
        <td>
          <div class="table-action-btns">
            ${actionButtons}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function setSeverityFilter(sev, btn) {
  currentSeverityFilter = sev;
  document.querySelectorAll('.filter-group:first-child .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderAlertsTable(allAlertsList);
}

function setStatusFilter(status, btn) {
  currentStatusFilter = status;
  document.querySelectorAll('.filter-group:nth-child(2) .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderAlertsTable(allAlertsList);
}

function filterAlertTable() {
  renderAlertsTable(allAlertsList);
}

function exportAlerts(format) {
  window.open(`/api/export/${format}`, '_blank');
}

// ── Alert Lifecycle Operations ────────────────────────────────────────────────
async function acknowledgeAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      showToast(`Alert #${alertId} acknowledged.`, 'ok');
      fetchAlerts();
      fetchStatus();
    }
  } catch (err) {
    showToast('Failed to acknowledge alert.', 'err');
  }
}

async function resolveAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/resolve`, { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      showToast(`Alert #${alertId} marked resolved.`, 'ok');
      fetchAlerts();
      fetchStatus();
    }
  } catch (err) {
    showToast('Failed to resolve alert.', 'err');
  }
}

// ── Communication Mode Simulator (Severity-Based Priority Queue) ────────────
async function fetchCommMode() {
  try {
    const res = await fetch('/api/comm/mode');
    const d = await res.json();
    activeCommMode = d.mode || 'NORMAL';
    updateCommModeUI(activeCommMode, d.queue_depth || 0, d.priority_breakdown);

    if (activeTab === 'analyzer') {
      fetchOfflineQueue();
    }
  } catch (err) {}
}

function updateCommModeUI(mode, queueDepth, breakdown) {
  const badge = document.getElementById('commStatusBadge');
  const headerPill = document.getElementById('commHeaderPill');
  const queueCount = document.getElementById('commQueueCount');

  // Update button active states
  document.getElementById('btnCommNormal')?.classList.toggle('active', mode === 'NORMAL');
  document.getElementById('btnCommLimited')?.classList.toggle('active', mode === 'LIMITED');
  document.getElementById('btnCommOffline')?.classList.toggle('active', mode === 'OFFLINE');

  if (badge) {
    if (mode === 'NORMAL') {
      badge.textContent = '🟢 NORMAL';
      badge.style.background = '#ecfdf5';
      badge.style.color = '#059669';
      badge.style.borderColor = '#a7f3d0';
    } else if (mode === 'LIMITED') {
      badge.textContent = '🟡 LIMITED';
      badge.style.background = '#fefce8';
      badge.style.color = '#ca8a04';
      badge.style.borderColor = '#fde047';
    } else {
      badge.textContent = '🔴 OFFLINE';
      badge.style.background = '#fef2f2';
      badge.style.color = '#dc2626';
      badge.style.borderColor = '#fca5a5';
    }
  }

  if (headerPill) {
    headerPill.textContent = `COMM: ${mode}`;
  }

  if (queueCount) {
    queueCount.textContent = `${queueDepth} alerts buffered`;
    queueCount.style.color = queueDepth > 0 ? '#dc2626' : '#64748b';
  }

  // Update priority breakdown counters in Dashboard and Analyzer
  if (breakdown) {
    setText('qCountCrit', breakdown.critical || 0);
    setText('qCountHigh', breakdown.high || 0);
    setText('qCountMed', breakdown.medium || 0);
    setText('qCountLow', breakdown.low || 0);

    setText('qCritVal', breakdown.critical || 0);
    setText('qHighVal', breakdown.high || 0);
    setText('qMedVal', breakdown.medium || 0);
    setText('qLowVal', breakdown.low || 0);
    setText('queueTotalCountBadge', `${queueDepth} Total`);
  }
}

async function setCommMode(mode) {
  try {
    const res = await fetch('/api/comm/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    const d = await res.json();
    if (d.success) {
      activeCommMode = d.mode;
      updateCommModeUI(d.mode, d.remaining_queue || 0, d.flushed_breakdown);
      showToast(d.message, 'ok');
      fetchCommMode();
      fetchAlerts();
    }
  } catch (err) {
    showToast('Failed to switch communication mode.', 'err');
  }
}

async function syncOfflineQueue() {
  showToast('Synchronizing buffered alerts in severity priority order...', 'info');
  await setCommMode('NORMAL');
}

async function fetchOfflineQueue() {
  try {
    const res = await fetch('/api/comm/queue');
    const d = await res.json();
    const container = document.getElementById('analyzerQueueList');
    if (!container) return;

    if (d.priority_breakdown) {
      setText('qCritVal', d.priority_breakdown.critical || 0);
      setText('qHighVal', d.priority_breakdown.high || 0);
      setText('qMedVal', d.priority_breakdown.medium || 0);
      setText('qLowVal', d.priority_breakdown.low || 0);
      setText('queueTotalCountBadge', `${d.count || 0} Total`);

      setText('qCountCrit', d.priority_breakdown.critical || 0);
      setText('qCountHigh', d.priority_breakdown.high || 0);
      setText('qCountMed', d.priority_breakdown.medium || 0);
      setText('qCountLow', d.priority_breakdown.low || 0);
    }

    if (!d.queue || d.queue.length === 0) {
      container.innerHTML = '<div class="empty-state">Queue is empty &mdash; all alerts transmitted in real time.</div>';
      return;
    }

    container.innerHTML = d.queue.map(q => {
      const timeStr = (q.timestamp || '').slice(11, 19) || '--:--:--';
      const eventId = q.event_id || 'SS-QUEUED';
      const sev = (q.severity || 'LOW').toUpperCase();
      const tier = q.priority_tier || (sev === 'CRITICAL' ? 'P1' : (sev === 'HIGH' ? 'P2' : (sev === 'MEDIUM' ? 'P3' : 'P4')));
      const tierCls = tier.toLowerCase();
      const eventName = (q.event_type || 'EVENT').replace(/_/g, ' ');
      const target = `${(q.object_class || 'target').toUpperCase()} #${q.track_id || 0}`;

      return `
        <div class="queue-item">
          <div style="display:flex; align-items:center; gap:0.4rem;">
            <span class="priority-badge ${tierCls}">${tier} ${sev}</span>
            <strong style="color: var(--brand); font-family: var(--font-mono); font-size: 0.72rem;">${eventId}</strong>
            <span style="font-weight: 600; color: var(--text-primary);">${eventName}</span>
            <small style="color: var(--text-muted); font-family: var(--font-mono);">(${target})</small>
          </div>
          <div style="display:flex; align-items:center; gap:0.6rem;">
            <span style="font-family: var(--font-mono); color: var(--text-dim); font-size: 0.65rem;">${timeStr}</span>
            <span style="font-family: var(--font-mono); color: #ea580c; font-weight: 700; font-size: 0.7rem;">${q.alert_payload_bytes || 180} B</span>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {}
}

// ── Communication Efficiency & Bandwidth ─────────────────────────────────────
async function fetchCommEfficiency() {
  try {
    const res = await fetch('/api/comm/efficiency');
    const d = await res.json();

    setText('effTotalAlerts', d.total_alerts || 0);
    setText('effTotalKb', (d.total_semantic_kb || 0.0) + ' KB');
    setText('effAvgBytes', Math.round(d.avg_payload_bytes || 185) + ' B');
    setText('effSavedPct', (d.estimated_bandwidth_saved_pct || 99.98) + '%');
  } catch (err) {}
}

async function fetchEdgeHealth() {
  try {
    const res = await fetch('/api/health');
    const d = await res.json();

    const cpuPct = Math.round(d.cpu_percent || 15);
    const ramPct = Math.round(d.memory_percent || 40);

    setText('cpuVal', cpuPct + '%');
    setText('ramVal', ramPct + '%');
    setText('edgeFpsVal', (d.fps || 25) + ' FPS');
    setText('edgeUptimeVal', d.uptime_formatted || '00:00:00');

    const cpuBar = document.getElementById('cpuMeter');
    const ramBar = document.getElementById('ramMeter');
    if (cpuBar) cpuBar.style.width = Math.min(100, Math.max(5, cpuPct)) + '%';
    if (ramBar) ramBar.style.width = Math.min(100, Math.max(5, ramPct)) + '%';
  } catch (err) {}
}

// ── Canonical Demo Scenario Injection ─────────────────────────────────────────
async function injectScenario(scenarioName) {
  try {
    showToast(`Injecting scenario: ${scenarioName.replace(/_/g, ' ').toUpperCase()}`, 'info');
    const res = await fetch(`/api/simulate/scenario/${scenarioName}`, { method: 'POST' });
    const d = await res.json();

    if (d.success && d.alert) {
      showToast(`Simulated: ${d.alert.severity} event triggered.`, 'ok');
      fetchAlerts();
      fetchVideoState();
      fetchStatus();
      fetchCommEfficiency();

      // If simulated track matches, update trend
      if (d.alert.track_id) {
        setTimeout(() => loadThreatTrend(d.alert.track_id), 300);
      }
    } else {
      // Fallback to legacy endpoint if needed
      const resOld = await fetch('/api/simulate/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioName })
      });
      fetchAlerts();
      fetchVideoState();
      fetchStatus();
    }
  } catch (err) {
    showToast('Scenario injection error.', 'err');
  }
}

// ── Semantic Packet Inspector Modal ───────────────────────────────────────────
async function openPacketModal(alertId) {
  currentModalAlertId = alertId;
  const modal = document.getElementById('packetModal');
  if (!modal) return;
  modal.style.display = 'flex';

  try {
    const res = await fetch(`/api/alerts/${alertId}/packet`);
    const d = await res.json();
    if (d.success && d.packet) {
      renderPacketModalData(d.packet);
    }
  } catch (err) {
    showToast('Failed to load semantic packet details.', 'err');
  }
}

function renderPacketModalData(p) {
  setText('modalEventId', p.event_id || `SS-${p.database_id}`);
  setText('modalSemanticMsg', p.semantic_message || p.explanation || 'No message statement provided.');

  const sevPill = document.getElementById('modalSeverity');
  if (sevPill) {
    const s = (p.severity || 'LOW').toUpperCase();
    sevPill.textContent = s;
    sevPill.className = 'severity-pill ' + s.toLowerCase();
  }

  const statPill = document.getElementById('modalStatus');
  if (statPill) {
    const st = (p.alert_status || 'NEW').toUpperCase();
    statPill.textContent = st;
    statPill.className = 'lifecycle-pill ' + (st === 'ACKNOWLEDGED' ? 'acknowledged' : (st === 'RESOLVED' ? 'resolved' : 'new'));
  }

  setText('modalTimestamp', (p.timestamp || '').slice(0, 19).replace('T', ' '));
  setText('modalCamera', p.camera_id || 'SENTINEL-EDGE');
  setText('modalObjectClass', (p.object_class || 'target').toUpperCase());
  setText('modalTrackId', `#${p.track_id}`);
  setText('modalZone', p.zone_name || 'Restricted Sector Alpha');
  setText('modalDuration', `${(p.duration || 0.0).toFixed(1)}s`);
  setText('modalConfidence', p.confidence_pct || `${Math.round((p.confidence || 0) * 100)}%`);
  setText('modalPersistence', `${p.persistence_frames || 0} frames`);

  // Risk Score Gauge & Bar
  const score = parseInt(p.risk_score || 0, 10);
  setText('modalRiskScore', score);
  const bar = document.getElementById('modalRiskBar');
  if (bar) bar.style.width = `${Math.min(100, Math.max(0, score))}%`;

  // Risk reasons checklist
  const reasonsWrap = document.getElementById('modalRiskReasons');
  if (reasonsWrap) {
    const reasons = p.risk_reasons || [];
    if (reasons.length === 0) {
      reasonsWrap.innerHTML = '<div class="check-item">&#9989; Baseline perimeter detection.</div>';
    } else {
      reasonsWrap.innerHTML = reasons.map(r => `
        <div class="check-item">&#128308; <span>${r}</span></div>
      `).join('');
    }
  }

  // Raw compact payload
  setText('modalRawPayload', p.compact_message || '--');
  setText('modalPayloadBytes', `${p.payload_bytes || 180} Bytes`);
}

function closePacketModal() {
  const modal = document.getElementById('packetModal');
  if (modal) modal.style.display = 'none';
  currentModalAlertId = null;
}

function handleBackdropClick(e) {
  if (e.target.id === 'packetModal') {
    closePacketModal();
  }
}

function copySemanticMessage() {
  const text = document.getElementById('modalSemanticMsg')?.textContent || '';
  if (!text) return;
  navigator.clipboard.writeText(text.trim()).then(() => {
    showToast('Semantic message copied to clipboard.', 'ok');
  }).catch(() => {
    showToast('Could not copy to clipboard.', 'warn');
  });
}

async function ackModalAlert() {
  if (!currentModalAlertId) return;
  await acknowledgeAlert(currentModalAlertId);
  openPacketModal(currentModalAlertId);
}

async function resolveModalAlert() {
  if (!currentModalAlertId) return;
  await resolveAlert(currentModalAlertId);
  openPacketModal(currentModalAlertId);
}

// ── Analyzer Tab: Tactical 2D Situation Canvas ────────────────────────────────
function renderTacticalCanvas(tracks, zones) {
  const canvas = document.getElementById('tacticalMapCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  // Background
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, w, h);

  // Tactical Radar Grid & Crosshairs
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  const step = 40;
  for (let x = step; x < w; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = step; y < h; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // Concentric Radar Rings
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
  const cx = w / 2;
  const cy = h / 2;
  [50, 100, 150].forEach(r => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
  });

  // Draw Camera FOV Arc
  ctx.beginPath();
  ctx.moveTo(cx, h - 10);
  ctx.lineTo(cx - 180, 20);
  ctx.lineTo(cx + 180, 20);
  ctx.closePath();
  ctx.fillStyle = 'rgba(37, 99, 235, 0.04)';
  ctx.fill();

  // Draw Restricted Zones
  const zList = (zones && zones.length > 0) ? zones : [{
    polygon: [[0.18, 0.25], [0.82, 0.25], [0.82, 0.85], [0.18, 0.85]],
    zone_name: 'Restricted Sector Alpha'
  }];

  zList.forEach(z => {
    const poly = z.polygon || [];
    if (poly.length < 3) return;

    ctx.beginPath();
    ctx.moveTo(poly[0][0] * w, poly[0][1] * h);
    for (let i = 1; i < poly.length; i++) {
      ctx.lineTo(poly[i][0] * w, poly[i][1] * h);
    }
    ctx.closePath();

    ctx.fillStyle = 'rgba(239, 68, 68, 0.12)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.65)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Zone label
    ctx.fillStyle = 'rgba(239, 68, 68, 0.8)';
    ctx.font = '10px "Space Mono", monospace';
    ctx.fillText(z.zone_name || 'Restricted Sector', poly[0][0] * w + 6, poly[0][1] * h + 14);
  });

  // Draw Track Points
  const tCount = tracks ? tracks.length : 0;
  setText('tacticalTrackCount', `${tCount} Track${tCount === 1 ? '' : 's'}`);

  if (tracks && tracks.length > 0) {
    tracks.forEach(t => {
      const pos = t.norm_pos || [0.5, 0.5];
      const tx = pos[0] * w;
      const ty = pos[1] * h;
      const isThreat = t.state === 'INSIDE' || t.state === 'ENTERED';
      const isBag = t.class === 'backpack' || t.class === 'suitcase';

      let dotColor = '#38bdf8';
      if (isThreat) dotColor = '#ef4444';
      else if (isBag) dotColor = '#f59e0b';

      // Pulsing outer ring
      ctx.beginPath();
      ctx.arc(tx, ty, 9, 0, Math.PI * 2);
      ctx.fillStyle = isThreat ? 'rgba(239, 68, 68, 0.25)' : 'rgba(56, 189, 248, 0.2)';
      ctx.fill();

      // Solid inner core
      ctx.beginPath();
      ctx.arc(tx, ty, 4, 0, Math.PI * 2);
      ctx.fillStyle = dotColor;
      ctx.fill();

      // Text label
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 9px "Space Mono", monospace';
      ctx.fillText(`#${t.id} ${t.class || ''}`, tx + 7, ty - 4);
    });
  }
}

// ── Analyzer Tab: Threat Progression & Chronology ─────────────────────────────
async function loadThreatTrend(trackId) {
  if (!trackId) return;

  try {
    const resTrend = await fetch(`/api/threat/trend/${trackId}`);
    const dTrend = await resTrend.json();
    renderThreatTrendBars(dTrend.timeline || []);

    const resTimeline = await fetch(`/api/timeline/${trackId}`);
    const dTimeline = await resTimeline.json();
    renderTrackTimelineList(dTimeline.events || []);
  } catch (err) {}
}

function renderThreatTrendBars(timeline) {
  const container = document.getElementById('threatTrendContainer');
  if (!container) return;

  if (!timeline || timeline.length === 0) {
    container.innerHTML = '<div class="trend-empty">No threat history recorded for this Track ID yet.</div>';
    return;
  }

  container.innerHTML = timeline.map((pt, idx) => {
    const score = parseInt(pt.risk_score || 10, 10);
    const heightPx = Math.max(12, Math.round((score / 100) * 65));
    let color = '#10b981';
    if (score >= 75) color = '#dc2626';
    else if (score >= 50) color = '#f59e0b';

    return `
      <div class="trend-col">
        <span class="trend-score-lbl" style="color: ${color};">${score}</span>
        <div class="trend-bar-elem" style="height: ${heightPx}px; background: ${color};"></div>
        <span class="trend-step-lbl">T+${idx + 1}</span>
      </div>
    `;
  }).join('');
}

function renderTrackTimelineList(events) {
  const container = document.getElementById('trackTimelineFeed');
  if (!container) return;

  if (!events || events.length === 0) {
    container.innerHTML = '<div class="empty-state">No recorded history for this track ID yet.</div>';
    return;
  }

  container.innerHTML = events.map(e => {
    const t = (e.timestamp || '').slice(11, 19) || '--:--:--';
    const sev = (e.severity || 'LOW').toUpperCase();
    const eventName = (e.event_type || 'EVENT').replace(/_/g, ' ');
    return `
      <div class="timeline-row">
        <span class="timeline-t">${t}</span>
        <span class="severity-pill ${sev.toLowerCase()}" style="font-size: 0.55rem; padding: 1px 4px;">${sev}</span>
        <div style="flex:1;">
          <strong>${eventName}</strong>: ${e.explanation || e.message || 'Logged event.'}
        </div>
      </div>
    `;
  }).join('');
}

// ── Video Controls ────────────────────────────────────────────────────────────
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
      showToast('Video Analysis Stopped.', 'warn');
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

// ── Video Source Switching ──────────────────────────────────────────────────
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

// ── Restricted Zone Drawing ───────────────────────────────────────────────────
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
    showToast('Click points on the video to define the zone. Double-click to save.', 'info');
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
  drawnPoints.pop();

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

    drawnPoints.forEach((p, idx) => {
      ctx.beginPath();
      ctx.arc(p[0] * w, p[1] * h, 5, 0, Math.PI * 2);
      ctx.fillStyle = idx === 0 ? '#ef4444' : '#00d4ff';
      ctx.fill();
    });
  }
}

// ── Settings ──────────────────────────────────────────────────────────────────
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
