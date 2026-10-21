import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { discussionHash, routeFromHash, sectionsFor } from '../src/discussion.js'
const server = await createServer({server:{middlewareMode:true,hmr:false,ws:false}, appType:'custom'})
after(() => server.close())
const { default: Detail } = await server.ssrLoadModule('/src/components/DiscussionDetail.vue')
const article = {title:'テスト記事',url:'https://example.com/a?x=1#part',
  discussion:{provider:'hacker_news',story_id:1,comment_count:12},
  discussion_analysis:{story_id:1,sample_count:1,evidence_comments:[{id:2}],sections:[{kind:'experience',
    points:[{text_ja:'使って時間を短縮したという意見。',evidence:[{comment_id:2,quote:'I used it and saved time.'}]}]}]}}
const render = data => renderToString(createSSRApp(Detail,{article:data}))
test('hash routes round trip including query and fragment', () => {
  assert.equal(routeFromHash(discussionHash(article)), article.url)
  assert.equal(routeFromHash('#feed'), '')
  assert.equal(routeFromHash('#discussion=%broken'), '__missing__')
})
test('grounded details include original, discussion, and comment links', async () => {
  const html = await render(article)
  for (const text of ['実際の使用経験','AIによる議論分析','議論全体の総意ではありません','item?id=1','item?id=2','I used it']) assert.ok(html.includes(text),text)
  assert.doesNotMatch(html,/懸念・反対意見/)
})
test('unknown IDs and mismatched story analysis are omitted', () => {
  const bad = structuredClone(article)
  bad.discussion_analysis.sections[0].points[0].evidence[0].comment_id = 999
  assert.deepEqual(sectionsFor(bad),[])
  bad.discussion_analysis.story_id = 2
  assert.deepEqual(sectionsFor(bad),[])
})
test('missing analysis retains source and HN links', async () => {
  const html = await render({...article,discussion_analysis:undefined})
  assert.match(html,/表示できる分析はまだありません/)
  assert.match(html,/item\?id=1/)
  assert.match(html,/元記事を読む/)
})
test('untrusted text is escaped and arbitrary evidence URLs ignored', async () => {
  const bad = structuredClone(article)
  bad.discussion_analysis.sections[0].points[0].text_ja = '<script>攻撃</script>'
  bad.discussion_analysis.evidence_comments[0].url = 'javascript:alert(1)'
  bad.discussion.url = 'javascript:alert(1)'
  const html = await render(bad)
  assert.doesNotMatch(html,/<script>|javascript:/)
  assert.match(html,/&lt;script&gt;/)
  assert.match(html,/item\?id=2/)
})
test('legacy articles render a safe empty state', async () => {
  const html = await render({title:'旧記事',url:'javascript:alert(1)'})
  assert.match(html,/表示できる分析はまだありません/)
  assert.doesNotMatch(html,/javascript:/)
})
test('App renders on server without browser globals during setup', async () => {
  const {default:App} = await server.ssrLoadModule('/src/App.vue')
  assert.match(await renderToString(createSSRApp(App)), /記事を読み込んでいます/)
})
