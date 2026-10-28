/* ==============================================================================
   Pórtico 2D · Service Worker (PWA Offline Real)
   Hito 5 de PLAN_MOVIL.md
   ============================================================================== */

const CACHE_NAME = 'portico2d-cache-v1';

// Recursos locales precacheados en la instalación
const CACHE_STATIC = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './manifest.json',
  './favicon.png',

  // Iconos PWA
  './icons/icon-72.png',
  './icons/icon-96.png',
  './icons/icon-128.png',
  './icons/icon-144.png',
  './icons/icon-152.png',
  './icons/icon-192.png',
  './icons/icon-384.png',
  './icons/icon-512.png',
  './icons/icon-maskable-192.png',
  './icons/icon-maskable-512.png',

  // KaTeX servido localmente (offline)
  './vendor/katex/katex.min.css',
  './vendor/katex/katex.min.js',
  './vendor/katex/fonts/KaTeX_Main-Regular.woff2',
  './vendor/katex/fonts/KaTeX_Main-Bold.woff2',
  './vendor/katex/fonts/KaTeX_Main-Italic.woff2',
  './vendor/katex/fonts/KaTeX_Math-Italic.woff2',
  './vendor/katex/fonts/KaTeX_Math-BoldItalic.woff2',
  './vendor/katex/fonts/KaTeX_Size1-Regular.woff2',
  './vendor/katex/fonts/KaTeX_Size2-Regular.woff2',
  './vendor/katex/fonts/KaTeX_Size3-Regular.woff2',
  './vendor/katex/fonts/KaTeX_Size4-Regular.woff2',

  // Módulos Python (copiados por construir.sh)
  './py/portico2d/__init__.py',
  './py/portico2d/modelo.py',
  './py/portico2d/solver.py',
  './py/portico2d/informe.py',
  './py/portico2d/dibujo.py',
  './py/portico2d/figuras.py',

  // Ejemplos oficiales
  './ejemplos/aplicacion2_portico_QD.json',
  './ejemplos/figura33_profesor.json',
  './ejemplos/figura33_portico_dos_vanos.json',
  './ejemplos/portico_simple.json',
  './ejemplos/viga_continua.json',
  './ejemplos/v02_armadura_triangular.json',
  './ejemplos/v02_portico_brazos_rigidos.json',
  './ejemplos/v02_viga_gerber_rotula.json',
  './ejemplos/v02_viga_trapezoidal_parcial.json'
];

// Instalación: precachear recursos estáticos y activar de inmediato
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async cache => {
      // Intentar agregar los recursos tolerando fallos individuales
      for (const url of CACHE_STATIC) {
        try {
          await cache.add(url);
        } catch (err) {
          console.warn('[SW] No se pudo precachear:', url, err);
        }
      }
    }).then(() => self.skipWaiting())
  );
});

// Activación: reclamar clientes y limpiar versiones antiguas de cache
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

// Intercepción de peticiones (Cache-First con Network Fallback dinámico)
// Garantiza que Pyodide (WASM + wheels de numpy/matplotlib) y fuentes
// queden cacheados tras la primera descarga para uso 100% offline.
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  event.respondWith(
    caches.match(req).then(cached => {
      if (cached) {
        return cached;
      }
      return fetch(req).then(response => {
        // Guardar en cache si la respuesta es exitosa u opaca (CORS de CDN)
        if (response && (response.status === 200 || response.type === 'opaque')) {
          const clon = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(req, clon);
          });
        }
        return response;
      }).catch(err => {
        // Si no hay red y se navega a una página HTML, devolver index.html
        if (req.mode === 'navigate') {
          return caches.match('./index.html');
        }
        throw err;
      });
    })
  );
});
