/* ── Merlin HUD — hud.js ──────────────────────────────────────────────────── */
'use strict';

// ── Mode definitions ─────────────────────────────────────────────────────────

const MODES = {
  SCOUT: {
    color: '#00e5ff',
    frameHz: 0.5,
    audio: true,
    gps: true,
    autoObserveMs: 15_000,
    label: 'SCOUT',
    purpose: 'Environmental awareness',
  },
  NAV: {
    color: '#00e676',
    frameHz: 0.2,
    audio: false,
    gps: true,
    autoObserveMs: 30_000,
    label: 'NAV',
    purpose: 'GPS / location context',
  },
  ANALYZE: {
    color: '#ffab40',
    frameHz: 1.0,
    audio: false,
    gps: false,
    autoObserveMs: null,
    label: 'ANALYZE',
    purpose: 'Deep visual analysis + exercise counting',
  },
  LISTEN: {
    color: '#e040fb',
    frameHz: 0.1,
    audio: true,
    gps: false,
    autoObserveMs: 10_000,
    label: 'LISTEN',
    purpose: 'Audio transcription + response',
  },
  QUERY: {
    color: '#ff6e40',
    frameHz: 0.5,
    audio: true,
    gps: true,
    autoObserveMs: null,
    label: 'QUERY',
    purpose: 'Text / voice Q&A, agent file tools',
  },
  RECON: {
    color: '#546e7a',
    frameHz: 0.1,
    audio: false,
    gps: true,
    autoObserveMs: null,
    label: 'RECON',
    purpose: 'Silent collection, minimal HUD',
  },
};

// ── PanelManager ──────────────────────────────────────────────────────────────

const PanelManager = {
  maxPanels: 5,

  spawn(title, content, accent, panelId) {
    const id = panelId || 'panel-' + Date.now();
    this._remove(id);

    const container = document.getElementById('panel-container');
    const panel = document.createElement('div');
    panel.className = 'hud-panel';
    panel.dataset.panelId = id;
    if (accent) panel.style.borderTopColor = accent;

    panel.innerHTML =
      '<div class="panel-header">' +
        '<span class="panel-title">' + this._esc(title) + '</span>' +
        '<button class="panel-close" data-pid="' + id + '">✕</button>' +
      '</div>' +
      '<div class="panel-body">' + this._esc(content) + '</div>';

    const closeBtn = panel.querySelector('.panel-close');
    closeBtn.addEventListener('click', () => this.close(id));
    closeBtn.addEventListener('touchend', (e) => { e.preventDefault(); this.close(id); });

    container.appendChild(panel);

    requestAnimationFrame(() => panel.classList.add('visible'));

    this._prune();
    return id;
  },

  update(id, content) {
    const body = document.querySelector('[data-panel-id="' + id + '"] .panel-body');
    if (body) body.textContent = content;
  },

  close(id) {
    const el = document.querySelector('[data-panel-id="' + id + '"]');
    if (!el) return;
    el.classList.remove('visible');
    setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 350);
  },

  closeAll() {
    document.querySelectorAll('.hud-panel').forEach(p => {
      p.classList.remove('visible');
      setTimeout(() => { if (p.parentNode) p.parentNode.removeChild(p); }, 350);
    });
  },

  _remove(id) {
    const existing = document.querySelector('[data-panel-id="' + id + '"]');
    if (existing) existing.remove();
  },

  _prune() {
    const panels = document.querySelectorAll('.hud-panel');
    while (panels.length > this.maxPanels) {
      const first = panels[0];
      first.classList.remove('visible');
      setTimeout(() => { if (first.parentNode) first.parentNode.removeChild(first); }, 350);
      panels.length = panels.length - 1; // crude but works in loop
    }
  },

  _esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  },
};

// ── State ─────────────────────────────────────────────────────────────────────

let currentMode = 'SCOUT';
let ws = null;
let videoStream = null;
let mediaRecorder = null;
let gpsWatchId = null;
let frameTimer = null;
let audioTimer = null;
let autoObserveTimer = null;
let lastGps = null;
let lastImu = null;
let poseEnabled = false;

const pendingPhoneFiles = {};

// ── DOM refs ──────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

const dom = {
  camera:        $('camera'),
  scanlines:     $('scanlines'),
  statusMode:    $('status-mode'),
  statusTime:    $('status-time'),
  indWs:         $('ind-ws'),
  indCam:        $('ind-cam'),
  indGps:        $('ind-gps'),
  indMic:        $('ind-mic'),
  indVoice:      $('ind-voice'),
  readoutGps:    $('readout-gps'),
  readoutImu:    $('readout-imu'),
  readoutSpd:    $('readout-spd'),
  panelContainer:$('panel-container'),
  wakeIndicator: $('wake-indicator'),
  modeTabs:      $('mode-tabs'),
  queryBar:      $('query-bar'),
  queryInput:    $('query-input'),
  querySend:     $('query-send'),
  tapHint:       $('tap-hint'),
  connectOverlay:$('connect-overlay'),
  wsUrl:         $('ws-url'),
  connectBtn:    $('connect-btn'),
  connectError:  $('connect-error'),
  filePicker:    $('file-picker'),
};

// ── Clock ─────────────────────────────────────────────────────────────────────

setInterval(() => {
  const now = new Date();
  dom.statusTime.textContent =
    String(now.getHours()).padStart(2,'0') + ':' +
    String(now.getMinutes()).padStart(2,'0');
}, 1000);

// ── Mode switching ─────────────────────────────────────────────────────────────

function setMode(mode) {
  if (!MODES[mode]) return;

  const prev = currentMode;
  currentMode = mode;
  const cfg = MODES[mode];

  document.documentElement.style.setProperty('--mode-color', cfg.color);
  document.body.className = 'mode-' + mode;
  dom.statusMode.textContent = mode;

  dom.modeTabs.querySelectorAll('.mode-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });

  dom.queryBar.classList.toggle('visible', mode === 'QUERY');

  restartStreamingIntervals();
  restartAutoObserveTimer();
  sendJson({ type: 'mode_change', mode });

  // Enable/disable pose tracking
  if (mode === 'ANALYZE') {
    enablePoseDetection(true);
  } else {
    enablePoseDetection(false);
  }

  console.log('[Merlin] Mode:', prev, '→', mode);
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

function connect(url) {
  dom.connectError.textContent = '';
  dom.connectBtn.textContent = 'CONNECTING…';
  dom.connectBtn.disabled = true;

  try { ws = new WebSocket(url); } catch (e) {
    showConnectError('Invalid WebSocket URL');
    return;
  }

  ws.addEventListener('open', () => {
    console.log('[Merlin] WebSocket connected');
    setIndicator(dom.indWs, true);
    dom.connectOverlay.classList.add('hidden');
    dom.connectBtn.textContent = 'CONNECT';
    dom.connectBtn.disabled = false;
    localStorage.setItem('merlin_ws_url', url);
  });

  ws.addEventListener('message', e => {
    try {
      const msg = JSON.parse(e.data);
      handleServerMessage(msg);
    } catch { console.warn('[Merlin] Unparseable server message'); }
  });

  ws.addEventListener('close', () => {
    console.log('[Merlin] WebSocket disconnected');
    setIndicator(dom.indWs, false);
    ws = null;
    setTimeout(() => {
      const savedUrl = localStorage.getItem('merlin_ws_url');
      if (savedUrl) connect(savedUrl);
    }, 3000);
  });

  ws.addEventListener('error', () => {
    showConnectError('Connection failed');
    dom.connectBtn.textContent = 'CONNECT';
    dom.connectBtn.disabled = false;
    ws = null;
  });
}

function sendJson(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

function sendBinary(header, blob) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const headerBytes = new TextEncoder().encode(JSON.stringify(header) + '\n');
  blob.arrayBuffer().then(buf => {
    const combined = new Uint8Array(headerBytes.byteLength + buf.byteLength);
    combined.set(headerBytes, 0);
    combined.set(new Uint8Array(buf), headerBytes.byteLength);
    ws.send(combined.buffer);
  }).catch(e => console.warn('[Merlin] Binary send failed:', e));
}

// ── Server message handler ────────────────────────────────────────────────────

let typewriterTimer = null;

function handleServerMessage(msg) {
  switch (msg.type) {
    case 'response':
      PanelManager.spawn(
        'MERLIN — ' + (msg.mode || currentMode),
        msg.text,
        MODES[msg.mode || currentMode]?.color
      );
      break;

    case 'transcription':
      PanelManager.spawn('TRANSCRIPTION', msg.text, MODES.LISTEN.color);
      break;

    case 'translation':
      PanelManager.spawn(
        'TRANSLATION ' + (msg.source_lang || '').toUpperCase() + ' → ' + (msg.target_lang || '').toUpperCase(),
        msg.original + '\n→ ' + msg.translated,
        '#ffab40'
      );
      break;

    case 'navigation_update':
      PanelManager.spawn(
        'NAVIGATION',
        (msg.instruction || '') + (msg.distance_m ? ' (' + msg.distance_m.toFixed(0) + 'm)' : ''),
        '#00e676'
      );
      break;

    case 'status':
      console.log('[Merlin] Server status:', msg);
      break;

    case 'request_file':
      handlePhoneFileRequest(msg.path);
      break;

    case 'panel_command':
      handlePanelCommand(msg);
      break;

    case 'exercise_update':
      PanelManager.spawn(
        'EXERCISE — ' + (msg.exercise || '').toUpperCase(),
        msg.reps + ' reps completed\nRecent sets: ' + (msg.recent_sets || 1),
        '#00e676'
      );
      break;

    default:
      console.debug('[Merlin] Unknown msg type:', msg.type);
  }
}

function handlePanelCommand(msg) {
  switch (msg.action) {
    case 'show':
      PanelManager.spawn(msg.title || 'MERLIN', msg.content || '', msg.accent, msg.panel_id);
      break;
    case 'update':
      PanelManager.update(msg.panel_id, msg.content || '');
      break;
    case 'close':
      PanelManager.close(msg.panel_id);
      break;
    case 'close_all':
      PanelManager.closeAll();
      break;
  }
}

// ── Wake word detection ───────────────────────────────────────────────────────

let wakeRecognition = null;
let wakeActive = false;

function startWakeWordDetection() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    console.log('[Merlin] Speech recognition not available');
    return;
  }

  wakeRecognition = new SR();
  wakeRecognition.continuous = true;
  wakeRecognition.interimResults = true;
  wakeRecognition.lang = 'en-US';

  wakeRecognition.onresult = (e) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      const textRaw = r[0].transcript;
      const text = textRaw.toLowerCase().trim();

      // In LISTEN mode, forward all speech for real-time subtitles
      if (currentMode === 'LISTEN' && textRaw.trim()) {
        sendJson({ type: 'transcription', text: textRaw, is_final: r.isFinal, mode: currentMode });
      }

      // Check for wake word (only on final results)
      if (!r.isFinal || !text.includes('merlin')) continue;

      // Wake word detected
      setIndicator(dom.indVoice, true);
      dom.wakeIndicator.classList.add('active');

      const idx = text.indexOf('merlin') + 6;
      const command = text.slice(idx).trim();

      if (command) {
        sendJson({ type: 'query', text: command, mode: currentMode });
        console.log('[Merlin] Wake command:', command);
        setTimeout(() => {
          dom.wakeIndicator.classList.remove('active');
          setIndicator(dom.indVoice, false);
        }, 2000);
      } else {
        dom.wakeIndicator.textContent = 'SAY COMMAND';
        setTimeout(() => {
          dom.wakeIndicator.classList.remove('active');
          dom.wakeIndicator.textContent = 'LISTENING';
          setIndicator(dom.indVoice, false);
        }, 5000);
      }
    }
  };

  wakeRecognition.onend = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      setTimeout(() => {
        try { wakeRecognition.start(); } catch (_) {}
      }, 200);
    }
  };

  wakeRecognition.onerror = (err) => {
    if (err.error !== 'no-speech' && err.error !== 'aborted') {
      console.warn('[Merlin] Wake word error:', err.error);
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      setTimeout(() => {
        try { wakeRecognition.start(); } catch (_) {}
      }, 2000);
    }
  };

  try {
    wakeRecognition.start();
    console.log('[Merlin] Wake word detection active');
  } catch (e) {
    console.warn('[Merlin] Failed to start wake word:', e);
    setTimeout(startWakeWordDetection, 2000);
  }
}

// ── Pose estimation (MoveNet) ─────────────────────────────────────────────────

let poseDetector = null;
let poseFrameTimer = null;

async function ensurePoseDetector() {
  if (poseDetector) return true;
  if (!window.poseDetection) {
    console.log('[Merlin] MoveNet not loaded');
    return false;
  }
  try {
    poseDetector = await window.poseDetection.createDetector(
      window.poseDetection.SupportedModels.MoveNet,
      { modelType: window.poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING }
    );
    console.log('[Merlin] Pose detector ready');
    return true;
  } catch (e) {
    console.warn('[Merlin] Pose detector error:', e);
    return false;
  }
}

async function detectPose() {
  if (!poseDetector || !dom.camera.videoWidth) return null;
  try {
    const poses = await poseDetector.estimatePoses(dom.camera);
    if (poses && poses.length > 0) {
      return poses[0].keypoints.map(kp => ({
        x: kp.x / dom.camera.videoWidth,
        y: kp.y / dom.camera.videoHeight,
        score: kp.score,
      }));
    }
  } catch (e) {}
  return null;
}

function enablePoseDetection(on) {
  if (poseFrameTimer) {
    clearInterval(poseFrameTimer);
    poseFrameTimer = null;
  }
  poseEnabled = on;
  if (!on) return;

  ensurePoseDetector().then(ready => {
    if (!ready) return;
    // Send pose keypoints at ~5 fps
    poseFrameTimer = setInterval(async () => {
      if (!poseEnabled) return;
      const kps = await detectPose();
      if (kps && kps.length >= 17) {
        sendJson({ type: 'pose', keypoints: kps, ts: Date.now(), mode: currentMode });
      }
    }, 200);
  });
}

// ── Camera ────────────────────────────────────────────────────────────────────

async function startCamera() {
  try {
    videoStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    dom.camera.srcObject = videoStream;
    setIndicator(dom.indCam, true);
    console.log('[Merlin] Camera started');
  } catch (e) {
    console.error('[Merlin] Camera error:', e);
    setIndicator(dom.indCam, false);
  }
}

// ── Frame capture ─────────────────────────────────────────────────────────────

const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');

function captureFrame() {
  const video = dom.camera;
  if (!video.videoWidth || !video.videoHeight) return;

  const MAX_W = 640;
  const scale = Math.min(1, MAX_W / video.videoWidth);
  canvas.width  = Math.round(video.videoWidth  * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(blob => {
    if (!blob) return;
    sendBinary({ type: 'frame', ts: Date.now(), mode: currentMode }, blob);
  }, 'image/jpeg', 0.65);
}

function restartStreamingIntervals() {
  if (frameTimer) clearInterval(frameTimer);
  const cfg = MODES[currentMode];
  const frameMs = Math.round(1000 / cfg.frameHz);
  frameTimer = setInterval(captureFrame, frameMs);

  if (audioTimer) clearTimeout(audioTimer);
  restartAudio();
}

// ── Audio ─────────────────────────────────────────────────────────────────────

async function startAudio() {
  const cfg = MODES[currentMode];
  if (!cfg.audio) return null;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    setIndicator(dom.indMic, true);
    return stream;
  } catch (e) {
    console.warn('[Merlin] Mic error:', e);
    setIndicator(dom.indMic, false);
    return null;
  }
}

let audioStream = null;

async function restartAudio() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  if (audioStream) {
    audioStream.getTracks().forEach(t => t.stop());
    audioStream = null;
  }

  const cfg = MODES[currentMode];
  if (!cfg.audio) {
    setIndicator(dom.indMic, false);
    return;
  }

  audioStream = await startAudio();
  if (!audioStream) return;

  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm';

  mediaRecorder = new MediaRecorder(audioStream, { mimeType });
  const chunks = [];

  mediaRecorder.addEventListener('dataavailable', e => {
    if (e.data.size > 0) chunks.push(e.data);
  });

  mediaRecorder.addEventListener('stop', () => {
    if (chunks.length > 0) {
      const blob = new Blob(chunks, { type: mimeType });
      chunks.length = 0;
      sendBinary({ type: 'audio', ts: Date.now(), mode: currentMode }, blob);
    }
    if (MODES[currentMode]?.audio) {
      setTimeout(restartAudio, 200);
    }
  });

  mediaRecorder.start();
  setTimeout(() => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
    }
  }, 4000);
}

// ── IMU ───────────────────────────────────────────────────────────────────────

function startImu() {
  if (typeof DeviceMotionEvent === 'undefined') return;

  if (typeof DeviceMotionEvent.requestPermission === 'function') {
    DeviceMotionEvent.requestPermission().catch(() => {});
  }

  window.addEventListener('devicemotion', e => {
    const a = e.accelerationIncludingGravity || {};
    const g = e.rotationRate || {};
    const imu = {
      type: 'imu',
      ts: Date.now(),
      ax: a.x, ay: a.y, az: a.z,
      gx: g.alpha, gy: g.beta, gz: g.gamma,
      mode: currentMode,
    };
    lastImu = imu;
    sendJson(imu);

    if (a.x != null) {
      dom.readoutImu.textContent =
        'IMU: ' + (a.x||0).toFixed(1) + '/' + (a.y||0).toFixed(1) + '/' + (a.z||0).toFixed(1);
    }
  }, { passive: true });
}

// ── GPS ───────────────────────────────────────────────────────────────────────

function startGps() {
  if (!navigator.geolocation) return;

  gpsWatchId = navigator.geolocation.watchPosition(pos => {
    const { latitude, longitude, altitude, accuracy, speed } = pos.coords;
    lastGps = { lat: latitude, lon: longitude, alt: altitude, acc: accuracy, speed };

    const cfg = MODES[currentMode];
    if (cfg.gps) {
      sendJson({ type: 'gps', ts: Date.now(), mode: currentMode, ...lastGps });
    }

    setIndicator(dom.indGps, true);
    dom.readoutGps.textContent =
      latitude.toFixed(4) + ', ' + longitude.toFixed(4);
    dom.readoutSpd.textContent =
      speed != null ? (speed * 3.6).toFixed(1) + ' km/h' : 'SPD: --';
  }, err => {
    console.warn('[Merlin] GPS error:', err.message);
    setIndicator(dom.indGps, false);
    dom.readoutGps.textContent = 'GPS: error';
  }, {
    enableHighAccuracy: true,
    maximumAge: 5000,
    timeout: 15000,
  });
}

// ── Auto-observe timer ─────────────────────────────────────────────────────────

function restartAutoObserveTimer() {
  if (autoObserveTimer) {
    clearInterval(autoObserveTimer);
    autoObserveTimer = null;
  }

  const cfg = MODES[currentMode];
  if (cfg.autoObserveMs) {
    autoObserveTimer = setInterval(() => {
      sendJson({ type: 'observe', mode: currentMode });
    }, cfg.autoObserveMs);
  }
}

// ── ANALYZE mode — tap to analyze ─────────────────────────────────────────────

document.addEventListener('click', e => {
  if (currentMode !== 'ANALYZE') return;
  if (e.target.closest('#mode-tabs, #panel-container, #status-bar, #query-bar, #connect-overlay')) return;

  captureFrame();
  sendJson({ type: 'observe', mode: 'ANALYZE' });

  const flash = document.createElement('div');
  flash.style.cssText = 'position:fixed;inset:0;background:rgba(255,171,64,0.15);pointer-events:none;z-index:50;transition:opacity 0.4s';
  document.body.appendChild(flash);
  requestAnimationFrame(() => {
    flash.style.opacity = '0';
    setTimeout(() => flash.remove(), 400);
  });
});

// ── Mode tab clicks ───────────────────────────────────────────────────────────

dom.modeTabs.addEventListener('click', e => {
  const tab = e.target.closest('.mode-tab');
  if (tab && tab.dataset.mode) {
    setMode(tab.dataset.mode);
  }
});

// ── Query submission ──────────────────────────────────────────────────────────

function submitQuery() {
  const text = dom.queryInput.value.trim();
  if (!text) return;
  dom.queryInput.value = '';
  sendJson({ type: 'query', text, mode: currentMode });
  PanelManager.spawn('MERLIN — ' + currentMode, '…', MODES[currentMode]?.color);
}

dom.querySend.addEventListener('click', submitQuery);
dom.queryInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') submitQuery();
});

// ── Phone file access ─────────────────────────────────────────────────────────

function handlePhoneFileRequest(path) {
  console.log('[Merlin] Server requests phone file:', path);
  PanelManager.spawn('FILE REQUEST', path + '\nTap to select file…', '#ff6e40');

  dom.filePicker.onchange = () => {
    const file = dom.filePicker.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
      const content = e.target.result;
      sendJson({ type: 'file_content', path, content: content.toString() });
    };
    reader.onerror = () => {
      sendJson({ type: 'file_content', path, content: '', error: 'read error' });
    };
    reader.readAsText(file);
  };
  dom.filePicker.click();
}

function sendDirectoryListing(dirPath) {
  sendJson({ type: 'file_list', path: dirPath, entries: [] });
}

// ── Indicators ────────────────────────────────────────────────────────────────

function setIndicator(el, active) {
  el.classList.toggle('active', active);
}

function showConnectError(msg) {
  dom.connectError.textContent = msg;
  dom.connectBtn.textContent = 'CONNECT';
  dom.connectBtn.disabled = false;
}

// ── Connect flow ──────────────────────────────────────────────────────────────

dom.connectBtn.addEventListener('click', async () => {
  const url = dom.wsUrl.value.trim() || dom.wsUrl.placeholder;
  if (!url.startsWith('ws://') && !url.startsWith('wss://')) {
    showConnectError('URL must start with ws:// or wss://');
    return;
  }

  await startCamera();
  startImu();
  startGps();

  connect(url);

  restartStreamingIntervals();
  restartAutoObserveTimer();

  // Start wake word detection after connecting
  setTimeout(startWakeWordDetection, 2000);
});

dom.wsUrl.addEventListener('keydown', e => {
  if (e.key === 'Enter') dom.connectBtn.click();
});

// ── Initialisation ────────────────────────────────────────────────────────────

(function init() {
  setMode('SCOUT');

  const savedUrl = localStorage.getItem('merlin_ws_url');
  if (savedUrl) dom.wsUrl.value = savedUrl;

  if ('wakeLock' in navigator) {
    navigator.wakeLock.request('screen').catch(() => {});
  }

  console.log('[Merlin] HUD ready. Select server URL and tap CONNECT.');
})();
