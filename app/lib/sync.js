import { config } from './config.js';
import { diary } from './diary.js';
import { engine } from './hud-engine.js';

class SyncManager extends EventTarget {
  constructor() {
    super();
    this._timer = null;
    this._syncing = false;
    this._serverReachable = false;
    this._checkIntervalMs = 60000; // check every 60s
  }

  start() {
    // Immediate check
    this._check();
    // Periodic checks
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => this._check(), this._checkIntervalMs);

    // Also check on network reconnect
    window.addEventListener('online', () => this._check());

    engine.addEventListener('connectionChange', (e) => {
      if (e.detail === 'server') this._push();
    });
  }

  stop() {
    if (this._timer) clearInterval(this._timer);
    this._timer = null;
  }

  async forceSync() {
    await this._push();
  }

  /* ── Server reachability ─────────────────── */

  async _check() {
    const url = config.get('serverUrl');
    if (!url) {
      // No server configured — standalone mode, nothing to sync
      return;
    }

    const reachable = await this._ping(url);
    if (reachable && !this._serverReachable) {
      this._serverReachable = true;
      engine.setConnection('server');
      await this._push();
      await this._pull();
    } else if (!reachable && this._serverReachable) {
      this._serverReachable = false;
      if (config.isDirectMode()) {
        engine.setConnection('direct');
      } else {
        engine.setConnection('disconnected');
      }
    }
  }

  async _ping(url) {
    // Try WebSocket connection to see if server is alive
    try {
      const ws = new WebSocket(url);
      const result = await new Promise((resolve) => {
        const t = setTimeout(() => { ws.close(); resolve(false); }, 2000);
        ws.onopen = () => { clearTimeout(t); ws.close(); resolve(true); };
        ws.onerror = () => { clearTimeout(t); resolve(false); };
      });
      return result;
    } catch {
      return false;
    }
  }

  /* ── Push local data to server ───────────── */

  async _push() {
    if (this._syncing) return;
    this._syncing = true;

    try {
      const unsynced = await diary.getUnsynced(200);
      if (unsynced.length === 0) {
        this._syncing = false;
        return;
      }

      // Connect to server via WebSocket and push
      const ws = new WebSocket(config.get('serverUrl'));
      await new Promise((resolve, reject) => {
        const t = setTimeout(() => { ws.close(); reject(new Error('timeout')); }, 5000);

        ws.onopen = async () => {
          clearTimeout(t);

          // Send entries in batches of 20
          const batchSize = 20;
          for (let i = 0; i < unsynced.length; i += batchSize) {
            const batch = unsynced.slice(i, i + batchSize);
            ws.send(JSON.stringify({
              type: 'sync_push',
              entries: batch,
              device: 'phone',
              timestamp: Date.now(),
            }));
          }

          // Signal end of push
          ws.send(JSON.stringify({
            type: 'sync_push_done',
            timestamp: Date.now(),
          }));

          // Wait for acknowledgment
          ws.onmessage = async (e) => {
            try {
              const msg = JSON.parse(e.data);
              if (msg.type === 'sync_ack') {
                // Mark all pushed entries as synced
                for (const entry of unsynced) {
                  await diary.update(entry.id, { synced: true });
                }
                config.set('lastSyncTimestamp', Date.now());
                this.dispatch('synced', { count: unsynced.length });
                resolve();
              }
            } catch {}
          };

          // Fallback: mark synced even without ack after 3s
          setTimeout(async () => {
            for (const entry of unsynced) {
              await diary.update(entry.id, { synced: true });
            }
            config.set('lastSyncTimestamp', Date.now());
            this.dispatch('synced', { count: unsynced.length });
            resolve();
          }, 3000);
        };

        ws.onerror = () => { clearTimeout(t); reject(new Error('ws error')); };
      });

      ws.close();
    } catch (e) {
      console.warn('[Merlin] Sync push failed:', e.message);
    }

    this._syncing = false;
  }

  /* ── Pull data from server ───────────────── */

  async _pull() {
    try {
      const ws = new WebSocket(config.get('serverUrl'));
      await new Promise((resolve, reject) => {
        const t = setTimeout(() => { ws.close(); reject(new Error('timeout')); }, 5000);

        ws.onopen = () => {
          clearTimeout(t);
          ws.send(JSON.stringify({
            type: 'sync_pull',
            device: 'phone',
            since: config.get('lastSyncTimestamp') || 0,
          }));
        };

        ws.onmessage = async (e) => {
          try {
            const msg = JSON.parse(e.data);
            if (msg.type === 'sync_pull_data') {
              // Server sent config updates, schedule, merged entries
              if (msg.config) {
                for (const [key, val] of Object.entries(msg.config)) {
                  config.set(key, val);
                }
              }
              if (msg.entries) {
                for (const entry of msg.entries) {
                  // Don't overwrite local unsynced entries
                  const local = await diary.get(entry.id);
                  if (!local || local.synced) {
                    await diary.add({ ...entry, synced: true });
                  }
                }
              }
              this.dispatch('pulled', msg);
              resolve();
            }
          } catch {}
        };

        ws.onerror = () => { clearTimeout(t); reject(new Error('ws error')); };

        // Resolve after timeout even without data
        setTimeout(() => resolve(), 4000);
      });
      ws.close();
    } catch (e) {
      console.warn('[Merlin] Sync pull failed:', e.message);
    }
  }

  dispatch(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }
}

export const syncManager = new SyncManager();
