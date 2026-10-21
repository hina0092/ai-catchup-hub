import {test} from 'node:test'
import assert from 'node:assert/strict'
import {selectFeed,highlights,commentCount,interests,recommendationScore,japanDay,applicationIdea} from '../src/feed.js'
const now=Date.parse('2026-10-21T03:00:00Z')
const article=(url,extras={})=>({url:`https://example.com/${url}`,title:'News',published_at:'2026-10-20T20:00:00Z',category:'ai-tools',...extras})
const hn=n=>({provider:'hacker_news',story_id:1,comment_count:n})
test('recommended matches technical interests, without mutating input',()=>{
  const rows=[article('general'),article('python',{title:'Python CSV 自動化'})]
  assert.deepEqual(interests(rows[1]),['Python','Excel・CSV','業務改善'])
  assert.equal(selectFeed(rows,{now})[0].url,rows[1].url)
  assert.equal(rows[0].url,'https://example.com/general')
})
test('work suggestions require a specific relevant combination',()=>{
  assert.equal(applicationIdea(article('general',{title:'AIの未来'})),null)
  assert.equal(applicationIdea(article('python',{title:'Pythonの新バージョン'})),null)
  assert.match(applicationIdea(article('csv',{title:'PythonでCSVを集計'})),/サンプルCSV/)
})
test('new and hot have separate ordering and unknown counts are not zero',()=>{
  const rows=[article('new',{published_at:'2026-10-21T02:00:00Z'}),article('hot',{discussion:hn(42)}),article('unknown',{discussion:hn(null)}),article('zero',{discussion:hn(0)})]
  assert.equal(selectFeed(rows,{tab:'new'})[0].url,rows[0].url)
  assert.deepEqual(selectFeed(rows,{tab:'hot'}).map(a=>a.url),[rows[1].url])
  assert.equal(commentCount(rows[2]),null)
})
test('filters combine and duplicate URLs are removed',()=>{
  const a=article('one',{category:'techniques',discussion:hn(1)})
  const rows=[a,a,article('two'),article('three',{category:'techniques'})]
  assert.deepEqual(selectFeed(rows,{category:'techniques',discussionsOnly:true}).map(a=>a.url),[a.url])
})
test('saved articles survive feed removal and current data takes precedence',()=>{
  const old=article('old'),fresh=article('old',{title:'Updated'})
  const savedItems=[{url:old.url,article:old,labels:['read']}]
  assert.equal(selectFeed([],{tab:'saved',savedItems})[0].saved_snapshot,true)
  assert.equal(selectFeed([fresh],{tab:'saved',savedItems})[0].title,'Updated')
  assert.equal(selectFeed([],{tab:'saved',savedItems,savedKind:'work'}).length,0)
})
test('highlights use JST day, at most three, no duplicated URLs',()=>{
  assert.equal(japanDay('2026-10-20T15:00:00Z'),'2026-10-21')
  const rows=[0,1,2,3].map(n=>article(n))
  const selected=highlights([...rows,rows[0]],now)
  assert.equal(selected.today,true)
  assert.equal(selected.items.length,3)
})
test('highlight fallback labels old news honestly and excludes future entries',()=>{
  const old=article('old',{published_at:'2026-10-19T01:00:00Z'})
  const future=article('future',{published_at:'2027-01-01T00:00:00Z'})
  const selected=highlights([old,future],now)
  assert.equal(selected.today,false)
  assert.deepEqual(selected.items,[old])
  assert.deepEqual(highlights([],now).items,[])
  assert.ok(Number.isFinite(recommendationScore(article('unknown',{published_at:null}),now)))
})
