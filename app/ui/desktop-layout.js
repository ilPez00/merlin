import { screenCapture } from '../lib/screen.js';
import { engine } from '../lib/hud-engine.js';
import { api } from '../lib/api.js';
import { panels } from './panels.js';

class DesktopLayout {
  constructor() {
    this.area = document.getElementById('content-area');
  }

  async activate() {
    this.area.innerHTML = `
      <div id="desktop-view">
        <div id="desktop-screen">
          <div id="desktop-screen-placeholder">
            <span>🖥️</span>
            <p>Screen capture feeds Merlin visual context</p>
            <button id="desktop-share-btn" class="primary-btn">SHARE SCREEN</button>
          </div>
          <div id="desktop-screen-live" class="hidden"></div>
        </div>
      </div>
    `;

    document.getElementById('desktop-share-btn')?.addEventListener('click', () => this._share());
  }

  deactivate() {
    screenCapture.stop();
    screenCapture.detach();
    this.area.innerHTML = '';
  }

  captureFrame() {
    return screenCapture.captureStill();
  }

  async _share() {
    try {
      await screenCapture.start();
      document.getElementById('desktop-screen-placeholder')?.classList.add('hidden');
      const live = document.getElementById('desktop-screen-live');
      live.classList.remove('hidden');
      screenCapture.attachTo(live);
      panels.spawn('DESKTOP', 'Screen shared. Ask me anything about what you see.', '#4A6FA5');
    } catch (e) {
      panels.spawn('DESKTOP', 'Screen share failed: ' + e.message, '#EF4444');
    }
  }
}

export const desktopLayout = new DesktopLayout();
