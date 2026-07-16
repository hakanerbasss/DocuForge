// Bump this on every deploy that changes anything under /static/ so
// clients drop the old cache instead of serving stale assets.
const CACHE = 'docuforge-v1';

const SHELL = [
  '/static/manifest.json',
  '/static/icons/icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

// DocuForge's pages ARE its live state -- job progress, project lists,
// pipeline status -- rendered server-side on every request. There is no
// static "app shell" HTML to cache the way a typical SPA has: caching a
// page here would mean showing a stale build status or project list,
// online or off. So only /static/* (manifest, icons) is cache-first;
// everything else -- every page, /api/*, /files/* -- always goes
// straight to the network. This service worker exists mainly to satisfy
// the "installable" requirement, not to provide offline functionality.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (url.origin !== self.location.origin || !url.pathname.startsWith('/static/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
