import { config } from './config.js';
import { engine } from './hud-engine.js';
import { api } from './api.js';
import { wsClient } from './ws.js';
import { audio } from './audio.js';
import { diary } from './diary.js';
import { syncManager } from './sync.js';
import { notifications } from './notifications.js';
import { statusBar } from '../ui/status-bar.js';
import { panels } from '../ui/panels.js';
import { modeTabs } from '../ui/mode-tabs.js';
import { queryBar } from '../ui/query-bar.js';
import { visorLayout } from '../ui/visor-layout.js';
import { copilotLayout } from '../ui/copilot-layout.js';
import { desktopLayout } from '../ui/desktop-layout.js';

/* ── DOM refs ────────────────────────────────── */
const $ = id => document.getElementById(id);
const dom = {
  setup:        $('setup-overlay'),
  setupProvider:$('setup-provider'),
  setupCustomUrl:$('setup-custom-url'),
  setupCustomUrlGroup:$('setup-custom-url-group'),
  setupKey:     $('setup-api-key'),
  setupServer:  $('setup-server-url'),
  setupCache:   $('setup-cache-models'),
  setupSyncAuto:$('setup-sync-auto'),
  setupDiarySave:$('setup-diary-save'),
  setupContinue:$('setup-continue'),
  setupError:   $('setup-error'),
  setupAdvanced: $('setup-advanced-fields'),
  setupToggleAdvanced: $('setup-toggle-advanced'),
  picker:       $('picker-overlay'),
  pickVisor:    $('pick-visor'),
  pickCopilot:  $('pick-copilot'),
  app:          $('app'),
};

/* ── Setup screen ────────────────────────────── */
dom.setupToggleAdvanced.addEventListener('click', () => {
  const hidden = dom.setupAdvanced.classList.contains('hidden');
  dom.setupAdvanced.classList.toggle('hidden');
  dom.setupToggleAdvanced.textContent = hidden ? '- Advanced' : '+ Advanced';
});

dom.setupProvider.addEventListener('change', () => {
  const show = dom.setupProvider.value === 'custom';
  dom.setupCustomUrlGroup.classList.toggle('hidden', !show);
});

// Fill saved values
if (config.get('apiKey')) dom.setupKey.value = config.get('apiKey');
if (config.get('serverUrl')) dom.setupServer.value = config.get('serverUrl');
if (config.get('provider')) dom.setupProvider.value = config.get('provider');
if (config.get('baseUrl')) dom.setupCustomUrl.value = config.get('baseUrl');

dom.setupContinue.addEventListener('click', async () => {
  const provider = dom.setupProvider.value;
  const apiKey = dom.setupKey.value.trim();
  const baseUrl = dom.setupCustomUrl.value.trim();
  const serverUrl = dom.setupServer.value.trim();

  config.set('provider', provider);
  config.set('apiKey', apiKey);
  config.set('baseUrl', baseUrl);
  config.set('serverUrl', serverUrl);
  config.set('cacheModels', dom.setupCache.checked);
  config.set('syncAuto', dom.setupSyncAuto.checked);
  config.set('diaryAutoSave', dom.setupDiarySave.checked);

  dom.setupError.textContent = '';

  if (!apiKey && !serverUrl) {
    dom.setupError.textContent = 'Enter an API key or server URL';
    return;
  }

  dom.setup.classList.remove('visible');

  // Register SW + install prompt
  notifications.registerSW();
  notifications.listenInstall();

  // Detect platform
  const isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);

  if (!isMobile) {
    // Desktop — go straight to desktop mode
    startApp('desktop');
  } else if (apiKey) {
    // Phone with direct API — show mode picker
    dom.picker.classList.add('visible');
  } else if (serverUrl) {
    // Phone with server — show mode picker
    dom.picker.classList.add('visible');
  } else {
    startApp('visor');
  }
});

/* ── Mode picker ─────────────────────────────── */
dom.pickVisor.addEventListener('click', () => {
  dom.picker.classList.remove('visible');
  startApp('visor');
});

dom.pickCopilot.addEventListener('click', () => {
  dom.picker.classList.remove('visible');
  startApp('copilot');
});

/* ── App start ───────────────────────────────── */
async function startApp(appMode) {
  dom.app.classList.remove('hidden');
  engine.setAppMode(appMode);

  // Connection
  if (config.isServerMode()) {
    wsClient.connect(config.get('serverUrl'));
    engine.setConnection('server');
  } else if (config.isDirectMode()) {
    engine.setConnection('direct');
  }

  // Audio
  try {
    await audio.start();
    if (appMode !== 'copilot') {
      audio.startRecording();
    }
    audio.startWakeWord();
    statusBar.setIndicator('mic', true);
  } catch (e) {
    console.warn('[Merlin] Mic not available:', e.message);
  }

  // Layout
  let layout;
  if (appMode === 'visor') {
    layout = visorLayout;
  } else if (appMode === 'copilot') {
    layout = copilotLayout;
  } else {
    layout = desktopLayout;
  }

  await layout.activate();
  queryBar.show();

  // Wake lock
  notifications.requestWakeLock();

  // Diary + sync (standalone-first)
  if ('indexedDB' in window) {
    // Diary is ready. Sync runs in background.
    if (config.get('syncAuto')) {
      syncManager.start();
      syncManager.addEventListener('synced', (e) => {
        const { count } = e.detail;
        if (count > 0) {
          panels.spawn('SYNC', count + ' entries synced to server', '#4ADE80');
        }
      });
    }
  }

  // Intro
  const unsyncedCount = await diary.countUnsynced().catch(() => 0);
  panels.spawn(
    'MERLIN — ' + appMode.toUpperCase(),
    (appMode === 'visor'
      ? 'Visor active. Camera is your eyes. Tap to observe, speak to ask.'
      : appMode === 'copilot'
        ? 'Copilot active. Share your screen, then enable WATCH for AI observation.'
        : 'Desktop mode active. Share your screen and ask anything.')
      + (unsyncedCount > 0 ? '\n\n' + unsyncedCount + ' entries queued for sync.' : ''),
    engine.getMode()?.color || '#00e5ff'
  );

  // Observe handler
  engine.addEventListener('userObserve', async (e) => {
    const { frame } = e.detail;
    const mode = engine.activityMode;
    const modeCfg = engine.getMode();

    const panelId = panels.spawn(
      'OBSERVE — ' + mode,
      '…',
      modeCfg?.color || '#00e5ff'
    );

    try {
      const result = await api.chatWithVision([
        {
          role: 'system',
          content: `You are Merlin in ${mode} mode. Look at what the user is pointing at. Describe it briefly and offer a useful observation. 1-3 sentences.`,
        },
        { role: 'user', content: 'What do you see?' },
      ], frame, { maxTokens: 300 });

      const text = result.content || '(nothing detected)';
      const time = new Date().toLocaleTimeString();
      panels.update(panelId, text);
      engine.dispatch('aiResponse', { text, timestamp: time });

      // Save to diary
      if ('indexedDB' in window) {
        await diary.addObservation(frame, mode, text);
      }
    } catch (e) {
      panels.update(panelId, 'Error: ' + e.message);
    }
  });

  // Auto-observe timer
  if (engine.getMode()?.observeMs) {
    setInterval(() => {
      if (engine.getMode()?.observeMs) {
        engine.dispatch('userObserve', { frame: layout.captureFrame() });
      }
    }, engine.getMode().observeMs);
  }
}

/* ── PWA Install via status bar ──────────────── */
setInterval(() => {
  if (notifications.canInstall()) {
    if (!document.querySelector('#install-btn')) {
      const btn = document.createElement('button');
      btn.id = 'install-btn';
      btn.textContent = '📲 INSTALL';
      btn.addEventListener('click', () => notifications.promptInstall());
      document.getElementById('status-bar')?.appendChild(btn);
    }
  } else {
    document.querySelector('#install-btn')?.remove();
  }
}, 5000);
