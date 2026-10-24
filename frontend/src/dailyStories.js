const kinds = {
  announcement: ['AIの最新情報', '✨', 'sonnet'],
  research: ['AIの研究', '🔬', 'skills'],
  guide: ['使い方としくみ', '🧭', 'earth'],
  practice: ['試してみた実例', '🛠️', 'earth'],
}
const statuses = new Set(['waiting', 'ready', 'no_new', 'budget_limit', 'generation_paused', 'source_unavailable', 'invalid_outputs', 'rate_limit', 'provider_error'])
const validText = (v, limit) => typeof v === 'string' && v.trim().length > 0 && [...v].length <= limit && !/[<>\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(v)
const validTime = v => typeof v === 'string' && /(?:Z|[+-]\d\d:\d\d)$/.test(v) && Number.isFinite(Date.parse(v))
function safeUrl(value) {
  try {
    const u = new URL(value)
    return u.protocol === 'https:' && ['zenn.dev', 'github.blog', 'aws.amazon.com'].includes(u.hostname) && !u.username && !u.password && !u.search && !u.hash && !u.port
  } catch { return false }
}
function validDay(v) {
  return typeof v === 'string' && /^\d{4}-\d\d-\d\d$/.test(v) && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v
}
export function dailyStories(feed) {
  if (feed?.format !== 1 || !statuses.has(feed.status) || !Array.isArray(feed.entries) || feed.entries.length > 30
      || !['checked_at', 'updated_at'].every(k => feed[k] === null || validTime(feed[k]))
      || (feed.entries.length && !validTime(feed.updated_at))) throw new Error('invalid daily feed')
  const seen = new Set()
  return feed.entries.map(entry => {
    const c = entry.card, meta = kinds[entry.article_kind]
    if (!/^a[a-f0-9]{20}$/.test(entry.id) || !safeUrl(entry.url) || seen.has(entry.id) || seen.has(entry.url)
        || !validText(entry.source, 100) || !validDay(entry.published_on) || !validTime(entry.generated_at)
        || !meta || !c || !Object.entries({title:90,lead:120,changed:220,example:220,caution:220}).every(([k,n]) => validText(c[k], n))
        || !Array.isArray(c.comments) || c.comments.length !== 8) throw new Error('invalid daily card')
    seen.add(entry.id); seen.add(entry.url)
    const comments = c.comments.map((r, i) => {
      if (!validText(r.name, 18) || !validText(r.text, 100)
          || !(r.reply_to === null || Number.isInteger(r.reply_to) && r.reply_to >= 0 && r.reply_to < i)) throw new Error('invalid daily comment')
      return [r.name, r.text, r.reply_to !== null, r.reply_to]
    })
    const d = c.diagram
    if (d !== null && (!d || !['steps', 'combine'].includes(d.layout) || !validText(d.question, 70) || !validText(d.result, 70)
        || !Array.isArray(d.nodes) || d.nodes.length < 2 || d.nodes.length > 4 || !d.nodes.every(n => validText(n, 35)))) throw new Error('invalid daily diagram')
    const [year, month, day] = entry.published_on.split('-').map(Number)
    return {
      id: entry.id, category: meta[0], emoji: meta[1], theme: meta[2],
      source: entry.source, sourceLabel: new URL(entry.url).hostname === 'zenn.dev' ? '著者の記事' : '公式記事',
      url: entry.url, date: `${year}/${month}/${day}`,
      ...Object.fromEntries(['title','lead','changed','example','caution'].map(k => [k, c[k]])),
      inputs: d?.nodes || [], question: d?.question || '', result: d?.result || '', layout: d?.layout,
      diagramNote: 'AIによる模式図です。実際の画面や実証結果ではありません。',
      comments, teaser: comments[0][1],
    }
  })
}

export function displayTime(value) {
  if (!validTime(value)) return '未実行'
  return new Intl.DateTimeFormat('ja-JP', { timeZone:'Asia/Tokyo', year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false }).format(new Date(value))
}
