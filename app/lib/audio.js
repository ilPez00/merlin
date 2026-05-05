import { config } from './config.js';

class AudioCapture {
  constructor() {
    this.stream = null;
    this.recorder = null;
    this._chunks = [];
    this._onChunk = null;
    this._onTranscription = null;
    this._speechRec = null;
    this._wakeWordActive = false;
    this.active = false;
  }

  onChunk(cb) { this._onChunk = cb; }
  onTranscription(cb) { this._onTranscription = cb; }

  async start() {
    if (this.active) return;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      this.active = true;
    } catch (e) {
      throw new Error('Mic access denied: ' + e.message);
    }
  }

  stop() {
    this.active = false;
    this.stopRecording();
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    this.stopWakeWord();
  }

  startRecording(chunkMs = 4000) {
    if (!this.stream || this.recorder) return;
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus' : 'audio/webm';
    this._chunks = [];
    this.recorder = new MediaRecorder(this.stream, { mimeType: mime });

    this.recorder.addEventListener('dataavailable', e => {
      if (e.data.size > 0) this._chunks.push(e.data);
    });

    this.recorder.addEventListener('stop', () => {
      if (this._chunks.length > 0) {
        const blob = new Blob(this._chunks, { type: mime });
        this._chunks = [];
        if (this._onChunk) this._onChunk(blob);
        // Auto-save to diary for later transcription
        if (config.get('diaryAudioSave')) {
          import('./diary.js').then(m => m.diary.addAudio(blob, 'audio')).catch(() => {});
        }
      }
      if (this.active) {
        setTimeout(() => this.startRecording(chunkMs), 200);
      }
    });

    this.recorder.start();
    setTimeout(() => {
      if (this.recorder?.state === 'recording') this.recorder.stop();
    }, chunkMs);
  }

  stopRecording() {
    if (this.recorder && this.recorder.state !== 'inactive') {
      this.recorder.stop();
    }
    this.recorder = null;
  }

  startWakeWord() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return false;
    this._speechRec = new SR();
    this._speechRec.continuous = true;
    this._speechRec.interimResults = true;
    this._speechRec.lang = 'en-US';

    this._speechRec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        const text = r[0].transcript;
        if (r.isFinal && text.toLowerCase().includes('merlin')) {
          const idx = text.toLowerCase().indexOf('merlin') + 6;
          const cmd = text.slice(idx).trim();
          if (this._onTranscription) this._onTranscription(cmd || 'wake');
        }
      }
    };

    this._speechRec.onend = () => {
      if (this._wakeWordActive) {
        setTimeout(() => {
          try { this._speechRec.start(); } catch {}
        }, 200);
      }
    };

    this._wakeWordActive = true;
    try { this._speechRec.start(); } catch {}
    return true;
  }

  stopWakeWord() {
    this._wakeWordActive = false;
    if (this._speechRec) {
      try { this._speechRec.stop(); } catch {}
      this._speechRec = null;
    }
  }

  async pushToTalk(durationMs = 5000) {
    if (!this.stream) await this.start();
    return new Promise((resolve) => {
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus' : 'audio/webm';
      const chunks = [];
      const r = new MediaRecorder(this.stream, { mimeType: mime });
      r.addEventListener('dataavailable', e => { if (e.data.size > 0) chunks.push(e.data); });
      r.addEventListener('stop', () => {
        if (chunks.length > 0) resolve(new Blob(chunks, { type: mime }));
        else resolve(null);
      });
      r.start();
      setTimeout(() => { if (r.state === 'recording') r.stop(); }, durationMs);
    });
  }
}

export const audio = new AudioCapture();
