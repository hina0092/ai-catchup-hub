import {test} from 'node:test'
import assert from 'node:assert/strict'
import {createSavedRepository,decodeSaved,STORAGE_KEY,snapshot} from '../src/savedArticles.js'
const article={url:'https://example.com/1',title:'保存する記事',source:'Fixture',discussion_analysis:{large:'not stored'}}
const clock=()=> '2026-10-21T00:00:00Z'
function memory(){const data=new Map();return {getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)}}
test('multiple labels persist across repository reload and final removal deletes entry',()=>{
  const storage=memory(),repo=createSavedRepository(()=>storage,clock)
  repo.load();repo.toggle(article,'read');repo.toggle(article,'work')
  const reload=createSavedRepository(()=>storage,clock)
  assert.deepEqual(reload.load().items[0].labels,['read','work'])
  reload.toggle(article,'read')
  assert.deepEqual(reload.state().items[0].labels,['work'])
  assert.equal(reload.toggle(article,'work').items.length,0)
  assert.equal(decodeSaved(storage.getItem(STORAGE_KEY)).length,0)
})
test('corrupt or unsupported storage is preserved while in-memory saving works',()=>{
  for(const raw of ['broken','{"version":2,"items":[]}','{"version":1,"items":[null]}']) {
    const storage=memory();storage.setItem(STORAGE_KEY,raw)
    const repo=createSavedRepository(()=>storage,clock)
    assert.ok(repo.load().warning)
    assert.equal(repo.toggle(article,'try').items.length,1)
    assert.equal(storage.getItem(STORAGE_KEY),raw)
  }
})
test('unavailable storage and quota failure keep UI functional with warning',()=>{
  const blocked=createSavedRepository(()=>{throw new Error('blocked')},clock)
  blocked.load()
  assert.equal(blocked.toggle(article,'read').items.length,1)
  assert.ok(blocked.state().warning)
  const quota=createSavedRepository(()=>({getItem:()=>null,setItem:()=>{throw new Error('quota')}}),clock)
  quota.load()
  assert.ok(quota.toggle(article,'try').warning)
  assert.equal(quota.state().items.length,1)
})
test('unsafe links and invalid labels are rejected; snapshots are bounded',()=>{
  assert.throws(()=>snapshot({...article,url:'javascript:alert(1)'}))
  assert.throws(()=>snapshot({...article,url:'https://user:password@example.com/'}))
  assert.equal(snapshot({...article,title:'a'.repeat(1000)}).title.length,500)
  assert.equal(snapshot(article).discussion_analysis,undefined)
  const repo=createSavedRepository(memory,clock)
  assert.throws(()=>repo.toggle(article,'arbitrary'))
})
test('external storage changes can be reloaded',()=>{
  const storage=memory(),a=createSavedRepository(()=>storage,clock),b=createSavedRepository(()=>storage,clock)
  a.load();b.load();a.toggle(article,'read')
  assert.equal(b.load().items.length,1)
})
test('storage refuses more than 500 items without silent eviction',()=>{
  const storage=memory()
  storage.setItem(STORAGE_KEY,JSON.stringify({version:1,items:Array.from({length:500},(_,n)=>({url:'https://example.com/'+n,article:{...article,url:'https://example.com/'+n},labels:['read'],saved_at:clock()}))}))
  const repo=createSavedRepository(()=>storage,clock);repo.load()
  const state=repo.toggle({...article,url:'https://example.com/new'},'read')
  assert.equal(state.items.length,500)
  assert.match(state.warning,/500/)
})
