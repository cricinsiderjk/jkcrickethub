/* CricInsider.jk service worker: shows J&K match alerts */
importScripts("push-config.js");
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
/* App shell: network first, but never wait more than 2.5 s; Firebase library files are cached (they never change for a given version). */
const SHELL = "ci-shell-v2";
const LIB = "ci-lib-v1";
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== LIB).map(k => caches.delete(k))))));
self.addEventListener("fetch", e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET") return;
  if (u.origin === "https://www.gstatic.com" && u.pathname.startsWith("/firebasejs/")) {
    e.respondWith(caches.open(LIB).then(async c => (await c.match(r)) || fetch(r).then(res => { if (res.ok) c.put(r, res.clone()); return res; })));
    return;
  }
  if (u.origin !== self.location.origin) return;
  const key = r.mode === "navigate" ? "./" : u.origin + u.pathname;  // one cache entry per file (ignore ?v=...)
  if (u.pathname.endsWith("/data.json")) {  // the page already shows its saved copy instantly, so here: always fresh, cache only as offline backup
    e.respondWith(caches.open(SHELL).then(c => fetch(r).then(res => { if (res.ok) c.put(key, res.clone()); return res; }).catch(async () => (await c.match(key)) || Response.error())));
    return;
  }
  e.respondWith((async () => {
    const c = await caches.open(SHELL);
    const net = fetch(r).then(res => { if (res && res.ok) c.put(key, res.clone()); return res; });
    const cached = await c.match(key, { ignoreSearch: true });
    if (!cached) return net.catch(async () => (await c.match("./")) || Response.error());
    const timeout = new Promise(res => setTimeout(() => res(cached), 2500));
    return Promise.race([net.catch(() => cached), timeout]);
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
