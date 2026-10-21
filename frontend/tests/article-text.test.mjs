import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
after(() => server.close())
const { default: ArticleText } = await server.ssrLoadModule('/src/components/ArticleText.vue')
const article = { title:'Original title', summary:'Original excerpt', url:'https://example.com' }
const render = data => renderToString(createSSRApp(ArticleText, {article:data}))
test('legacy JSON renders original title and excerpt', async () => {
  const html = await render(article)
  assert.match(html, /Original title/)
  assert.match(html, /Original excerpt/)
  assert.doesNotMatch(html, /AI翻訳/)
})
test('Japanese enrichment retains original and source link', async () => {
  const html = await render({...article, translation:{language:'ja', title_ja:'翻訳した見出し', summary_ja:'日本語の要約'}})
  for (const value of ['翻訳した見出し','日本語の要約','Original title','AI翻訳','https://example.com']) assert.ok(html.includes(value))
})
test('untrusted text is escaped and invalid translation falls back', async () => {
  const html = await render({...article, title:'<script>alert(1)</script>', translation:{title_ja:42}})
  assert.doesNotMatch(html, /<script>/)
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /Original excerpt/)
})
test('title-only translation works without a public excerpt', async () => {
  const html = await render({title:'Original', url:article.url, translation:{language:'ja',title_ja:'日本語',summary_ja:null}})
  assert.match(html, /詳しい内容は元記事/)
  assert.doesNotMatch(html, /RSS説明文のAI要約/)
})
