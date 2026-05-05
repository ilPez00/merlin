import { engine, ACTIVITY_MODES } from '../lib/hud-engine.js';

class ModeTabs {
  constructor() {
    this.el = document.getElementById('mode-tabs');
    this.el.addEventListener('click', (e) => {
      const tab = e.target.closest('.mode-tab');
      if (tab && tab.dataset.mode) {
        engine.setActivityMode(tab.dataset.mode);
      }
    });

    this._rebuild();
    engine.addEventListener('modeChange', (e) => this._highlight(e.detail));
  }

  _rebuild() {
    this.el.innerHTML = '';
    const names = Object.keys(ACTIVITY_MODES);
    names.forEach(name => {
      const btn = document.createElement('button');
      btn.className = 'mode-tab';
      btn.dataset.mode = name;
      btn.textContent = ACTIVITY_MODES[name].label;
      btn.style.setProperty('--tab-color', ACTIVITY_MODES[name].color);
      if (name === engine.activityMode) btn.classList.add('active');
      this.el.appendChild(btn);
    });
  }

  _highlight(mode) {
    this.el.querySelectorAll('.mode-tab').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });
  }
}

export const modeTabs = new ModeTabs();
