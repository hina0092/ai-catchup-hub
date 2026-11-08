import { articleLink } from './feedRoute.js'
import { safeUrl } from './savedArticles.js'
export function buildShareData(story, base) {
  const original = safeUrl(story.url)
  if (!original || typeof story.title !== 'string') throw new Error('invalid share article')
  const title = story.title.replace(/\s+/g, ' ').trim()
  const url = story.saved_snapshot || !story.id ? original : articleLink(base, story.id)
  return { title, text: `${title}\nTechmin Feed${story.saved_snapshot ? 'で保存した記事' : ''}\n元記事: ${original}`, url }
}
export async function shareArticle(story, base, navigator) {
  const data = buildShareData(story, base)
  if (typeof navigator.share === 'function') {
    try { await navigator.share(data); return 'shared' }
    catch (error) { return error?.name === 'AbortError' ? 'cancelled' : 'failed' }
  }
  return await copyText(`${data.text}\n${data.url}`, navigator.clipboard) ? 'copied' : 'failed'
}
export async function copyText(text, clipboard) {
  try {
    if (typeof clipboard?.writeText !== 'function') return false
    await clipboard.writeText(text)
    return true
  } catch { return false }
}
