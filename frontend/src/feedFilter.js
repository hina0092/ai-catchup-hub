export const emptyFilters = () => ({ query: '', source: '', category: '', unreadOnly: false })
const normalize = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase('ja').replace(/\s+/g, ' ').trim()
export function filterStories(stories, { query = '', source = '', category = '', unreadOnly = false } = {}, readUrls = new Set()) {
  const words = normalize(query).split(' ').filter(Boolean)
  return stories.filter(story => {
    const text = normalize(['title', 'lead', 'changed', 'example', 'caution', 'source', 'category'].map(key => story[key]).join(' '))
    return (!source || story.source === source) && (!category || story.category === category)
      && (!unreadOnly || !readUrls.has(story.url)) && words.every(word => text.includes(word))
  })
}
export function filterOptions(stories) {
  const values = key => [...new Set(stories.map(story => story[key]).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ja'))
  return { sources: values('source'), categories: values('category') }
}
