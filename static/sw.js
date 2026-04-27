const CACHE_NAME = 'ecofield-cache-v2';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/manifest.json',
  '/static/images/header.jpg',
  '/static/images/icon-192x192.png',
  '/static/images/icon-512x512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  // 1. Only cache GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // 2. DO NOT cache these dynamic data paths
  const url = new URL(event.request.url);
  const bypassCachePaths = [
    '/group', 
    '/view_group',
    '/admin',
    '/delete_entry'
  ];
  
  // If the request path is in our bypass list, or it's the root URL ('/') but being requested
  // from a form submission or refresh expecting fresh data, bypass cache entirely.
  if (bypassCachePaths.some(path => url.pathname.includes(path))) {
      return; 
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response unless it's the root HTML, 
        // we'll try network first for the root to ensure fresh form data view
        if (response && url.pathname !== '/') {
          return response;
        }

        return fetch(event.request).then(
          function(response) {
            if(!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            var responseToCache = response.clone();

            caches.open(CACHE_NAME)
              .then(function(cache) {
                cache.put(event.request, responseToCache);
              });

            return response;
          }
        ).catch(() => {
          // Optional: return offline fallback here
        });
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
