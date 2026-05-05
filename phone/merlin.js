// Merlin — phone client
// Streams camera frames, audio chunks, IMU, and GPS over WebSocket

const CONFIG = {
  // Set this to your computer's local IP and the server port
  serverUrl: "ws://192.168.1.100:8765",

  // Camera frame capture
  frameIntervalMs: 2000,   // how often to capture a frame
  frameQuality: 0.6,       // JPEG quality 0-1
  frameMaxWidth: 640,      // downscale to this width

  // Audio chunking
  audioChunkMs: 4000,      // send audio every N ms

  // Sensor sampling
  imuIntervalMs: 500,      // accelerometer/gyro rate
  gpsIntervalMs: 5000,     // GPS update rate
};

// ── State ────────────────────────────────────────────────────────────────────
let ws = null;
let stream = null;
let mediaRecorder = null;
let frameTimer = null;
let imuTimer = null;
let gpsWatchId = null;
let facingMode = "environment";
let lastImu = {};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const video    = document.getElementById("viewfinder");
const canvas   = document.getElementById("capture-canvas");
const btnConn  = document.getElementById("btn-connect");
const btnFlip  = document.getElementById("btn-cam-flip");
const btnStop  = document.getElementById("btn-stop");
const logLines = [
  document.getElementById("log-line-1"),
  document.getElementById("log-line-2"),
];

// ── Logging ──────────────────────────────────────────────────────────────────
function log(msg) {
  logLines[0].textContent = logLines[1].textContent;
  logLines[1].textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  console.log("[merlin]", msg);
}

// ── Status dots ──────────────────────────────────────────────────────────────
function setDot(id, state) {
  const el = document.getElementById(`dot-${id}`);
  el.className = `dot${state ? " " + state : ""}`;
}

// ── WebSocket ────────────────────────────────────────────────────────────────
function connect() {
  const url = prompt("Server WebSocket URL:", CONFIG.serverUrl) || CONFIG.serverUrl;
  CONFIG.serverUrl = url;

  ws = new WebSocket(url);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    log("connected to " + url);
    setDot("ws", "active");
    startStreaming();
    btnConn.disabled = true;
    btnStop.disabled = false;
  };

  ws.onclose = () => {
    log("disconnected");
    setDot("ws", "error");
    stopStreaming();
    btnConn.disabled = false;
    btnStop.disabled = true;
  };

  ws.onerror = (e) => {
    log("ws error — check server URL");
    setDot("ws", "error");
  };

  ws.onmessage = (evt) => {
    // Server can send text commands back (future use)
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === "ack") return;
      log("server: " + evt.data.slice(0, 80));
    } catch (_) {}
  };
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

function sendBinary(type, blob) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    // Prefix with a small JSON header so server can identify the blob type
    const header = JSON.stringify({ type, ts: Date.now() });
    const headerBytes = new TextEncoder().encode(header + "\n");
    blob.arrayBuffer().then((buf) => {
      const combined = new Uint8Array(headerBytes.length + buf.byteLength);
      combined.set(headerBytes);
      combined.set(new Uint8Array(buf), headerBytes.length);
      ws.send(combined.buffer);
    });
  }
}

// ── Camera ───────────────────────────────────────────────────────────────────
async function startCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode, width: { ideal: 1280 } },
      audio: true,
    });
    video.srcObject = stream;
    setDot("cam", "active");
    setDot("mic", "active");
    log("camera/mic started (" + facingMode + ")");
    return true;
  } catch (e) {
    log("camera error: " + e.message);
    setDot("cam", "error");
    setDot("mic", "error");
    return false;
  }
}

function captureFrame() {
  if (!stream) return;
  const vTrack = stream.getVideoTracks()[0];
  if (!vTrack) return;

  const { width: vw, height: vh } = vTrack.getSettings();
  const scale = Math.min(1, CONFIG.frameMaxWidth / (vw || 640));
  canvas.width  = Math.round((vw || 640) * scale);
  canvas.height = Math.round((vh || 480) * scale);

  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(
    (blob) => {
      if (blob) sendBinary("frame", blob);
    },
    "image/jpeg",
    CONFIG.frameQuality
  );
}

// ── Audio recording ───────────────────────────────────────────────────────────
function startAudio() {
  if (!stream) return;
  const audioStream = new MediaStream(stream.getAudioTracks());

  mediaRecorder = new MediaRecorder(audioStream, {
    mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm",
  });

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) {
      sendBinary("audio", e.data);
    }
  };

  mediaRecorder.start(CONFIG.audioChunkMs);
  log("audio streaming (" + CONFIG.audioChunkMs + "ms chunks)");
}

// ── IMU ───────────────────────────────────────────────────────────────────────
function startImu() {
  const handler = (e) => {
    lastImu = {
      ax: e.acceleration?.x,
      ay: e.acceleration?.y,
      az: e.acceleration?.z,
      gx: e.rotationRate?.alpha,
      gy: e.rotationRate?.beta,
      gz: e.rotationRate?.gamma,
      interval: e.interval,
    };
  };

  if (typeof DeviceMotionEvent !== "undefined") {
    if (typeof DeviceMotionEvent.requestPermission === "function") {
      // iOS 13+
      DeviceMotionEvent.requestPermission()
        .then((r) => {
          if (r === "granted") {
            window.addEventListener("devicemotion", handler);
            setDot("imu", "active");
          }
        })
        .catch(() => setDot("imu", "warn"));
    } else {
      window.addEventListener("devicemotion", handler);
      setDot("imu", "active");
    }
  } else {
    setDot("imu", "warn");
    log("IMU not available");
  }

  imuTimer = setInterval(() => {
    if (Object.keys(lastImu).length > 0) {
      send({ type: "imu", ts: Date.now(), ...lastImu });
    }
  }, CONFIG.imuIntervalMs);
}

// ── GPS ───────────────────────────────────────────────────────────────────────
function startGps() {
  if (!navigator.geolocation) {
    setDot("gps", "warn");
    log("GPS not available");
    return;
  }

  gpsWatchId = navigator.geolocation.watchPosition(
    (pos) => {
      setDot("gps", "active");
      send({
        type: "gps",
        ts: Date.now(),
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        alt: pos.coords.altitude,
        acc: pos.coords.accuracy,
        speed: pos.coords.speed,
        heading: pos.coords.heading,
      });
    },
    (err) => {
      setDot("gps", "warn");
      log("GPS error: " + err.message);
    },
    { enableHighAccuracy: true, maximumAge: CONFIG.gpsIntervalMs }
  );
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
async function startStreaming() {
  const ok = await startCamera();
  if (!ok) return;

  startAudio();
  startImu();
  startGps();

  frameTimer = setInterval(captureFrame, CONFIG.frameIntervalMs);
  log("streaming started");
}

function stopStreaming() {
  clearInterval(frameTimer);
  clearInterval(imuTimer);
  if (gpsWatchId !== null) navigator.geolocation.clearWatch(gpsWatchId);
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  if (stream) stream.getTracks().forEach((t) => t.stop());

  frameTimer = null;
  imuTimer = null;
  gpsWatchId = null;
  stream = null;

  ["cam", "mic", "gps", "imu"].forEach((id) => setDot(id, null));
  log("streaming stopped");
}

// ── Button handlers ───────────────────────────────────────────────────────────
btnConn.addEventListener("click", connect);

btnFlip.addEventListener("click", async () => {
  facingMode = facingMode === "environment" ? "user" : "environment";
  if (stream) {
    await startCamera();   // restarts with new facing mode
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
      startAudio();
    }
  }
});

btnStop.addEventListener("click", () => {
  if (ws) ws.close();
});
