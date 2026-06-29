const CACHE_NAME = "livealong-cache-v1";
const ASSETS_TO_CACHE = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "/static/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
});

self.addEventListener("fetch", (event) => {
  // On ne mute en cache que les assets statiques, jamais les appels API (/start, /message, /end)
  if (event.request.url.includes("/static/") || event.request.url.endsWith("/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});