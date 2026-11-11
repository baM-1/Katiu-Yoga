// Service worker mínimo de Katiu Yoga.
// - Estáticos (CSS, JS, iconos): "cache first" → la app abre al instante aunque falle la red.
// - Páginas: "network first" → siempre datos frescos; sin red, la última versión vista o un aviso.
// - Nunca se cachean POST (marcar asistencia, cobrar): eso tiene que llegar al servidor.
const VERSION = "katiu-v1";
const STATIC = [
  "/static/css/tokens.css", "/static/css/base.css", "/static/css/components.css",
  "/static/css/utilities.css", "/static/js/htmx.min.js", "/static/js/app.js",
  "/static/img/logo-katiu-yoga.png", "/static/icons/icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
    return;
  }
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || offlinePage()))
    );
  }
});

function offlinePage() {
  return new Response(
    "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>" +
    "<body style='font-family:system-ui;padding:2rem;background:#FBF7EF;color:#14384A'>" +
    "<h1>Sin conexión 🌊</h1><p>En cuanto vuelva la cobertura, recarga.</p>",
    { headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}
