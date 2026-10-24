import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { trialStories } from '../src/prototype/trialStories.js'
import { readerSnapshot, savedReaderStories } from '../src/readerSnapshots.js'
import { createSavedRepository, STORAGE_KEY } from '../src/savedArticles.js'

const story = trialStories[0]
const wrapped = s => ({url:s.url,title:s.title,source:s.source,reader_story:s})
const clock = () => '2026-10-25T10:00:00Z'
function memory() {
  const data = new Map()
  return {getItem:k => data.get(k) ?? null,setItem:(k,v) => data.set(k,v)}
}
const server = await createServer({server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'})
after(() => server.close())
const {default:FeedView} = await server.ssrLoadModule('/src/prototype/FeedView.vue')

test('bookmarks retain explanation, diagram and all comments after reload and feed removal', () => {
  const storage=memory(),repo=createSavedRepository(() => storage,clock)
  repo.load()
  repo.bookmark(wrapped(story))
  const reloaded=createSavedRepository(() => storage,clock)
  const items=reloaded.load().items
  const [saved]=savedReaderStories(items,[])
  assert.equal(saved.changed,story.changed)
  assert.deepEqual(saved.inputs,story.inputs)
  assert.equal(saved.comments.length,8)
  assert.deepEqual(saved.comments.map(r=>r.slice(0,3)),story.comments.map(r=>[r[0],r[1],Boolean(r[2])]))
  assert.equal(saved.saved_snapshot,true)
  assert.equal(reloaded.bookmark(wrapped(story)).items.length,0)
})
test('old label saves survive new bookmarks and can be removed in one action', () => {
  const storage=memory(),repo=createSavedRepository(() => storage,clock)
  const old={url:'https://example.com/old',title:'以前の記事',source:'RSS'}
  repo.load();repo.toggle(old,'try');repo.toggle(old,'work')
  repo.bookmark(wrapped(story))
  assert.equal(repo.state().items.length,2)
  assert.deepEqual(repo.state().items.find(i=>i.url===old.url).labels,['try','work'])
  repo.bookmark(old)
  assert.equal(repo.state().items.length,1)
  assert.equal(repo.state().items[0].url,story.url)
})
test('current data wins when available without mutating the saved snapshot', () => {
  const repo=createSavedRepository(memory,clock)
  repo.bookmark(wrapped(story))
  const current={...story,lead:'更新された説明'}
  assert.equal(savedReaderStories(repo.state().items,[current])[0],current)
  assert.equal(repo.state().items[0].article.reader_story.lead,story.lead)
})
test('unsafe or corrupted reader snapshots are rejected and existing storage is preserved', () => {
  for (const mutate of [
    s=>s.url='javascript:alert(1)',
    s=>s.comments[1][3]=1,
    s=>s.comments[0][1]='a'.repeat(1201),
    s=>s.inputs=Array(10).fill('入力'),
    s=>s.id='"><script>',
  ]) {
    const bad=structuredClone(story);mutate(bad)
    assert.throws(() => readerSnapshot(bad))
  }
  const storage=memory(),repo=createSavedRepository(() => storage,clock)
  repo.bookmark(wrapped(story))
  const value=JSON.parse(storage.getItem(STORAGE_KEY))
  value.items[0].article.reader_story.comments[0][3]=100
  const raw=JSON.stringify(value);storage.setItem(STORAGE_KEY,raw)
  const blocked=createSavedRepository(() => storage,clock)
  assert.ok(blocked.load().warning)
  blocked.bookmark(wrapped(story))
  assert.equal(storage.getItem(STORAGE_KEY),raw)
})
test('stored snapshots exclude unknown fields and preserve actual reply targets', () => {
  const data=structuredClone(story)
  data.source_text='Do not store source excerpts'
  data.grounding=[{quote:'Do not store quotes'}]
  data.comments[1][3]=0
  const saved=readerSnapshot(data)
  assert.equal(saved.comments[1][3],0)
  assert.equal(saved.source_text,undefined)
  assert.equal(saved.grounding,undefined)
  assert.equal(saved.saved_snapshot,undefined)
})
test('new bookmark path reports quota errors and respects the item limit', () => {
  const quota=createSavedRepository(() => ({getItem:()=>null,setItem:()=>{throw new Error('quota')}}),clock)
  quota.load()
  assert.ok(quota.bookmark(wrapped(story)).warning)
  const storage=memory()
  storage.setItem(STORAGE_KEY,JSON.stringify({version:1,items:Array.from({length:500},(_,i)=>({url:'https://example.com/'+i,article:{url:'https://example.com/'+i,title:'以前の記事',source:'RSS'},labels:['read'],saved_at:clock()}))}))
  const full=createSavedRepository(() => storage,clock);full.load()
  assert.match(full.bookmark(wrapped(story)).warning,/500/)
  assert.equal(full.state().items.length,500)
})
test('saved view renders archived content and does not show the daily-update banner', async () => {
  const html=await renderToString(createSSRApp(FeedView,{stories:[{...readerSnapshot(story),saved_snapshot:true}],publicMode:true,saveEnabled:true,savedView:true,savedUrls:[story.url]}))
  assert.match(html,/保存時の内容/)
  assert.match(html,/保存を解除：/)
  assert.match(html,/このブラウザー内だけ/)
  assert.doesNotMatch(html,/毎日19:17|ニュースの自動更新は準備中/)
})
test('empty saved view offers a way back and old saves retain their original source link', async () => {
  const empty=await renderToString(createSSRApp(FeedView,{stories:[],publicMode:true,saveEnabled:true,savedView:true}))
  assert.match(empty,/保存した記事はまだありません/)
  assert.match(empty,/発見フィードへ/)
  const legacy=await renderToString(createSSRApp(FeedView,{stories:[],publicMode:true,saveEnabled:true,savedView:true,savedUrls:['https://example.com/old'],legacySaved:[{url:'https://example.com/old',article:{title:'以前の記事',source:'RSS'}}]}))
  assert.match(legacy,/以前の画面で保存した記事/)
  assert.match(legacy,/https:\/\/example.com\/old/)
  assert.doesNotMatch(legacy,/保存した記事はまだありません/)
})
