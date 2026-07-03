/* Service worker — Enrolador Bodega (tablet). HTML siempre red; assets PWA cacheados. */
var CACHE = 'lhexia-bodega-enrolador-v1';

self.addEventListener('install', function (event) {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) {
          return k.indexOf('lhexia-bodega-enrolador-') === 0 && k !== CACHE;
        }).map(function (k) { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (event.request.method !== 'GET') return;
  if (url.pathname.indexOf('/api/') === 0) return;

  var isDoc = event.request.mode === 'navigate'
    || (event.request.headers.get('accept') || '').indexOf('text/html') >= 0
    || url.pathname === '/inventario/enrolamiento/tablet';

  if (isDoc) {
    event.respondWith(
      fetch(event.request).catch(function () {
        return caches.match('/inventario/enrolamiento/tablet');
      })
    );
    return;
  }

  if (url.pathname.indexOf('/static/bodega-enrolador/') === 0
      || url.pathname === '/bodega-enrolador/manifest.webmanifest') {
    event.respondWith(
      fetch(event.request).then(function (res) {
        if (res && res.status === 200) {
          caches.open(CACHE).then(function (cache) {
            cache.put(event.request, res.clone());
          });
        }
        return res;
      }).catch(function () {
        return caches.open(CACHE).then(function (cache) {
          return cache.match(event.request);
        });
      })
    );
  }
});
