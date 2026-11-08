import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseFeedRoute, resolveCard, articleLink } from '../src/feedRoute.js'
import { buildShareData, shareArticle } from '../src/shareText.js'
const story = { id: 'polly', title: '記事\nタイトル', url: 'https://example.com/original' }
const base = 'https://example.org/ai-catchup-hub/?private=value#saved'
test('routes accept editorial and generated IDs while skip links retain the view', () => {
  assert.deepEqual(parseFeedRoute('#card-polly'), { view: 'feed', id: 'polly' })
  assert.equal(parseFeedRoute('#card-a01234567890123456789').id, 'a01234567890123456789')
  assert.equal(parseFeedRoute('#card-<script>').invalid, true)
  assert.equal(parseFeedRoute('#story-polly'), null)
  assert.equal(parseFeedRoute('#saved').view, 'saved')
  assert.equal(articleLink(base, story.id), 'https://example.org/ai-catchup-hub/#card-polly')
  assert.equal(resolveCard('missing', [story], []), null)
  assert.equal(resolveCard('polly', [], [story]).view, 'saved')
  assert.equal(resolveCard('polly', [story], [story]).view, 'feed')
})
test('shared text excludes private fields and archived links lead to the original', () => {
  const data = buildShareData({ ...story, context: 'secret', comments: ['secret'] }, base)
  assert.equal(data.title, '記事 タイトル')
  assert.equal(data.url, 'https://example.org/ai-catchup-hub/#card-polly')
  assert.ok(!JSON.stringify(data).includes('secret'))
  assert.equal(buildShareData({ ...story, saved_snapshot: true }, base).url, story.url)
})
test('share cancellation never copies and unsupported sharing uses the clipboard', async () => {
  let copied = ''
  const clipboard = { writeText: async value => { copied = value } }
  assert.equal(await shareArticle(story, base, { share: async () => { throw { name: 'AbortError' } }, clipboard }), 'cancelled')
  assert.equal(copied, '')
  assert.equal(await shareArticle(story, base, { clipboard }), 'copied')
  assert.match(copied, /#card-polly/)
  assert.equal(await shareArticle(story, base, {}), 'failed')
  assert.equal(await shareArticle(story, base, { share: async () => { throw Error('denied') }, clipboard }), 'failed')
})
