// Keep only the fields the illustrated reader displays; never store source excerpts.
const text = (v, n) => typeof v === 'string' && v.trim().length > 0 && [...v].length <= n
const optional = (v, n) => v === undefined || v === '' ? '' : text(v, n) ? v : invalid()
const invalid = () => { throw new Error('invalid reader snapshot') }
export function readerSnapshot(story) {
  if (!story || typeof story !== 'object') return invalid()
  let url
  try {
    url = new URL(story.url)
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return invalid()
  } catch { return invalid() }
  const limits = { id:80, title:500, category:100, source:160, date:32, lead:1200, changed:2400, example:2400, caution:2400 }
  if (!Object.entries(limits).every(([k,n]) => text(story[k], n))
      || !/^[a-zA-Z0-9_-]+$/.test(story.id)
      || !Array.isArray(story.inputs) || story.inputs.length > 4 || !story.inputs.every(n => text(n, 200))
      || !Array.isArray(story.comments) || story.comments.length < 2 || story.comments.length > 20) return invalid()
  const question = optional(story.question, 300), result = optional(story.result, 300)
  if (story.inputs.length && (!question || !result || !['steps','combine','compare',undefined].includes(story.layout)
      || (story.layout === 'compare' && story.inputs.length !== 2))) return invalid()
  const comments = story.comments.map((row, index) => {
    if (!Array.isArray(row) || !text(row[0], 80) || !text(row[1], 1200)
        || ![true,false,0,1].includes(row[2])
        || !(row[3] == null || Number.isInteger(row[3]) && row[3] >= 0 && row[3] < index)) return invalid()
    return [row[0], row[1], Boolean(row[2]) || row[3] != null, row[3] ?? null]
  })
  return {
    ...Object.fromEntries(Object.keys(limits).map(k => [k,story[k]])),
    url:url.href, emoji:optional(story.emoji, 16) || '📰',
    theme:['earth','skills','sonnet'].includes(story.theme) ? story.theme : 'earth',
    sourceLabel:optional(story.sourceLabel, 80) || '元記事',
    inputs:[...story.inputs], question, result, layout:story.layout || 'combine',
    diagramNote:optional(story.diagramNote, 1200), reviewNote:optional(story.reviewNote, 1200),
    teaser:comments[0][1], comments,
  }
}

export function savedReaderStories(items, currentStories) {
  const current = new Map(currentStories.map(s => [new URL(s.url).href,s]))
  return items.filter(item => item.article.reader_story).map(item => {
    const latest = current.get(item.url)
    return latest || { ...readerSnapshot(item.article.reader_story), saved_snapshot:true }
  })
}
