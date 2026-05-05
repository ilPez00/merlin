import { engine } from '../lib/hud-engine.js';

class StatusBar {
  constructor() {
    this.el = document.getElementById('status-bar');
    this.modeEl = document.getElementById('status-mode');
    this.connEl = document.getElementById('status-connection');
    this.timeEl = document.getElementById('status-time');
    this.indicators = {
      cam: document.getElementById('ind-cam'),
      mic: document.getElementById('ind-mic'),
      gps: document.getElementById('ind-gps'),
    };

    this._startClock();
    this._bindEngine();

    document.documentElement.style.setProperty('--mode-color', engine.getMode()?.color || '#00e5ff');
  }

  setIndicator(name, active) {
    const el = this.indicators[name];
    if (el) el.classList.toggle('active', active);
  }

  setMode(name) {
    this.modeEl.textContent = name;
    const mode = engine.getMode();
    if (mode) {
      document.documentElement.style.setProperty('--mode-color', mode.color);
    }
  }

  setConnection(state) {
    const el = this.connEl;
    el.className = 'dot';
    if (state === 'direct') { el.classList.add('direct'); el.title = 'Direct API'; }
    else if (state === 'server') { el.classList.add('server'); el.title = 'Server'; }
    else { el.classList.add('disconnected'); el.title = 'Disconnected'; }
  }

  _startClock() {
    setInterval(() => {
      const now = new Date();
      this.timeEl.textContent =
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0');
    }, 1000);
  }

  _bindEngine() {
    engine.addEventListener('modeChange', (e) => this.setMode(e.detail));
    engine.addEventListener('connectionChange', (e) => this.setConnection(e.detail));
  }
}

export const statusBar = new StatusBar();
