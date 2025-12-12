// static/sw.js
const CACHE_NAME = "big-calc-v2";
const ASSETS_TO_CACHE = [
    "/",
    "/static/style.css",
    "/static/app.js",
    "/static/calc_worker.js",
    "/static/calc_logic.py",
    "/static/manifest.json",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png"
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);

    // Strategy: Stale-While-Revalidate for app files, Cache-First for CDN/Pyodide
    if (url.origin === location.origin || url.hostname.includes("jsdelivr")) {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                // Return cache if found
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                // Otherwise fetch, return, and cache for next time
                return fetch(event.request).then((networkResponse) => {
                    // Check if valid response
                    if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic' && networkResponse.type !== 'cors') {
                        return networkResponse;
                    }

                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });

                    return networkResponse;
                });
            })
        );
    }
});