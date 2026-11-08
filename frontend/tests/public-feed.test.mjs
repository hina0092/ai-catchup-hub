import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { trialStories } from '../src/prototype/trialStories.js'

const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
after(() => server.close())
const { default: FeedView } = await server.ssrLoadModule('/src/prototype/FeedView.vue')
const { default: FeedFilters } = await server.ssrLoadModule('/src/components/FeedFilters.vue')

test('search belongs to the header and keeps inactive counts out of the reading surface', async () => {
  const filters = { query: '', source: '', category: '', unreadOnly: false }
  const html = await renderToString(createSSRApp({ render: () => h(FeedView, { stories: trialStories, publicMode: true }, {
    search: () => h(FeedFilters, { filters, options: { sources: [], categories: [] }, count: 5, total: 5 }),
  }) }))
  const header = html.match(/<header\b[\s\S]*?<\/header>/)[0]
  assert.match(header, /aria-label="記事を検索"/)
  assert.match(header, /placeholder="キーワードで記事を検索"/)
  assert.match(header, /aria-label="絞り込み"/)
  assert.doesNotMatch(header, /5件中 5件/)
  assert.doesNotMatch(html.match(/<main\b[\s\S]*?<\/main>/)[0], /class="feed-filters"/)
})

test('active search exposes its count and reset without opening source selectors', async () => {
  const html = await renderToString(createSSRApp(FeedFilters, {
    filters: { query: '課金', source: '', category: '', unreadOnly: false }, options: { sources: ['AWS'], categories: [] }, count: 1, total: 5,
  }))
  assert.match(html, /5件中 1件/)
  assert.match(html, /条件をクリア/)
  assert.doesNotMatch(html, /<select/)
})

test('Techmin branding keeps source-linked stories and navigation without redundant browser chrome or catchphrase', async () => {
  const story = { ...trialStories[0], title: '今回の表示記事', category: '実データの分類' }
  const html = await renderToString(createSSRApp(FeedView, { stories: [story], publicMode: true, saveEnabled: true }))
  assert.match(html, /aria-label="Techmin Feed ホーム"/)
  assert.match(html, /Tech<span class="brand-mint">min<\/span> Feed/)
  assert.match(html, /YOUR DAILY TECH FIX/)
  assert.match(html, /brand\/mint-loppy-game\.jpg/)
  assert.match(html, /aria-label="1件目：今回の表示記事"/)
  assert.match(html, /class="nav-story"><strong>今回の表示記事<\/strong><span>実データの分類<\/span>/)
  assert.match(html, /実データの分類/)
  assert.doesNotMatch(html, /browser-chrome|browser-address|mobile-catchphrase|ちょっと気になる。|読んだら、わかる。/)
  assert.match(html, /<h1 class="brand-name">Tech/)
  assert.match(html, /<div class="reader-toolbar"><header/)
  const header = html.match(/<header\b[\s\S]*?<\/header>/)[0]
  assert.doesNotMatch(header, /reader-tabs/)
  assert.match(html, /<\/header><nav class="reader-tabs" aria-label="記事の表示">/)
  assert.match(html, /brand\/discover-pc\.svg/)
  assert.match(html, /brand\/saved-folder\.svg/)
  assert.match(html, /会話ルーム/)
  assert.match(html, /発見/)
  assert.match(html, /保存済み/)
  assert.ok(html.includes(story.url))
  assert.doesNotMatch(html, /AI Catchup Hub|いいね数|通知設定/)
})

test('public entry renders five editorial stories without preview navigation or unreviewed generation', async () => {
  const html = await renderToString(createSSRApp(FeedView, { stories: trialStories, publicMode: true }))
  assert.equal((html.match(/<article /g) || []).length, 5)
  assert.equal((html.match(/全8件の会話を開く/g) || []).length, 5)
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
  assert.equal((comments.match(/class="comment-body preview-bubble"/g) || []).length, story.comments.length)
  const conversation = html.slice(html.indexOf(`id="comments-${story.id}"`)).split('</section>')[0]
  assert.match(conversation, /class="fiction-notice">AIの架空会話 · 全8件<\/span>/)
  assert.doesNotMatch(conversation, /<p class="fiction-notice"|実在の投稿・利用者の声ではありません/)
  for (const [name, text] of story.comments) {
    assert.ok(html.includes(name))
    assert.ok(html.includes(text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')))
  }
  assert.match(html, /全8件/)
  assert.match(html, /保存する：/)
  assert.match(html, /AIに聞く：/)
  assert.doesNotMatch(html, /続きを読む|<dialog/)
})

test('article byline uses its source and a topic sticker while repeated speakers keep their avatar', async () => {
  const story = { ...trialStories[0], source: '取得元 <著者>', emoji: '🎙️' }
  const html = await renderToString(createSSRApp(FeedView, { stories: [story], publicMode: true }))
  const bylineIcon = html.match(/class="publisher-avatar" aria-hidden="true">([\s\S]*?)<\/span>/)[1]
  assert.match(bylineIcon, /<svg/)
  assert.match(bylineIcon, /class="topic-sticker" data-kind="audio"/)
  assert.doesNotMatch(bylineIcon, /🎙/)
  assert.match(html, /<strong>取得元 &lt;著者&gt;<\/strong>/)
  assert.doesNotMatch(html, /<strong>AI Catchup Hub<\/strong>/)
  const comments = html.slice(html.indexOf('<ol class="comments">')).split('</ol>')[0]
  const avatars = [...comments.matchAll(/<img[^>]+src="([^"]+)"/g)].map(match => match[1])
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

test('pixel topic avatars match between navigation and articles and retain a legacy fallback', async () => {
  const stories = [
    { ...trialStories[0], id: 'research-icon', emoji: '🔬', category: 'AIの研究' },
    { ...trialStories[1], id: 'guide-icon', emoji: '🧭', category: '使い方としくみ' },
    { ...trialStories[2], id: 'legacy-icon', emoji: '？', category: '以前の分類' },
  ]
  const original = structuredClone(stories)
  const html = await renderToString(createSSRApp(FeedView, { stories, publicMode: true }))
  for (const kind of ['research', 'guide', 'chip']) {
    assert.equal((html.match(new RegExp(`data-kind="${kind}"`, 'g')) || []).length, 2)
  }
  assert.equal((html.match(/shape-rendering="crispEdges"/g) || []).length, 6)
  assert.equal((html.match(/viewBox="0 0 16 16"/gi) || []).length, 6)
  assert.deepEqual(stories, original)
})

test('reader opens conversations from the preview and keeps article actions below the conversation', async () => {
  const html = await renderToString(createSSRApp(FeedView, { stories: trialStories.slice(0, 2), publicMode: true, saveEnabled: true }))
  assert.doesNotMatch(html, /もっとこれ|好きなテーマ/)
  assert.doesNotMatch(html, /次の発見へ/)
  const articles = [...html.matchAll(/<article\b[\s\S]*?<\/article>/g)].map(match => match[0])
  for (const article of articles) {
    const actions = article.match(/<div class="actions">([\s\S]*?)<\/div>/)[1]
    assert.equal((actions.match(/<button\b/g) || []).length, 2)
    assert.match(article, /class="comment-preview" role="button" tabindex="0" aria-expanded="false"/)
    assert.match(article, /全8件の会話を開く/)
    assert.doesNotMatch(article, /クリックで会話を開く/)
    assert.doesNotMatch(actions, /read-comments|会話を読む/)
    assert.ok(article.indexOf('class="actions"') > article.indexOf('class="conversation-end-actions"'))
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
  assert.match(html, /毎朝の更新を目指して、1日最大3件/)
  assert.doesNotMatch(html, /前夜23:17と午前0:17/)
  assert.match(html, /2026\/10\/24の見本5件/)
})

test('daily counts remain independent of filtering and offline readiness lives inside details', async () => {
  const props = { stories: [], publicMode: true, edition: { generated: true, updated: '2026/11/9 5:00', checked: '2026/11/9 5:30', additions: { label: '11/9：2件追加', date: '2026/11/9', complete: true } } }
  const render = savedView => renderToString(createSSRApp({ render: () => h(FeedView, { ...props, savedView }, {
    'offline-status': () => h('p', { class: 'offline-ready' }, 'オフラインの準備ができています'),
  }) }))
  const html = await render(false)
  const details = html.match(/<details\b[\s\S]*?<\/details>/)[0]
  assert.match(details, /11\/9：2件追加/)
  assert.doesNotMatch(details, /集計日：|（日本時間）|説明・図・会話はAI生成です/)
  assert.match(details, /オフラインの準備ができています/)
  assert.equal((html.match(/オフラインの準備ができています/g) || []).length, 1)
  const saved = await render(true)
  assert.doesNotMatch(saved, /edition-status/)
  assert.match(saved.match(/<footer\b[\s\S]*?<\/footer>/)[0], /オフラインの準備ができています/)
})

test('read and share controls retain all existing actions and stable article anchors', async () => {
  const story = trialStories[0]
  const html = await renderToString(createSSRApp(FeedView, {
    stories: [story], publicMode: true, saveEnabled: true, readEnabled: true, shareEnabled: true, readUrls: new Set([story.url]),
  }))
  assert.match(html, new RegExp(`id="story-${story.id}"`))
  assert.match(html, /✓ 読んだ/)
  assert.match(html, /未読に戻す/)
  assert.match(html, /保存する：/)
  assert.match(html, /AIに聞く：/)
  assert.match(html, /シェア/)
  assert.doesNotMatch(html, /記事リンクをコピー|copy-article-link/)
  assert.match(html, /aria-controls="share-options-polly"/)
  const actions = html.slice(html.indexOf('<div class="actions">')).split('</article>')[0]
  assert.equal((actions.match(/<button\b/g) || []).length, 4)
  assert.equal((html.match(/class="comment-body preview-bubble"/g) || []).length, 8)
})

test('filtering to zero never changes the edition source count', async () => {
  const html = await renderToString(createSSRApp(FeedView, {
    stories: [], publicMode: true, edition: { count: 5, generated: false, updated: '未実行', checked: '未実行' },
  }))
  assert.match(html, /見本5件を表示中/)
  assert.doesNotMatch(html, /見本0件を表示中/)
})

test('undo feedback stays outside the feed and keeps an interactive undo action', async () => {
  const html = await renderToString(createSSRApp({ render: () => h(FeedView, { stories: trialStories, publicMode: true }, {
    feedback: () => h('div', { class: 'read-feedback' }, ['読了にしました', h('button', '元に戻す')]),
  }) }))
  assert.doesNotMatch(html.match(/<main\b[\s\S]*?<\/main>/)[0], /読了にしました|元に戻す/)
  assert.match(html, /class="[^"]*toast-actionable[^"]*" role="status"/)
  assert.match(html, /<button>元に戻す<\/button>/)
})
