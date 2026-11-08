const validId = id => typeof id === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(id)
export function parseFeedRoute(hash) {
  if (hash === '#saved') return { view: 'saved', id: null }
  if (!hash || hash === '#feed') return { view: 'feed', id: null }
  if (hash.startsWith('#card-')) {
    const id = hash.slice(6)
    return validId(id) ? { view: 'feed', id } : { view: 'feed', id: null, invalid: true }
  }
  return null // Native skip links do not change the selected view.
}
export function resolveCard(id, current, saved) {
  const story = current.find(story => story.id === id)
  if (story) return { story, view: 'feed' }
  const archived = saved.find(story => story.id === id)
  return archived ? { story: archived, view: 'saved' } : null
}
export function articleLink(base, id) {
  if (!validId(id)) throw new Error('invalid card ID')
  const url = new URL(base)
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('invalid site URL')
  url.search = ''
  url.hash = `card-${id}`
  return url.href
}
