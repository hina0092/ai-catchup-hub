import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { dailyStories, displayTime } from '../src/dailyStories.js'

const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
after(() => server.close())
const { default: PublicFeed } = await server.ssrLoadModule('/src/PublicFeed.vue')
const { default: FeedView } = await server.ssrLoadModule('/src/prototype/FeedView.vue')
const deployed = JSON.parse(readFileSync(new URL('../src/daily-feed.json', import.meta.url), 'utf8'))
const fixture = {
  format:1, checked_at:'2026-10-25T19:18:00+09:00', updated_at:'2026-10-25T19:18:00+09:00',status:'ready',
  entries:[{id:'a01234567890123456789',url:'https://zenn.dev/example/articles/daily',source:'Zenn AI',published_on:'2026-10-25',generated_at:'2026-10-25T19:18:00+09:00',article_kind:'guide',card:{
    title:'AIの作業を引き継ぐ',lead:'会話を引き継ぐ手順です。',changed:'公式の手順ガイドです。',example:'記事の手順を確認する例。',caution:'条件は元記事で確認してください。',
    diagram:null, comments:Array.from({length:8},(_,i)=>({name:i%2?'返す人':'聞く人',text:`論点${i}を確認したい。`,reply_to:i%2?i-1:null})),
  }}],
}
test('deployed export renders without preview links and describes automatic updates honestly', async () => {
  dailyStories(deployed)
  const html = await renderToString(createSSRApp(PublicFeed))
  assert.match(html,/朝6時までの更新を目標/)
  assert.match(html,/前夜23:17と午前0:17/)
  assert.match(html,/AIによる架空の会話/)
  assert.doesNotMatch(html,/catchup-preview\.html|LOCAL PREVIEW/)
  assert.equal((html.match(/<article /g)||[]).length,deployed.entries.length||5)
})
test('automatic stories retain generated text, reply targets, null diagram, and source date', async () => {
  const [story] = dailyStories(fixture)
  assert.equal(story.comments.length,8)
  assert.equal(story.comments[1][3],0)
  assert.deepEqual(story.inputs,[])
  assert.equal(story.date,'2026/10/25')
  assert.equal(story.changed,fixture.entries[0].card.changed)
  const html = await renderToString(createSSRApp(FeedView,{stories:[story],publicMode:true,edition:{generated:true,updated:'2026/10/25 19:18',checked:'2026/10/25 19:18',message:'新しい記事を追加しました。'}}))
  assert.match(html,/新しい記事を追加しました/)
  assert.doesNotMatch(html,/固定記事|見本5件|2026\/10\/24版/)
})
test('invalid URLs, dates, replies and missing fields are rejected before deployment', () => {
  for (const mutate of [f=>f.entries[0].url='javascript:alert(1)',f=>f.entries[0].published_on='2026-02-31',
    f=>f.entries[0].card.comments[0].reply_to=true,f=>f.entries[0].card.title='',f=>f.entries.push(structuredClone(f.entries[0]))]) {
    const f=structuredClone(fixture);mutate(f);assert.throws(()=>dailyStories(f))
  }
})
test('display time is explicitly JST and unknown time does not claim a successful update', () => {
  assert.match(displayTime('2026-10-25T10:18:00Z'),/2026\/10\/25 19:18/)
  assert.equal(displayTime(null),'未実行')
})

test('official OpenAI and Google articles and comparison diagrams render while lookalike hosts fail', () => {
  for (const host of ['openai.com', 'blog.google', 'www.anthropic.com']) {
    const feed = structuredClone(fixture)
    feed.entries[0].url = `https://${host}/article/`
    feed.entries[0].card.diagram = { layout:'compare', question:'何が違う？', nodes:['変更前：名前だけ', '変更後：内容も説明'], result:'判断材料の違い' }
    assert.equal(dailyStories(feed)[0].layout, 'compare')
    feed.entries[0].url = `https://${host}.evil.test/article/`
    assert.throws(() => dailyStories(feed))
    feed.entries[0].url = `https://${host}/article/`
    feed.entries[0].card.diagram.nodes.push('第三の項目')
    assert.throws(() => dailyStories(feed))
  }
})
