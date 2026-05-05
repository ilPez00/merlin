const CACHE = 'merlin-v1';
const MODEL_CACHE = 'merlin-models-v1';

const PRECACHE = [
  '/app/',
  '/app/index.html',
  '/app/hud.css',
  '/app/visor.css',
  '/app/copilot.css',
  '/app/desktop.css',
];

const MODEL_URLS = [
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm/vision_wasm_internal.js',
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm/vision_wasm_internal.wasm',
];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(PRECACHE);
    try {
      const modelCache = await caches.open(MODEL_CACHE);
      await modelCache.addAll(MODEL_URLS);
    } catch (_) { /* models are large; fail silently */ }
  })());
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Model files: cache-first
  if (url.hostname === 'cdn.jsdelivr.net' && url.pathname.includes('mediapipe')) {
    e.respondWith((async () => {
      const cached = await caches.match(e.request, { cacheName: MODEL_CACHE });
      if (cached) return cached;
      return fetch(e.request);
    })());
    return;
  }

  // App shell: cache-first
  if (url.pathname.startsWith('/app/') && e.request.mode === 'navigate') {
    e.respondWith((async () => {
      const cached = await caches.match('/app/index.html');
      if (cached) return cached;
      return fetch(e.request);
    })());
    return;
  }

  // Everything else: network-first
  e.respondWith((async () => {
    try {
      const fresh = await fetch(e.request);
      const cache = await caches.open(CACHE);
      cache.put(e.request, fresh.clone());
      return fresh;
    } catch {
      const cached = await caches.match(e.request);
      if (cached) return cached;
      return new Response('offline', { status: 503 });
    }
  })());
});
