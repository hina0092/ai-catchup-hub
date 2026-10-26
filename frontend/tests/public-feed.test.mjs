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
  assert.equal((html.match(/会話を読む/g) || []).length, 5)
  assert.match(html, /2026\/10\/24時点の固定記事/)
  assert.match(html, /ニュースの自動更新は準備中/)
  assert.match(html, /AIによる架空の会話/)
  assert.doesNotMatch(html, /catchup-preview\.html|LOCAL PREVIEW|新発表です。|スマホなどのアプリ/)
  for (const story of trialStories) assert.ok(html.includes(story.url))
})

test('timeline keeps every comment inline with its reply target and an accessible toggle', async () => {
  const story = trialStories[0]
  const html = await renderToString(createSSRApp(FeedView, { stories: [story], publicMode: true, saveEnabled: true }))
  assert.match(html, /class="publisher-avatar"/)
  assert.ok(html.includes(`aria-controls="comments-${story.id}"`))
  assert.match(html, /aria-expanded="false"/)
  const comments = html.slice(html.indexOf('<ol class="comments">')).split('</ol>')[0]
  assert.equal((comments.match(/<li[ >]/g) || []).length, story.comments.length)
  for (const [name, text] of story.comments) {
    assert.ok(html.includes(name))
    assert.ok(html.includes(text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')))
  }
  assert.match(html, /全8件/)
  assert.match(html, /保存する：/)
  assert.match(html, /AIに聞く：/)
  assert.doesNotMatch(html, /続きを読む|<dialog/)
})

test('article byline uses its source and topic emoji and repeated speakers keep their avatar', async () => {
  const story = { ...trialStories[0], source: '取得元 <著者>', emoji: '🎙️' }
  const html = await renderToString(createSSRApp(FeedView, { stories: [story], publicMode: true }))
  assert.match(html, /class="publisher-avatar" aria-hidden="true">🎙️<\/span>/)
  assert.match(html, /<strong>取得元 &lt;著者&gt;<\/strong>/)
  assert.doesNotMatch(html, /<strong>AI Catchup Hub<\/strong>/)
  const comments = html.slice(html.indexOf('<ol class="comments">')).split('</ol>')[0]
  const avatars = [...comments.matchAll(/class="comment-avatar" aria-hidden="true">([^<]+)<\/span>/g)].map(match => match[1])
  assert.equal(avatars.length, story.comments.length)
  const assigned = new Map()
  story.comments.forEach(([name], index) => {
    if (assigned.has(name)) assert.equal(avatars[index], assigned.get(name))
    else assigned.set(name, avatars[index])
  })
  assert.ok(new Set(avatars).size > 1)
  const card = html.match(/<a class="source-card"[\s\S]*?<\/a>/)[0]
  assert.match(card, /元記事を読む/)
  assert.match(card, /取得元 &lt;著者&gt; · aws\.amazon\.com/)
  assert.ok(card.includes(`href="${story.url}"`))
  assert.match(card, /target="_blank" rel="noopener noreferrer"/)
})

test('reader offers three article actions and end-of-conversation navigation without a next link on the last story', async () => {
  const html = await renderToString(createSSRApp(FeedView, { stories: trialStories.slice(0, 2), publicMode: true, saveEnabled: true }))
  assert.doesNotMatch(html, /もっとこれ|好きなテーマ/)
  const articles = [...html.matchAll(/<article\b[\s\S]*?<\/article>/g)].map(match => match[0])
  for (const article of articles) {
    const actions = article.match(/<div class="actions">([\s\S]*?)<\/div>/)[1]
    assert.equal((actions.match(/<button\b/g) || []).length, 3)
    assert.match(article, /会話を閉じる ↑/)
  }
  assert.match(articles[0], /次の記事へ ↓/)
  assert.doesNotMatch(articles[1], /次の記事へ ↓/)
})

test('update notice starts collapsed while preserving status, schedule and fallback explanation', async () => {
  const html = await renderToString(createSSRApp(FeedView, {
    stories: trialStories, publicMode: true,
    edition: { generated: false, checked: '未実行', updated: '未実行', message: '初回の自動更新を待っています。' },
  }))
  assert.match(html, /<details class="edition-status">/)
  assert.match(html, /見本5件を表示中/)
  assert.match(html, /更新の詳細/)
  assert.match(html, /初回の自動更新を待っています/)
  assert.match(html, /毎日19:17/)
  assert.match(html, /2026\/10\/24の見本5件/)
})
