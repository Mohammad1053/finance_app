// Minimal service worker: it makes the app installable but never caches anything,
// so financial data is always fresh from the server.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {
  // No handler logic: the browser performs the normal network request
});
