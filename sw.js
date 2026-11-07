/** MP3z: only public icons/manifest may be cached. Never cache login or API. */
const PUBLIC_CACHE = 'mp3z-public-v2';
const PUBLIC_ASSETS = new Set(['/manifest.json', '/icon-192.png', '/icon-512.png']);

self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith('mp3z-') && k !== PUBLIC_CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/agent/')) return;
  if (!url.search && PUBLIC_ASSETS.has(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(PUBLIC_CACHE);
      const hit = await cache.match(request);
      if (hit) return hit;
      const response = await fetch(request);
      if (response.ok) await cache.put(request, response.clone());
      return response;
    })());
    return;
  }
  event.respondWith(fetch(request, {cache: 'no-store'}).catch(() =>
    new Response('MP3z ist offline. Fuer die Anmeldung ist eine Verbindung zum Server erforderlich.',
      {status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store'}})
  ));
});
