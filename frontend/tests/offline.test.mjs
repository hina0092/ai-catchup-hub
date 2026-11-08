import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { offlineBuild } from '../offlineBuild.js'

function harness({ failInstall = false, version = 'v2' } = {}) {
  const scope = 'https://example.com/ai-catchup-hub/'
  const prefix = `techmin-feed:${scope}:`
  const stores = new Map([[prefix + 'v1', new Map()], ['another-app:v1', new Map()]])
  const handlers = {}, fetched = []
  let claimed = false, skipped = false
  const caches = {
    open: async key => {
      if (!stores.has(key)) stores.set(key, new Map())
      const store = stores.get(key)
      return {
        addAll: async requests => {
          for (const request of requests) {
            if (failInstall && request.url.endsWith('.js')) throw Error('unavailable asset')
            store.set(request.url, { body: request.url })
          }
        },
        match: async url => store.get(String(url)),
      }
    },
    keys: async () => [...stores.keys()],
    delete: async key => stores.delete(key),
  }
  const template = readFileSync(new URL('../sw-template.js', import.meta.url), 'utf8')
    .replace('__BUILD_VERSION__', JSON.stringify(version))
    .replace('__PRECACHE__', JSON.stringify(['index.html', 'assets/app.js', 'brand/icon-48.png']))
  runInNewContext(template, {
    URL, Request, caches,
    fetch: async request => { fetched.push(request.url); return { network: true } },
    self: { registration: { scope }, clients: { claim: async () => { claimed = true } }, skipWaiting: () => { skipped = true }, addEventListener: (name, handler) => { handlers[name] = handler } },
  })
  async function run(name) { let pending; handlers[name]({ waitUntil: value => { pending = value } }); await pending }
  async function request(path, mode = 'cors', method = 'GET') {
    let pending
    handlers.fetch({ request: { url: new URL(path, scope).href, mode, method }, respondWith: value => { pending = value } })
    return pending
  }
  return { scope, prefix, stores, fetched, run, request, handlers, claimed: () => claimed, skipped: () => skipped }
}
test('worker caches a complete subpath shell and serves it offline with revisioned brand URLs', async () => {
  const h = harness()
  await h.run('install'); await h.run('activate')
  assert.equal((await h.request('./#saved', 'navigate')).body, h.scope + 'index.html')
  assert.equal((await h.request('assets/app.js')).body, h.scope + 'assets/app.js')
  assert.equal((await h.request('brand/icon-48.png?v=2')).body, h.scope + 'brand/icon-48.png')
  assert.equal(await h.request('https://outside.example/'), undefined)
  assert.equal(await h.request('assets/app.js', 'cors', 'POST'), undefined)
  assert.deepEqual(h.fetched, [])
  assert.ok(h.claimed())
  assert.ok(h.stores.has('another-app:v1'))
  assert.ok(!h.stores.has(h.prefix + 'v1'))
  h.handlers.message({ data: { type: 'ACTIVATE_UPDATE' } })
  assert.ok(h.skipped())
})
test('failed installation removes only the incomplete new cache and keeps the working version', async () => {
  const h = harness({ failInstall: true })
  await assert.rejects(h.run('install'), /unavailable asset/)
  assert.ok(!h.stores.has(h.prefix + 'v2'))
  assert.ok(h.stores.has(h.prefix + 'v1'))
  assert.ok(h.stores.has('another-app:v1'))
})
test('build derives worker versions from content and precaches exact hashed JS and HTML', () => {
  function build(code) {
    let output
    offlineBuild().generateBundle.call({ emitFile: file => { output = file } }, {}, {
      'index.html': { type: 'asset', source: '<html>app</html>' },
      'assets/app-hash.js': { type: 'chunk', code },
    })
    return output
  }
  const a = build('first'), same = build('first'), next = build('updated daily feed')
  assert.equal(a.fileName, 'sw.js')
  assert.equal(a.source, same.source)
  assert.notEqual(a.source, next.source)
  assert.ok(a.source.includes('index.html'))
  assert.ok(a.source.includes('assets/app-hash.js'))
  assert.ok(!a.source.includes('__PRECACHE__'))
})
