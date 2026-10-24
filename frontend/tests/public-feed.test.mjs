import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { trialStories } from '../src/prototype/trialStories.js'

const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
after(() => server.close())
const { default: FeedView } = await server.ssrLoadModule('/src/prototype/FeedView.vue')

test('public entry renders five editorial stories without preview navigation or unreviewed generation', async () => {
  const html = await renderToString(createSSRApp(FeedView, { stories: trialStories, publicMode: true }))
  assert.equal((html.match(/<article /g) || []).length, 5)
  assert.equal((html.match(/コメントを読む/g) || []).length, 5)
  assert.match(html, /2026\/10\/24時点の固定記事/)
  assert.match(html, /ニュースの自動更新は準備中/)
  assert.match(html, /AIによる架空の会話/)
  assert.doesNotMatch(html, /catchup-preview\.html|LOCAL PREVIEW|新発表です。|スマホなどのアプリ/)
  for (const story of trialStories) assert.ok(html.includes(story.url))
})
