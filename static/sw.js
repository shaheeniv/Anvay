// A deliberately empty service worker — Anvay's content is private and
// always changing (new photos, videos, answers), so there's nothing here
// worth caching offline. Its only job is to exist: Chrome/Android will
// only offer a real "Install app" (opens full-screen, own icon) rather
// than a plain bookmark shortcut once a fetch-handling service worker is
// registered, so this is the minimum needed to qualify for that.
self.addEventListener("fetch", function (event) {
  event.respondWith(fetch(event.request));
});
