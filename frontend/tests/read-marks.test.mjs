import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createReadRepository, decodeReadMarks, READ_STORAGE_KEY, MAX_READ_ITEMS } from '../src/readMarks.js'
function memory(raw = null) { return { getItem: () => raw, setItem: (key, value) => { assert.equal(key, READ_STORAGE_KEY); raw = value } } }
test('read marks reload, unmark, and share the same URL across current and saved stories', () => {
  const storage = memory(), repo = createReadRepository(() => storage)
  repo.load(); repo.setRead('https://example.com/a', true)
  const other = createReadRepository(() => storage)
  assert.equal(other.load().items[0].url, 'https://example.com/a')
  assert.deepEqual(other.setRead('https://example.com/a', false).items, [])
})
test('corrupt storage is not overwritten and quota failures retain in-memory changes', () => {
  const storage = memory('{broken'), repo = createReadRepository(() => storage)
  assert.ok(repo.load().warning)
  assert.equal(repo.setRead('https://example.com/a', true).items.length, 1)
  assert.equal(storage.getItem(), '{broken')
  const quota = createReadRepository(() => ({ getItem: () => null, setItem: () => { throw Error('quota') } }))
  quota.load(); assert.ok(quota.setRead('https://example.com/a', true).warning)
  assert.equal(quota.state().items.length, 1)
})
test('invalid entries are rejected and retention removes the oldest timestamp', () => {
  for (const item of [{ url: 'javascript:alert(1)', read_at: '2026-11-08' }, { url: 'https://example.com/a', read_at: 'invalid' }]) {
    assert.throws(() => decodeReadMarks(JSON.stringify({ version: 1, items: [item] })))
  }
  const entries = Array.from({ length: MAX_READ_ITEMS }, (_, i) => ({ url: `https://example.com/${i}`, read_at: new Date(i * 1000).toISOString() }))
  const repo = createReadRepository(() => memory(JSON.stringify({ version: 1, items: entries })))
  repo.load()
  const result = repo.setRead('https://example.com/new', true)
  assert.equal(result.items.length, MAX_READ_ITEMS)
  assert.ok(!result.items.some(item => item.url.endsWith('/0')))
})
