export const categories = {
  support:'期待・賛成意見', concern:'懸念・反対意見', disagreement:'意見が割れているポイント',
  insight:'深い考察・意外な視点', experience:'実際の使用経験',
}
export const validId = id => Number.isSafeInteger(id) && id > 0
export const hnUrl = id => validId(id) ? `https://news.ycombinator.com/item?id=${id}` : null
export const discussionFor = article => article?.discussion?.provider === 'hacker_news' && validId(article.discussion.story_id) ? article.discussion : null
export const discussionHash = article => `#discussion=${encodeURIComponent(article.url)}`
export function routeFromHash(hash) {
  if (!hash.startsWith('#discussion=')) return ''
  try { return decodeURIComponent(hash.slice(12)) || '__missing__' } catch { return '__missing__' }
}
export function sectionsFor(article) {
  const discussion = discussionFor(article)
  const analysis = article?.discussion_analysis
  if (!discussion || analysis?.story_id !== discussion.story_id || !Array.isArray(analysis.sections) ||
      !Array.isArray(analysis.evidence_comments)) return []
  const known = new Set(analysis.evidence_comments.filter(c => validId(c?.id)).map(c => c.id))
  return analysis.sections.filter(s => s && Object.hasOwn(categories, s.kind) && Array.isArray(s.points))
    .map(s => ({kind:s.kind, points:s.points.filter(p => typeof p?.text_ja === 'string' && p.text_ja.trim() &&
      Array.isArray(p.evidence) && p.evidence.length > 0 && p.evidence.every(e => validId(e?.comment_id) && known.has(e.comment_id) && typeof e.quote === 'string' && e.quote.trim()) &&
      (s.kind !== 'disagreement' || new Set(p.evidence.map(e => e.comment_id)).size >= 2))}))
    .filter(s => s.points.length > 0)
}
