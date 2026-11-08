import { safeUrl } from './savedArticles.js'
export const READ_STORAGE_KEY = 'ai-catchup-hub.read.v1'
export const MAX_READ_ITEMS = 1000
export function decodeReadMarks(raw) {
  if (raw === null) return []
  const data = JSON.parse(raw)
  if (data?.version !== 1 || !Array.isArray(data.items) || data.items.length > MAX_READ_ITEMS) throw new Error('invalid read marks')
  const seen = new Set()
  return data.items.map(item => {
    const url = safeUrl(item?.url)
    if (!url || url !== item.url || seen.has(url) || typeof item.read_at !== 'string' || !Number.isFinite(Date.parse(item.read_at))) throw new Error('invalid read mark')
    seen.add(url)
    return { url, read_at: item.read_at }
  })
}
export function createReadRepository(getStorage, now = () => new Date().toISOString()) {
  let items = [], persistent = true, warning = ''
  const state = () => ({ items: items.map(item => ({ ...item })), warning })
  function load() {
    try { items = decodeReadMarks(getStorage().getItem(READ_STORAGE_KEY)); persistent = true; warning = '' }
    catch { persistent = false; warning = '読了の記録を読み込めません。この画面内だけで保持し、既存データは上書きしません。' }
    return state()
  }
  function setRead(value, read) {
    const url = safeUrl(value)
    if (!url) throw new Error('invalid read URL')
    items = items.filter(item => item.url !== url)
    if (read) items.push({ url, read_at: now() })
    items.sort((a, b) => Date.parse(b.read_at) - Date.parse(a.read_at))
    items = items.slice(0, MAX_READ_ITEMS)
    if (persistent) {
      try { getStorage().setItem(READ_STORAGE_KEY, JSON.stringify({ version: 1, items })); warning = '' }
      catch { persistent = false; warning = '読了を端末に記録できません。今回の変更は再読み込みすると失われます。' }
    }
    return state()
  }
  return { load, setRead, state }
}
