// Service worker mínimo: permite instalar o app. Os dados sempre vêm ao vivo da ponte.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
