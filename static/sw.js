// static/sw.js
const CACHE_NAME = "big-calc-v8"; // Incremented version for MathQuill support
const ASSETS_TO_CACHE = [
    "/",
    "/static/style.css",
    "/static/app.js",
    "/static/calc_worker.js",
    "/static/calc_logic.py",
    "/static/manifest.json",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
    // Cache the LZ-String library
    "https://cdnjs.cloudflare.com/ajax/libs/lz-string/1.4.4/lz-string.min.js",
    // Cache Export libraries
    "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
    // Cache MathQuill & jQuery
    "https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.4/jquery.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/mathquill/0.10.1/mathquill.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/mathquill/0.10.1/mathquill.min.js",
    // Cache CodeMirror CSS/JS (Used in 'Code' mode)
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/codemirror.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/codemirror.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/mode/python/python.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/addon/selection/active-line.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/addon/edit/matchbrackets.min.js"
];

self.addEventListener("install", (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);

    // Always fetch python logic from network during dev to avoid "it didn't change" issues
    if (url.pathname.endsWith("calc_logic.py")) {
         event.respondWith(
            fetch(event.request).catch(() => caches.match(event.request))
        );
        return;
    }

    if (url.origin === location.origin || url.hostname.includes("jsdelivr") || url.hostname.includes("plot.ly") || url.hostname.includes("cloudflare")) {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                const fetchPromise = fetch(event.request).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseToCache);
                        });
                    }
                    return networkResponse;
                });
                return cachedResponse || fetchPromise;
            })
        );
    }
});