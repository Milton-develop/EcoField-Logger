const CACHE_NAME = 'ecofield-cache-v3';
const urlsToCache = [
  '/',
  '/form',    
  '/home',                          // ← ADDED: cache the form page for offline use
  '/static/css/style.css',
  '/static/manifest.json',
  '/static/data.json',                  // ← ADDED: needed for species dropdown offline
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
  self.skipWaiting(); // ← ADDED: activate SW immediately without waiting
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
  
  if (bypassCachePaths.some(path => url.pathname.includes(path))) {
      return; 
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
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
          // ← ADDED: if offline and navigating, serve the cached /form page
          if (event.request.mode === 'navigate') {
            return caches.match('/form');
          }
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
  self.clients.claim(); // ← ADDED: take control of all open pages immediately
});

// ── INDEXEDDB SETUP FOR SW ─────────────────────────────────────
const DB_NAME = 'EcoFieldDB';
const STORE = 'submissions';

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('synced', 'synced', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function getUnsyncedRecords() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).index('synced').getAll(0);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(tx.error);
  });
}

async function markSynced(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    const req = store.get(id);
    req.onsuccess = () => {
      if (req.result) {
        const record = req.result;
        record.synced = 1;
        store.put(record);
      }
    };
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

async function syncToServerSW() {
  const records = await getUnsyncedRecords();
  if (records.length === 0) return;

  console.log(`[SW] Syncing ${records.length} offline record(s)...`);

  for (const record of records) {
    try {
      const formData = new FormData();
      Object.entries(record).forEach(([key, val]) => {
        if (key === 'photos') {
          val.forEach((photo, i) => formData.append(`offline_photo_${i}`, photo.data));
        } else if (key === 'species_entries' || key === 'new_species_entries') {
          formData.append(key, JSON.stringify(val));
        } else {
          formData.append(key, val);
        }
      });
      formData.append('offline_sync', 'true');

      const res = await fetch('/form', { method: 'POST', body: formData });
      if (res.ok) {
        await markSynced(record.id);
        console.log(`[SW] Record ${record.id} synced successfully!`);
      } else {
        console.warn(`[SW] Record ${record.id} sync failed with status ${res.status}.`);
      }
    } catch (err) {
      console.warn(`[SW] Record ${record.id} sync failed (network error).`);
      throw err; // throw to let Background Sync know it failed and should retry later
    }
  }
}

// ── Background Sync listener ──────────────────────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-ecofield') {
    console.log('[SW] Background sync event triggered');
    event.waitUntil(syncToServerSW());
  }
});
