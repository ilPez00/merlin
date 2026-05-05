import { config } from './config.js';

const ACTIVITY_MODES = {
  WORK: {
    label: 'WORK', color: '#4A6FA5',
    camFps: 0.2, audio: true, gps: false,
    observeMs: null,
    widgets: ['mode_tag', 'status_bar', 'schedule', 'ai_text'],
  },
  LIFT: {
    label: 'LIFT', color: '#EF4444',
    camFps: 1.0, audio: 'push_to_talk', gps: false,
    observeMs: null,
    widgets: ['mode_tag', 'status_bar', 'reps_timer', 'ai_text'],
  },
  WALK: {
    label: 'WALK', color: '#4ADE80',
    camFps: 0.3, audio: true, gps: true,
    observeMs: 15000,
    widgets: ['mode_tag', 'status_bar', 'compass', 'ai_text', 'diary_prompt'],
  },
  TALK: {
    label: 'TALK', color: '#E11D48',
    camFps: 0, audio: true, gps: false,
    observeMs: null,
    widgets: ['mode_tag', 'status_bar', 'transcription', 'ai_text'],
  },
  NOTES: {
    label: 'NOTES', color: '#F59E0B',
    camFps: 0.2, audio: true, gps: true,
    observeMs: null,
    widgets: ['mode_tag', 'status_bar', 'transcription', 'diary_prompt'],
  },
  SCOUT: {
    label: 'SCOUT', color: '#00e5ff',
    camFps: 0.5, audio: true, gps: true,
    observeMs: 15000,
    widgets: ['mode_tag', 'status_bar', 'ai_text', 'sensor_readout'],
  },
  RECON: {
    label: 'RECON', color: '#546e7a',
    camFps: 0.1, audio: false, gps: true,
    observeMs: null,
    widgets: ['mode_tag', 'status_bar'],
  },
};

class HudEngine extends EventTarget {
  constructor() {
    super();
    this.activityMode = config.get('lastActivityMode') || 'SCOUT';
    this.appMode = 'visor'; // visor | copilot | desktop
    this.connectionMode = 'direct'; // direct | server | disconnected
    this.fpsInterval = null;
    this.observeInterval = null;
  }

  setActivityMode(mode) {
    if (!ACTIVITY_MODES[mode]) return;
    this.activityMode = mode;
    config.set('lastActivityMode', mode);
    this.dispatch('modeChange', mode);
  }

  setAppMode(mode) {
    if (!['visor', 'copilot', 'desktop'].includes(mode)) return;
    this.appMode = mode;
    config.set('lastMode', mode);
    this.dispatch('appModeChange', mode);
  }

  setConnection(mode) {
    this.connectionMode = mode;
    this.dispatch('connectionChange', mode);
  }

  getMode() { return ACTIVITY_MODES[this.activityMode]; }

  dispatch(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }
}

export const engine = new HudEngine();
export { ACTIVITY_MODES };
