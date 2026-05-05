import { screenCapture } from '../lib/screen.js';
import { engine } from '../lib/hud-engine.js';
import { config } from '../lib/config.js';
import { api } from '../lib/api.js';
import { panels } from './panels.js';

class CopilotLayout {
  constructor() {
    this.area = document.getElementById('content-area');
    this._watchActive = false;
  }

  async activate() {
    this.area.innerHTML = `
      <div id="copilot-view">
        <div id="copilot-screen">
          <div id="copilot-screen-placeholder">
            <span>🎯</span>
            <p>Share your screen to let Merlin watch</p>
            <button id="copilot-share-btn" class="primary-btn">SHARE SCREEN</button>
          </div>
        </div>
        <div id="copilot-feed">
          <div id="copilot-feed-header">
            <span>MERLIN COPILOT</span>
            <button id="copilot-watch-btn" class="secondary-btn" disabled>WATCH</button>
          </div>
          <div id="copilot-feed-content">
            <p class="muted">Share your screen, then enable WATCH to let Merlin observe and advise.</p>
          </div>
        </div>
      </div>
    `;

    document.getElementById('copilot-share-btn')?.addEventListener('click', () => this._share());
    document.getElementById('copilot-watch-btn')?.addEventListener('click', () => this._toggleWatch());
  }

  deactivate() {
    this._watchActive = false;
    screenCapture.stopWatching();
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
      const placeholder = document.getElementById('copilot-screen-placeholder');
      if (placeholder) placeholder.style.display = 'none';
      screenCapture.attachTo(document.getElementById('copilot-screen'));
      document.getElementById('copilot-watch-btn').disabled = false;
    } catch (e) {
      panels.spawn('COPILOT', 'Screen share failed: ' + e.message, '#E11D48');
    }
  }

  async _toggleWatch() {
    const btn = document.getElementById('copilot-watch-btn');
    this._watchActive = !this._watchActive;

    if (this._watchActive) {
      btn.textContent = 'STOP';
      btn.classList.add('active');
      screenCapture.setInterval(config.get('copilotIntervalMs') || 3000);
      screenCapture.onFrame((frame) => this._analyzeFrame(frame));
      screenCapture.startWatching();
      panels.spawn('COPILOT', 'Watching… I\'ll observe silently and speak when I have insight.', '#00e5ff');
    } else {
      btn.textContent = 'WATCH';
      btn.classList.remove('active');
      screenCapture.stopWatching();
      panels.spawn('COPILOT', 'Observation paused.', '#546e7a');
    }
  }

  async _analyzeFrame(frameB64) {
    if (!this._watchActive) return;

    const mode = engine.activityMode;
    const prompt = `You are Merlin Copilot, watching the user's screen in ${mode} mode. Give a brief observation or suggestion based on what you see. Be concise (1-2 sentences).`;

    try {
      const result = await api.chatWithVision([
        { role: 'system', content: prompt },
        { role: 'user', content: 'What do you see?' },
      ], frameB64, { maxTokens: 200 });

      const text = result.content || '';
      if (text) {
        const feed = document.getElementById('copilot-feed-content');
        if (feed) {
          const entry = document.createElement('div');
          entry.className = 'copilot-entry';
          entry.textContent = '💡 ' + text;
          feed.prepend(entry);
          if (feed.children.length > 20) feed.lastChild.remove();
        }
      }
    } catch {}
  }
}

export const copilotLayout = new CopilotLayout();
