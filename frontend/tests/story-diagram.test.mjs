import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { readerSnapshot } from '../src/readerSnapshots.js'
import { trialStories } from '../src/prototype/trialStories.js'

const server = await createServer({ server:{ middlewareMode:true, hmr:false, ws:false }, appType:'custom' })
after(() => server.close())
const { default: StoryDiagram } = await server.ssrLoadModule('/src/components/StoryDiagram.vue')
const render = story => renderToString(createSSRApp(StoryDiagram, { story }))

test('steps preserve their order and separate the output from the use case', async () => {
  const story = trialStories.find(s => s.id === 'polly')
  const html = await render(story)
  assert.match(html, /処理の流れ/)
  assert.match(html, /<ol[^>]+aria-label="処理の順番"/)
  assert.ok(html.indexOf('利用者：') < html.indexOf('Polly：'))
  assert.match(html, /読み上げ音声が得られる/)
  assert.doesNotMatch(html, /動画や案内|ひと目でわかる/)
})

test('comparison uses two labeled targets without causal arrows and survives saving', async () => {
  const story = trialStories.find(s => s.id === 'folders')
  const html = await render(story)
  assert.match(html, /同じ観点で比較/)
  assert.match(html, /変更前：/)
  assert.match(html, /変更後：/)
  assert.doesNotMatch(html, /diagram-join|diagram-steps|↓/)
  assert.equal(readerSnapshot(story).layout, 'compare')
  assert.throws(() => readerSnapshot({ ...story, inputs:[...story.inputs, '追加'] }))
})

test('combine labels the relationship and a null diagram stays hidden', async () => {
  const story = { ...trialStories[0], layout:'combine', inputs:['材料A', '材料B'] }
  const html = await render(story)
  assert.match(html, /組み合わせる材料/)
  assert.match(html, /組み合わせる/)
  assert.doesNotMatch(html, /diagram-steps/)
  assert.doesNotMatch(await render({ ...story, inputs:[] }), /<figure/)
})
