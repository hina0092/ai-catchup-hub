/* Build inserts the exact files and version; installation is all-or-nothing. */
const VERSION = __BUILD_VERSION__
const FILES = __PRECACHE__
const PREFIX = `techmin-feed:${self.registration.scope}:`
const CACHE = PREFIX + VERSION
const absolute = name => new URL(name, self.registration.scope).href
const resources = new Set(FILES.map(absolute))

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE)
    try {
      await cache.addAll(FILES.map(name => new Request(absolute(name), { cache: 'reload' })))
    } catch (error) {
      await caches.delete(CACHE)
      throw error
    }
  })())
})
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith(PREFIX) && key !== CACHE) await caches.delete(key)
    }
    await self.clients.claim()
  })())
})
self.addEventListener('message', event => {
  if (event.data?.type === 'ACTIVATE_UPDATE') self.skipWaiting()
})
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || !url.href.startsWith(self.registration.scope)) return
  if (event.request.mode === 'navigate') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE)
      return await cache.match(absolute('index.html')) || fetch(event.request)
    })())
    return
  }
  // Public brand files carry a visual revision query; only their pathname is used.
  if (url.pathname.startsWith(new URL('brand/', self.registration.scope).pathname)) url.search = ''
  if (!resources.has(url.href)) return
  event.respondWith((async () => {
    const cache = await caches.open(CACHE)
    return await cache.match(url.href) || fetch(event.request)
  })())
})
