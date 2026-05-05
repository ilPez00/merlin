class AppNotifications {
  constructor() {
    this.wakeLock = null;
    this._deferredPrompt = null;
    this._installable = false;
  }

  async requestWakeLock() {
    if (!navigator.wakeLock) return;
    try {
      this.wakeLock = await navigator.wakeLock.request('screen');
      this.wakeLock.addEventListener('release', () => { this.wakeLock = null; });
    } catch {}
  }

  releaseWakeLock() {
    if (this.wakeLock) {
      this.wakeLock.release();
      this.wakeLock = null;
    }
  }

  listenInstall() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this._deferredPrompt = e;
      this._installable = true;
    });

    window.addEventListener('appinstalled', () => {
      this._deferredPrompt = null;
      this._installable = false;
    });
  }

  canInstall() { return this._installable; }

  async promptInstall() {
    if (!this._deferredPrompt) return false;
    this._deferredPrompt.prompt();
    const result = await this._deferredPrompt.userChoice;
    this._deferredPrompt = null;
    this._installable = false;
    return result.outcome === 'accepted';
  }

  registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    }
  }
}

export const notifications = new AppNotifications();
