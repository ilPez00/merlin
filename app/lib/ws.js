import { config } from './config.js';
import { engine } from './hud-engine.js';

class WsClient extends EventTarget {
  constructor() {
    super();
    this.ws = null;
    this.reconnectTimer = null;
    this._pending = [];
  }

  connect(url) {
    if (this.ws) this.close();
    try {
      this.ws = new WebSocket(url);
    } catch (e) {
      this.dispatch('error', e.message);
      return;
    }

    this.ws.onopen = () => {
      engine.setConnection('server');
      this._flush();
      this.dispatch('connected');
    };

    this.ws.onclose = () => {
      engine.setConnection('disconnected');
      this.dispatch('disconnected');
      this._scheduleReconnect(url);
    };

    this.ws.onerror = () => {
      this.dispatch('error', 'WebSocket error');
    };

    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        this.dispatch('message', msg);
      } catch { /* binary messages not yet handled */ }
    };
  }

  sendJson(obj) {
    const msg = JSON.stringify(obj);
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(msg);
    } else {
      this._pending.push(msg);
    }
  }

  sendBinary(header, blob) {
    if (this.ws?.readyState !== WebSocket.OPEN) return;
    const hdr = JSON.stringify(header);
    const enc = new TextEncoder().encode(hdr + '\n');
    const combined = new Blob([enc, blob]);
    this.ws.send(combined);
  }

  close() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) this.ws.close();
    this.ws = null;
  }

  _flush() {
    for (const msg of this._pending) {
      this.ws?.send(msg);
    }
    this._pending = [];
  }

  _scheduleReconnect(url) {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connect(url), 3000);
  }

  dispatch(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }
}

export const wsClient = new WsClient();
