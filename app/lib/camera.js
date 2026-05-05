class Camera {
  constructor() {
    this.stream = null;
    this.video = null;
    this.canvas = null;
    this.ctx = null;
    this.active = false;
    this._timer = null;
  }

  async start() {
    if (this.active) return;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      this.video = document.createElement('video');
      this.video.srcObject = this.stream;
      this.video.playsInline = true;
      this.video.muted = true;
      await this.video.play();

      this.canvas = document.createElement('canvas');
      this.ctx = this.canvas.getContext('2d');
      this.active = true;
    } catch (e) {
      throw new Error('Camera access denied: ' + e.message);
    }
  }

  stop() {
    this.active = false;
    if (this._timer) clearInterval(this._timer);
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    this.video = null;
  }

  captureFrame(maxW = 640, quality = 0.65) {
    if (!this.active || !this.video?.videoWidth) return null;
    const scale = Math.min(1, maxW / this.video.videoWidth);
    this.canvas.width = Math.round(this.video.videoWidth * scale);
    this.canvas.height = Math.round(this.video.videoHeight * scale);
    this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
    return this.canvas.toDataURL('image/jpeg', quality).split(',')[1];
  }

  attachTo(el) {
    if (!this.video) return;
    el.innerHTML = '';
    this.video.style.width = '100%';
    this.video.style.height = '100%';
    this.video.style.objectFit = 'cover';
    el.appendChild(this.video);
  }

  detach() {
    if (this.video?.parentNode) this.video.parentNode.removeChild(this.video);
  }
}

export const camera = new Camera();
