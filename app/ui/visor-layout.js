import { camera } from '../lib/camera.js';
import { lens } from '../lib/vision.js';
import { engine } from '../lib/hud-engine.js';

class VisorLayout {
  constructor() {
    this.area = document.getElementById('content-area');
    this.lensOverlay = null;
    this._detectionTimer = null;
  }

  async activate() {
    this.area.innerHTML = `
      <div id="visor-view">
        <div id="visor-camera"></div>
        <canvas id="visor-lens-canvas"></canvas>
        <div id="visor-lens-chips"></div>
        <div id="visor-tap-hint">TAP TO OBSERVE</div>
      </div>
    `;

    try {
      await camera.start();
      camera.attachTo(document.getElementById('visor-camera'));
    } catch (e) {
      this.area.innerHTML = `<div class="error-overlay">Camera: ${e.message}</div>`;
      return;
    }

    this._setupTap();
    this._setupLens();
  }

  deactivate() {
    camera.stop();
    camera.detach();
    lens.stop();
    this.area.innerHTML = '';
  }

  captureFrame() {
    return camera.captureFrame();
  }

  _setupTap() {
    const hint = document.getElementById('visor-tap-hint');
    this.area.addEventListener('click', (e) => {
      if (e.target.closest('.hud-panel, #status-bar, #mode-tabs, #query-bar')) return;
      hint.classList.add('flash');
      setTimeout(() => hint.classList.remove('flash'), 400);
      engine.dispatch('userObserve', { frame: camera.captureFrame() });
    });
  }

  async _setupLens() {
    const ready = await lens.load();
    if (!ready) return;

    const video = camera.video;
    if (!video) return;

    const canvas = document.getElementById('visor-lens-canvas');
    const chips = document.getElementById('visor-lens-chips');
    if (!canvas || !chips) return;

    const ctx = canvas.getContext('2d');

    const resize = () => {
      canvas.width = this.area.clientWidth;
      canvas.height = this.area.clientHeight;
    };
    window.addEventListener('resize', resize);
    resize();

    lens.onDetections((detections) => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      chips.innerHTML = '';

      detections.forEach((d, i) => {
        const box = d.boundingBox;
        const x = box.originX * (canvas.width / video.videoWidth);
        const y = box.originY * (canvas.height / video.videoHeight);
        const w = box.width * (canvas.width / video.videoWidth);
        const h = box.height * (canvas.height / video.videoHeight);

        ctx.strokeStyle = 'rgba(0, 229, 255, 0.8)';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);

        const label = d.categories[0]?.categoryName || 'object';
        const score = d.categories[0]?.score || 0;
        if (score > 0.5) {
          const chip = document.createElement('span');
          chip.className = 'lens-chip';
          chip.textContent = label;
          chip.style.left = x + 'px';
          chip.style.top = (y - 24) + 'px';
          chips.appendChild(chip);
        }
      });
    });

    lens.start(video);
  }
}

export const visorLayout = new VisorLayout();
