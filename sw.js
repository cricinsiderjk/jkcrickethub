/* CricInsider.jk service worker: shows J&K match alerts */
importScripts("push-config.js");
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
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
