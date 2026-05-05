class ScreenCapture {
  constructor() {
    this.stream = null;
    this.video = null;
    this.canvas = null;
    this.ctx = null;
    this._timer = null;
    this._intervalMs = 3000;
    this._onFrame = null;
    this._watching = false;
  }

  setInterval(ms) { this._intervalMs = ms; }
  onFrame(cb) { this._onFrame = cb; }

  async start() {
    if (this.stream) return;
    try {
      this.stream = await navigator.mediaDevices.getDisplayMedia({
        video: { cursor: 'always' },
        audio: false,
      });

      this.video = document.createElement('video');
      this.video.srcObject = this.stream;
      this.video.playsInline = true;
      this.video.muted = true;
      await this.video.play();

      this.canvas = document.createElement('canvas');
      this.ctx = this.canvas.getContext('2d');

      this.stream.getVideoTracks()[0].onended = () => this.stop();
    } catch (e) {
      throw new Error('Screen capture denied: ' + e.message);
    }
  }

  stop() {
    this._watching = false;
    if (this._timer) clearInterval(this._timer);
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    this.video = null;
  }

  startWatching() {
    if (!this.stream) return;
    this._watching = true;
    this._tick();
  }

  stopWatching() {
    this._watching = false;
    if (this._timer) clearInterval(this._timer);
    this._timer = null;
  }

  _tick() {
    if (!this._watching || !this.video?.videoWidth) return;
    const frame = this._grab();
    if (frame && this._onFrame) this._onFrame(frame);
    this._timer = setTimeout(() => this._tick(), this._intervalMs);
  }

  captureStill() {
    return this._grab();
  }

  _grab() {
    if (!this.video?.videoWidth) return null;
    const maxW = 640;
    const scale = Math.min(1, maxW / this.video.videoWidth);
    this.canvas.width = Math.round(this.video.videoWidth * scale);
    this.canvas.height = Math.round(this.video.videoHeight * scale);
    this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
    return this.canvas.toDataURL('image/jpeg', 0.65).split(',')[1];
  }

  attachTo(el) {
    if (!this.video) return;
    el.innerHTML = '';
    this.video.style.width = '100%';
    this.video.style.height = '100%';
    this.video.style.objectFit = 'contain';
    el.appendChild(this.video);
  }

  detach() {
    if (this.video?.parentNode) this.video.parentNode.removeChild(this.video);
  }
}

export const screenCapture = new ScreenCapture();
