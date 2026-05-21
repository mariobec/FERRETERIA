/* Service worker PWA Dueño — HTML red; CSS/JS red primero (evita UI vieja tras deploy). */
var CACHE = 'lhexia-guardian-v9';

self.addEventListener('install', function (event) {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k.indexOf('lhexia-owner-pwa-') === 0 && k !== CACHE; })
          .map(function (k) { return caches.delete(k); })
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
    || url.pathname === '/owner-mobile';

  if (isDoc) {
    event.respondWith(
      fetch(event.request).catch(function () {
        return caches.match('/owner-mobile');
      })
    );
    return;
  }

  if (url.pathname.indexOf('/static/owner-pwa/') === 0
      || url.pathname === '/owner-pwa/manifest.webmanifest') {
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
