/* Service worker mínimo — shell PWA Dueño (sin cachear API). */
var CACHE = 'lhexia-owner-pwa-v4';
var SHELL = [
  '/owner-mobile',
  '/static/owner-pwa/owner-dashboard.css',
  '/static/owner-pwa/owner-dashboard.js',
  '/static/css/bootstrap.css',
  '/static/vendor/fontawesome/css/all.min.css',
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(SHELL).catch(function () {});
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function (event) {
  var url = new URL(event.request.url);
  if (url.pathname.indexOf('/api/') === 0) {
    return;
  }
  if (event.request.method !== 'GET') {
    return;
  }
  event.respondWith(
    caches.match(event.request).then(function (cached) {
      return (
        cached ||
        fetch(event.request).then(function (res) {
          if (res && res.status === 200 && url.origin === self.location.origin) {
            var copy = res.clone();
            caches.open(CACHE).then(function (c) {
              c.put(event.request, copy);
            });
          }
          return res;
        })
      );
    })
  );
});
