const STORAGE_KEY = 'merlin_config';

const DEFAULT_CONFIG = {
  provider: 'deepseek',
  apiKey: '',
  baseUrl: '',
  serverUrl: '',
  cacheModels: true,
  lastMode: 'visor',
  lastActivityMode: 'WORK',
  copilotIntervalMs: 3000,
  lensEnabled: true,
  syncAuto: true,
  lastSyncTimestamp: 0,
  diaryAutoSave: true,       // auto-save captures to diary
  diaryAudioSave: true,      // auto-save audio blobs for later transcription
};

const PROVIDER_DEFAULTS = {
  deepseek: { baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  openai:   { baseUrl: 'https://api.openai.com/v1',     model: 'gpt-4o' },
  anthropic:{ baseUrl: 'https://api.anthropic.com/v1',  model: 'claude-sonnet-4-20250514' },
};

class AppConfig {
  constructor() {
    this.data = { ...DEFAULT_CONFIG };
    this.load();
  }

  load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        Object.assign(this.data, DEFAULT_CONFIG, saved);
      }
    } catch { /* use defaults */ }
  }

  save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data));
    } catch { /* storage full or unavailable */ }
  }

  get(key) { return this.data[key]; }
  set(key, value) { this.data[key] = value; this.save(); }

  apiEndpoint() {
    const p = this.data.provider;
    if (p === 'custom') return this.data.baseUrl;
    return PROVIDER_DEFAULTS[p]?.baseUrl || PROVIDER_DEFAULTS.deepseek.baseUrl;
  }

  apiModel() {
    const p = this.data.provider;
    if (p === 'custom') return '';
    return PROVIDER_DEFAULTS[p]?.model || PROVIDER_DEFAULTS.deepseek.model;
  }

  isDirectMode() {
    return !!this.data.apiKey;
  }

  isServerMode() {
    return !!this.data.serverUrl;
  }
}

export const config = new AppConfig();
