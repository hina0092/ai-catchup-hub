import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { trialStories } from '../src/prototype/trialStories.js'
import { readerSnapshot } from '../src/readerSnapshots.js'

const cast = JSON.parse(readFileSync(new URL('../src/commenters.json', import.meta.url), 'utf8'))
const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
after(() => server.close())
const { default: Avatar } = await server.ssrLoadModule('/src/components/CommentAvatar.vue')
const { default: FeedView } = await server.ssrLoadModule('/src/prototype/FeedView.vue')

test('all eight approved avatars resolve to local images independently of article order', async () => {
  assert.equal(cast.length, 8)
  const urls = new Set()
  for (const person of cast) {
    assert.ok(existsSync(new URL(`../src/assets/commenters/${person.avatar}`, import.meta.url)))
    const html = await renderToString(createSSRApp(Avatar, { name: person.name }))
    assert.match(html, /aria-hidden="true"/)
    assert.match(html, /alt=""/)
    const src = html.match(/src="([^"]+)"/)[1]
    assert.ok(src.endsWith(person.avatar))
    urls.add(src)
  }
  assert.equal(urls.size, 8)
})

test('editorial examples use varied groups of three or four, eight comments and valid earlier replies', () => {
  let previous = ''
  for (const story of trialStories) {
    const names = [...new Set(story.comments.map(row => row[0]))].sort()
    assert.ok([3, 4].includes(names.length))
    assert.ok(names.every(name => cast.some(person => person.name === name)))
    assert.notEqual(names.join(','), previous)
    previous = names.join(',')
    assert.equal(story.comments.length, 8)
    story.comments.forEach(([, , reply, parent], index) => {
      if (reply) assert.ok(Number.isInteger(parent) && parent >= 0 && parent < index)
    })
    assert.equal(story.teaser, story.comments[0][1])
    readerSnapshot(story)
  }
})

test('old speakers retain their names and text with a neutral avatar in saved articles', async () => {
  const old = structuredClone(trialStories[0])
  old.comments[0][0] = '昔の常連'
  const saved = readerSnapshot(old)
  const html = await renderToString(createSSRApp(FeedView, { stories: [saved], publicMode: true }))
  assert.match(html, /昔の常連/)
  const avatar = await renderToString(createSSRApp(Avatar, { name: '昔の常連' }))
  assert.doesNotMatch(avatar, /<img/)
  assert.match(avatar, /<svg/)
  assert.doesNotMatch(avatar, /👤/)
})
