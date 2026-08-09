/**
 * MP3z Samba Player — Service Worker
 * Strategie:
 *   App Shell   → Cache First (offline-fähig)
 *   API Browse/Search → Network First (immer frisch)
 *   Album Art   → Cache First + Background Refresh
 *   Audio Stream → Kein Cache (zu groß)
 */

const CACHE_NAME    = 'mp3z-v1';
const SHELL_CACHE   = 'mp3z-shell-v2';
const ART_CACHE     = 'mp3z-art-v1';

const SHELL_ASSETS = [
  '/',
  '/manifest.json',
];

// ── INSTALL ───────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(cache => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── ACTIVATE ──────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== SHELL_CACHE && k !== ART_CACHE)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── FETCH ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const path = url.pathname;

  // Audio Streaming → immer Netzwerk, kein Cache
  if (path.startsWith('/api/stream')) {
    return; // Browser-Standard verwenden (Range-Requests)
  }

  // Album Art → Cache First, Background Refresh
  if (path.startsWith('/api/art')) {
    event.respondWith(cacheFirstWithRefresh(event.request, ART_CACHE));
    return;
  }

  // API Browse/Search/Verify → Network First
  if (path.startsWith('/api/')) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // App Shell & Icons → Cache First
  event.respondWith(cacheFirst(event.request, SHELL_CACHE));
});

// ── STRATEGIEN ────────────────────────────────────────────────────────────────
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline — kein Cache verfügbar', { status: 503 });
  }
}

async function networkFirst(request) {
  try {
    return await fetch(request);
  } catch {
    const cached = await caches.match(request);
    return cached || new Response(
      JSON.stringify({ error: 'Offline' }), 
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

async function cacheFirstWithRefresh(request, cacheName) {
  const cache  = await caches.open(cacheName);
  const cached = await cache.match(request);
  // Im Hintergrund neu laden
  const fetchPromise = fetch(request).then(response => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);
  return cached || await fetchPromise || new Response('', { status: 404 });
}
