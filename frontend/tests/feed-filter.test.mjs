import { test } from 'node:test'
import assert from 'node:assert/strict'
import { filterStories, filterOptions } from '../src/feedFilter.js'
const stories = [
  { url: 'https://example.com/1', title: 'ＡＩ\nガイド', caution: '課金条件を確認', source: '公式', category: 'ガイド', comments: [['人', '秘密']] },
  { url: 'https://example.com/2', title: '以前の保存', source: '個人' },
]
test('search normalizes width, case and whitespace and searches explanations with AND', () => {
  assert.deepEqual(filterStories(stories, { query: 'ai　課金' }), [stories[0]])
  assert.equal(filterStories(stories, { query: '秘密' }).length, 0)
  assert.equal(filterStories(stories, { query: 'AI 存在しない' }).length, 0)
  assert.deepEqual(filterStories(stories, { source: '個人', query: '以前' }), [stories[1]])
  assert.equal(filterStories(stories, { source: '個人', category: 'ガイド' }).length, 0)
})
test('options come from the original list and legacy saves need no explanation fields', () => {
  assert.deepEqual(filterOptions(stories), { sources: ['公式', '個人'].sort((a,b) => a.localeCompare(b,'ja')), categories: ['ガイド'] })
  assert.equal(filterStories(stories, { unreadOnly: true }, new Set([stories[0].url])).length, 1)
})
