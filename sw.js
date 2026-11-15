/* CricInsider.jk service worker: shows J&K match alerts */
importScripts("push-config.js");
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
/* App shell: always try the network first (so the site is never stale), keep a copy for when there's no signal. */
const SHELL = "ci-shell-v1";
self.addEventListener("fetch", e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== self.location.origin) return;
  e.respondWith((async () => {
    try {
      const res = await fetch(r);
      if (res && res.ok) { const c = await caches.open(SHELL); c.put(r.mode === "navigate" ? "./" : r, res.clone()); }
      return res;
    } catch (err) {
      const c = await caches.open(SHELL);
      return (await c.match(r.mode === "navigate" ? "./" : r, { ignoreSearch: true })) || (await c.match("./")) || Response.error();
    }
  })());
});
self.addEventListener("push", e => {
  const W = (self.PUSH_CONFIG || {}).worker;
  e.waitUntil((async () => {
    let list = [];
    try { list = await (await fetch(W + "/latest", { cache: "no-store" })).json(); } catch (err) {}
    const fresh = list.filter(x => Date.now() - x.ts < 3 * 60e3);
    const items = fresh.length ? fresh.slice(0, 2) : [{ id: "jk", title: "CricInsider.jk", body: "New J&K cricket update. Tap to open.", url: "./" }];
    for (const x of items.reverse())
      await self.registration.showNotification(x.title, { body: x.body, tag: x.id, icon: "icon.svg", badge: "icon.svg", data: { url: x.url } });
  })());
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "./";
  e.waitUntil(self.clients.openWindow(url));
});
