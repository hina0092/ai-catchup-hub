export const STORAGE_KEY = 'ai-catchup-hub.saved.v1'
export const saveKinds = [['read','あとで読む'],['try','試したい'],['work','仕事に使えそう']]
const kinds = new Set(saveKinds.map(([id])=>id))
const MAX_ITEMS = 500
export function safeUrl(value) {
  if(typeof value!=='string') return null
  try {const url=new URL(value);return ['https:','http:'].includes(url.protocol)&&!url.username&&!url.password ? url.href : null} catch{return null}
}
export function snapshot(article) {
  const url=safeUrl(article?.url)
  if(!url || typeof article.title!=='string' || !article.title.trim()) throw new Error('invalid article')
  const result={url,title:article.title.slice(0,500),source:typeof article.source==='string'?article.source.slice(0,160):'情報源不明'}
  for(const key of ['id','category','published_at','collected_at','summary']) if(typeof article[key]==='string') result[key]=article[key].slice(0,500)
  const t=article.translation
  if(t?.language==='ja' && typeof t.title_ja==='string') result.translation={language:'ja',title_ja:t.title_ja.slice(0,500),summary_ja:typeof t.summary_ja==='string'?t.summary_ja.slice(0,500):null}
  const d=article.discussion
  if(d?.provider==='hacker_news' && Number.isSafeInteger(d.story_id) && d.story_id>0) result.discussion={provider:'hacker_news',story_id:d.story_id,comment_count:Number.isSafeInteger(d.comment_count)&&d.comment_count>=0?d.comment_count:null,checked_at:typeof d.checked_at==='string'?d.checked_at.slice(0,80):null}
  return result
}
export function decodeSaved(raw) {
  if(raw===null) return []
  const value=JSON.parse(raw)
  if(value?.version!==1 || !Array.isArray(value.items) || value.items.length>MAX_ITEMS) throw new Error('invalid saved data')
  const urls=new Set()
  return value.items.map(item=>{
    const article=snapshot(item?.article)
    if(item.url!==article.url || urls.has(item.url) || !Array.isArray(item.labels) || !item.labels.length || item.labels.length>3 || item.labels.some(k=>!kinds.has(k)) || typeof item.saved_at!=='string' || !Number.isFinite(Date.parse(item.saved_at))) throw new Error('invalid saved entry')
    urls.add(item.url)
    return {url:item.url,article,labels:[...new Set(item.labels)],saved_at:item.saved_at}
  })
}
export function createSavedRepository(getStorage, now=()=>new Date().toISOString()) {
  let items=[],persistent=true,warning=''
  const state=()=>({items:[...items],warning})
  function load() {
    try {items=decodeSaved(getStorage().getItem(STORAGE_KEY));persistent=true;warning=''}
    catch {persistent=false;warning='保存領域を読み込めません。この画面内だけで保存します。既存の保存データは上書きしません。'}
    return state()
  }
  function toggle(article,kind) {
    if(!kinds.has(kind)) throw new Error('invalid save kind')
    const clean=snapshot(article)
    const found=items.find(s=>s.url===clean.url)
    if(!found && items.length>=MAX_ITEMS) {warning='保存は500件までです。不要な保存を解除してください。';return state()}
    const labels=found?.labels.includes(kind)?found.labels.filter(k=>k!==kind):[...(found?.labels||[]),kind]
    items=items.filter(s=>s.url!==clean.url)
    if(labels.length) items.unshift({url:clean.url,article:clean,labels,saved_at:now()})
    if(persistent) {
      try {getStorage().setItem(STORAGE_KEY,JSON.stringify({version:1,items}));warning=''}
      catch {persistent=false;warning='端末に保存できません。この画面内では保持しますが、再読み込みすると今回の変更が失われます。'}
    }
    return state()
  }
  return {load,toggle,state}
}
