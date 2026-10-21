import { discussionFor } from './discussion.js'
export const feedTabs = [['recommended','おすすめ'],['hot','議論が熱い'],['new','新着'],['saved','保存済み']]
export function commentCount(article) {
  const n = discussionFor(article)?.comment_count
  return Number.isSafeInteger(n) && n >= 0 ? n : null
}
const topics = [
  [/\bpython\b/i,'Python'], [/\bc#\b|c#|\.net\b/i,'C#・.NET'],
  [/\bexcel\b|\bcsv\b|スプレッドシート/i,'Excel・CSV'],
  [/\bgis\b|\bqgis\b|\barcgis\b|地理情報/i,'GIS'],
  [/自動化|業務改善|効率化|\bautomat(?:e|ion|ing)\b|workflow/i,'業務改善'],
  [/\bcopilot\b|\bcodex\b|開発支援|coding agent/i,'開発効率化'],
]
export function interests(article) {
  const text = [article.title,article.summary,article.translation?.title_ja,article.translation?.summary_ja].filter(v=>typeof v==='string').join(' ')
  return topics.filter(([pattern])=>pattern.test(text)).map(([,name])=>name)
}
const published = article => Number.isFinite(Date.parse(article.published_at)) ? Date.parse(article.published_at) : 0
export function recommendationScore(article, now=Date.now()) {
  const time = published(article)
  const age = time && time <= now ? Math.max(0,(now-time)/86400000) : Infinity
  return Math.min(interests(article).length,3)*5 + Math.max(0,7-age) + Math.min(commentCount(article) || 0,100)/20
}
export function recommendationReason(article) {
  const tags = interests(article)
  return tags.length ? `${tags.slice(0,2).join('・')}に関連` : (commentCount(article)>0 ? 'HNでコメントあり' : '公開日時をもとに選定')
}
export function applicationIdea(article) {
  const tags=interests(article)
  if(tags.includes('Python') && tags.includes('Excel・CSV')) return '手元のサンプルCSVで、集計や整形の手作業を置き換えられるか小さく試す。'
  if(tags.includes('GIS') && tags.includes('業務改善')) return 'サンプルの地理データで、繰り返し行う変換・確認作業への応用を検討する。'
  if(tags.includes('C#・.NET') && (tags.includes('開発効率化') || tags.includes('業務改善'))) return '小さなC#の検証用プロジェクトで、開発やレビューの手間が減るか比較する。'
  return null
}
export function selectFeed(articles, {tab='recommended',category='all',discussionsOnly=false,savedKind='all',savedItems=[],now=Date.now()}={}) {
  const current = new Map(articles.map(a=>[a.url,a]))
  const source = tab==='saved' ? savedItems.filter(s=>savedKind==='all'||s.labels.includes(savedKind)).map(s=>current.get(s.url)||{...s.article,saved_snapshot:true}) : [...current.values()]
  return source.filter(a=>(category==='all'||a.category===category)&&(!discussionsOnly||discussionFor(a))&&(tab!=='hot'||commentCount(a)>0))
    .sort((a,b)=> {
      if(tab==='saved') return savedItems.findIndex(s=>s.url===a.url)-savedItems.findIndex(s=>s.url===b.url)
      const primary = tab==='hot' ? commentCount(b)-commentCount(a) : tab==='recommended' ? recommendationScore(b,now)-recommendationScore(a,now) : 0
      return primary || published(b)-published(a) || a.url.localeCompare(b.url)
    })
}
export function japanDay(value) {
  const time = typeof value === 'number' ? value : Date.parse(value)
  return Number.isFinite(time) ? new Date(time+9*3600000).toISOString().slice(0,10) : ''
}
export function highlights(articles, now=Date.now()) {
  const today = articles.filter(a=>published(a)<=now && japanDay(a.published_at)===japanDay(now))
  const source = today.length ? today : articles.filter(a=>published(a)<=now)
  return {today:today.length>0,items:selectFeed(source,{now}).slice(0,3)}
}
