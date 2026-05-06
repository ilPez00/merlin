/* ── Merlin Desktop HUD — app.js ───────────────────────────────── */

// ── Config ────────────────────────────────────────────────────────

const DEFAULT_WS = 'ws://localhost:8765';
const ACTIVITY_TIMEOUT = 10_000; // ms before panels dim

// ── State ─────────────────────────────────────────────────────────

let ws = null;
let activityTimer = null;
let lastTranscription = '';
let lastTranslation = '';
let suggestionFadeTimer = null;
const SUGGESTION_DISPLAY_MS = 9000;  // how long each suggestion stays visible

// ── DOM refs ──────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const dom = {
  status:        $('status-text'),
  navPanel:      $('nav-panel'),
  navBody:       $('nav-body'),
  aiPanel:       $('ai-panel'),
  aiBody:        $('ai-body'),
  transcriptPan: $('transcription-panel'),
  transcriptBody:$('transcription-body'),
  translatePan:  $('translation-panel'),
  translateBody: $('translation-body'),
};

// ── Electron IPC ──────────────────────────────────────────────────

let isClickThrough = true;
if (window.electronAPI) {
  window.electronAPI.onClickThroughChanged((val) => {
    isClickThrough = val;
    document.body.style.cursor = val ? 'default' : 'default';
  });
}

// ── WebSocket ─────────────────────────────────────────────────────

function connect(url) {
  if (ws) { ws.close(); }

  setStatus('connecting', '⏳ Connecting...');
  console.log('[Merlin HUD] Connecting to', url);

  ws = new WebSocket(url);

  ws.onopen = () => {
    setStatus('connected', '✓ MERLIN HUD');
    console.log('[Merlin HUD] Connected');
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      handleMessage(msg);
    } catch (_) {}
  };

  ws.onclose = () => {
    setStatus('disconnected', '✗ Disconnected');
    console.log('[Merlin HUD] Disconnected');
    ws = null;
    setTimeout(() => connect(url), 3000);
  };

  ws.onerror = () => {
    setStatus('disconnected', '✗ Connection error');
    ws = null;
    setTimeout(() => connect(url), 5000);
  };
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

// ── Message handler ───────────────────────────────────────────────

function handleMessage(msg) {
  markActive();

  switch (msg.type) {
    case 'transcription':
      showTranscription(msg.text, msg.is_final);
      break;

    case 'translation':
      showTranslation(msg);
      break;

    case 'navigation_update':
      showNavigation(msg);
      break;

    case 'response':
      showAIResponse(msg.text, msg.mode);
      break;

    case 'exercise_update':
      showAIResponse(
        `🏋️ ${msg.exercise}: ${msg.reps} reps (${msg.recent_sets} sets)`,
        'EXERCISE'
      );
      break;

    case 'suggestion':
      showSuggestion(msg.text);
      break;

    case 'advisor_state':
      setAdvisorActive(msg.active);
      break;

    case 'status':
      setStatus('connected', `✓ ${msg.model || 'MERLIN HUD'}`);
      break;
  }
}

// ── Transcription subtitles ───────────────────────────────────────

function showTranscription(text, isFinal) {
  const pan = dom.transcriptPan;
  const body = dom.transcriptBody;

  pan.classList.remove('hidden', 'idle');

  if (isFinal) {
    // Keep last few lines as history
    lastTranscription = text;
    const history = body.textContent.split('\n').slice(-4);
    history.push(text);
    body.textContent = history.join('\n');
  } else {
    // Interim result — show as single line with cursor
    body.textContent = text + ' ▋';
  }

  // Auto-scroll to bottom
  body.scrollTop = body.scrollHeight;
}

// ── Translation display ───────────────────────────────────────────

function showTranslation(msg) {
  const pan = dom.translatePan;
  const body = dom.translateBody;

  pan.classList.remove('hidden', 'idle');
  lastTranslation = msg.translated;
  body.textContent = msg.translated;

  if (msg.source_lang && msg.target_lang) {
    const label = pan.querySelector('.panel-label');
    label.textContent = `🌐 ${msg.source_lang.toUpperCase()} → ${msg.target_lang.toUpperCase()}`;
  }
}

// ── Navigation display ────────────────────────────────────────────

function showNavigation(msg) {
  const pan = dom.navPanel;
  const body = dom.navBody;

  pan.classList.remove('hidden', 'idle');

  let html = '';
  if (msg.instruction) {
    const turnIcon = {
      'turn-right': '→',
      'turn-left': '←',
      'straight': '↑',
      'uturn': '↩',
    }[msg.turn] || '•';
    html += `<div style="font-size:16px;font-weight:bold">${turnIcon} ${msg.instruction}</div>`;
  }
  if (msg.distance_m) {
    html += `<div style="font-size:11px;color:var(--hud-dim)">${msg.distance_m.toFixed(0)}m</div>`;
  }
  if (msg.summary) {
    html += `<div style="font-size:10px;color:var(--hud-dim);margin-top:4px">${msg.summary}</div>`;
  }
  body.innerHTML = html;
}

// ── AI response ───────────────────────────────────────────────────

function showAIResponse(text, mode) {
  const pan = dom.aiPanel;
  const body = dom.aiBody;

  pan.classList.remove('hidden', 'idle');

  const label = pan.querySelector('.panel-label');
  label.textContent = `💬 ${mode || 'MERLIN'}`;

  body.textContent = text;
  body.scrollTop = body.scrollHeight;
}

// ── ADVISOR teleprompter ──────────────────────────────────────────

function showSuggestion(text) {
  if (!text || !text.trim()) return;
  const panel = $('suggestion-panel');
  const textEl = $('suggestion-text');

  // Cancel pending fade
  clearTimeout(suggestionFadeTimer);
  panel.classList.remove('hidden', 'fading');

  textEl.textContent = text.trim();

  // Auto-fade after display duration
  suggestionFadeTimer = setTimeout(() => {
    panel.classList.add('fading');
    setTimeout(() => panel.classList.add('hidden'), 1200);
  }, SUGGESTION_DISPLAY_MS);
}

function setAdvisorActive(active) {
  document.body.classList.toggle('advisor-active', active);
  if (!active) {
    clearTimeout(suggestionFadeTimer);
    const panel = $('suggestion-panel');
    panel.classList.add('fading');
    setTimeout(() => {
      panel.classList.add('hidden');
      panel.classList.remove('fading');
    }, 1200);
  }
}

// ── Activity tracking ─────────────────────────────────────────────

function markActive() {
  // Show all panels on activity
  document.querySelectorAll('.hud-panel').forEach(p => p.classList.remove('idle'));

  clearTimeout(activityTimer);
  activityTimer = setTimeout(() => {
    document.querySelectorAll('.hud-panel:not(.hidden)').forEach(p => p.classList.add('idle'));
  }, ACTIVITY_TIMEOUT);
}

// ── Status bar ────────────────────────────────────────────────────

function setStatus(cls, text) {
  dom.status.className = cls;
  dom.status.textContent = text;
}

// ── Connection UI ─────────────────────────────────────────────────

function showConnectDialog() {
  const url = localStorage.getItem('merlin_hud_ws') || DEFAULT_WS;
  const input = prompt('Merlin WebSocket URL:', url);
  if (input) {
    localStorage.setItem('merlin_hud_ws', input);
    connect(input);
  } else {
    setStatus('disconnected', '✗ No server URL');
    setTimeout(showConnectDialog, 5000);
  }
}

// ── Init ──────────────────────────────────────────────────────────

(function init() {
  showConnectDialog();
  console.log('[Merlin HUD] Initialized');
})();
