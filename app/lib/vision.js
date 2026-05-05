class VisionLens {
  constructor() {
    this.detector = null;
    this.ready = false;
    this._detections = [];
    this._onDetections = null;
    this._timer = null;
    this._running = false;
  }

  onDetections(cb) { this._onDetections = cb; }

  async load() {
    if (this.ready) return true;
    try {
      const vision = window.Vision;
      if (!vision) {
        console.warn('[Merlin] MediaPipe Vision not loaded');
        return false;
      }
      this.detector = await vision.ObjectDetector.createFromOptions(
        vision.FilesetResolver.forVisionTasks(
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm/'
        ),
        {
          baseOptions: {
            modelAssetPath:
              'https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite',
            delegate: 'GPU',
          },
          runningMode: 'VIDEO',
          scoreThreshold: 0.5,
          maxResults: 5,
        }
      );
      this.ready = true;
      return true;
    } catch (e) {
      console.warn('[Merlin] MediaPipe load failed:', e.message);
      return false;
    }
  }

  start(videoEl) {
    if (!this.ready || this._running) return;
    this._running = true;
    this._video = videoEl;
    let lastCall = performance.now();
    this._timer = setInterval(() => {
      if (!this._running || !videoEl?.videoWidth) return;
      const now = performance.now();
      const results = this.detector.detectForVideo(videoEl, now - lastCall);
      lastCall = now;
      this._detections = results.detections || [];
      if (this._onDetections) this._onDetections(this._detections);
    }, 200);
  }

  stop() {
    this._running = false;
    if (this._timer) clearInterval(this._timer);
    this._timer = null;
  }
}

export const lens = new VisionLens();
