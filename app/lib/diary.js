const DB_NAME = 'MerlinDiary';
const DB_VERSION = 1;
const STORE = 'entries';

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'id' });
        store.createIndex('synced', 'synced', { unique: false });
        store.createIndex('type', 'type', { unique: false });
        store.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

let _db = null;
async function db() {
  if (!_db) _db = await openDB();
  return _db;
}

class Diary {
  constructor() {
    this._pendingOp = null;
  }

  /* ── CRUD ─────────────────────────────────── */

  async add(entry) {
    const d = await db();
    const doc = {
      id: entry.id || crypto.randomUUID(),
      timestamp: entry.timestamp || Date.now(),
      type: entry.type || 'note',        // note | photo | voice | observation | conversation
      content: entry.content || '',
      metadata: entry.metadata || {},     // { mode, gps, tags, activityMode, appMode }
      synced: false,
      syncAttempts: 0,
    };
    await d.put(STORE, doc);
    return doc.id;
  }

  async update(id, changes) {
    const d = await db();
    const existing = await d.get(STORE, id);
    if (!existing) return;
    Object.assign(existing, changes);
    await d.put(STORE, existing);
  }

  async get(id) {
    const d = await db();
    return d.get(STORE, id);
  }

  async delete(id) {
    const d = await db();
    return d.delete(STORE, id);
  }

  /* ── Queries ──────────────────────────────── */

  async list(opts = {}) {
    const d = await db();
    const { type, synced, limit = 50, offset = 0 } = opts;
    let items = await d.getAll(STORE);

    if (type) items = items.filter(e => e.type === type);
    if (synced !== undefined) items = items.filter(e => e.synced === synced);

    items.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    return items.slice(offset, offset + limit);
  }

  async countUnsynced() {
    const items = await this.list({ synced: false, limit: 10000 });
    return items.length;
  }

  async getUnsynced(limit = 100) {
    return this.list({ synced: false, limit });
  }

  async deleteBefore(timestamp) {
    const d = await db();
    const all = await d.getAll(STORE);
    const ids = all.filter(e => (e.timestamp || 0) < timestamp).map(e => e.id);
    for (const id of ids) await d.delete(STORE, id);
    return ids.length;
  }

  /* ── Convenience ──────────────────────────── */

  async addObservation(frameB64, mode, text = '') {
    return this.add({
      type: 'observation',
      content: text,
      metadata: { mode, appMode: 'visor', hasFrame: !!frameB64 },
      // frame data stored separately to keep IndexedDB lean
    });
  }

  async addConversation(messages, mode) {
    return this.add({
      type: 'conversation',
      content: JSON.stringify(messages),
      metadata: { mode, msgCount: messages.length },
    });
  }

  async addPhoto(frameB64, mode, tags = []) {
    return this.add({
      type: 'photo',
      content: frameB64,
      metadata: { mode, tags },
    });
  }

  async addAudio(blob, mode) {
    // Convert blob to base64 for IndexedDB storage
    const b64 = await this._blobToBase64(blob);
    return this.add({
      type: 'voice',
      content: b64,
      metadata: { mode, mime: blob.type, size: blob.size },
    });
  }

  /* ── Helpers ──────────────────────────────── */

  _blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }
}

export const diary = new Diary();
