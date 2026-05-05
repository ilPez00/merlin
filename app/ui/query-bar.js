import { config } from '../lib/config.js';
import { engine } from '../lib/hud-engine.js';
import { api } from '../lib/api.js';
import { camera } from '../lib/camera.js';
import { screenCapture } from '../lib/screen.js';
import { audio } from '../lib/audio.js';
import { panels } from './panels.js';

class QueryBar {
  constructor() {
    this.el = document.getElementById('query-bar');
    this.input = document.getElementById('query-input');
    this.sendBtn = document.getElementById('query-send');
    this.micBtn = document.getElementById('query-mic');

    this.sendBtn.addEventListener('click', () => this._submit());
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this._submit();
    });
    this.micBtn.addEventListener('click', () => this._pushToTalk());
  }

  show() { this.el.classList.add('visible'); }
  hide() { this.el.classList.remove('visible'); }

  async _submit() {
    const text = this.input.value.trim();
    if (!text) return;
    this.input.value = '';

    // Grab current visual context
    let frameB64 = null;
    if (engine.appMode === 'visor') {
      frameB64 = camera.captureFrame();
    } else if (engine.appMode === 'copilot' || engine.appMode === 'desktop') {
      frameB64 = screenCapture.captureStill();
    }

    const panelId = panels.spawn(
      'MERLIN — ' + engine.activityMode,
      '…',
      engine.getMode()?.color
    );

    // Build conversation
    const messages = [
      { role: 'system', content: 'You are Merlin, an AI field assistant. Be concise, grounded in context.' },
      { role: 'user', content: text },
    ];

    try {
      const result = await api.chatWithVision(messages, frameB64);
      const response = result.content || '(no response)';
      panels.update(panelId, response);
    } catch (e) {
      panels.update(panelId, 'Error: ' + e.message);
    }
  }

  async _pushToTalk() {
    try {
      const blob = await audio.pushToTalk(5000);
      if (!blob) return;
      panels.spawn('MERLIN — VOICE', 'Transcribing…', engine.getMode()?.color);
      // In direct API mode, we'd send audio to Whisper first, then submit.
      // For now, show placeholder. Full audio flow will be step 8.
      panels.update('panel-' + (Date.now() - 1), 'Voice recording captured (' + (blob.size / 1024).toFixed(0) + 'KB). Transcribe + submit logic incoming.');
    } catch (e) {
      panels.spawn('MERLIN — ERROR', 'Mic error: ' + e.message, '#EF4444');
    }
  }
}

export const queryBar = new QueryBar();
