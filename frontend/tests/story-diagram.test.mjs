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
  assert.doesNotMatch(html, /📝|🎙/)
  assert.match(story.inputs[0], /📝/)
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

test('only short sequences can use a horizontal layout and all steps keep their order', async () => {
  for (const length of [2, 3, 4]) {
    const story = { ...trialStories[0], layout: 'steps', inputs: Array.from({ length }, (_, i) => `手順${i + 1}`) }
    const html = await render(story)
    assert.equal(html.includes('short-steps'), length <= 3)
    assert.equal((html.match(/<li\b/g) || []).length, length)
    for (let i = 1; i < length; i++) assert.ok(html.indexOf(`手順${i}`) < html.indexOf(`手順${i + 1}`))
  }
})

test('combine labels the relationship and a null diagram stays hidden', async () => {
  const story = { ...trialStories[0], layout:'combine', inputs:['材料A', '材料B'] }
  const html = await render(story)
  assert.match(html, /組み合わせる材料/)
  assert.match(html, /組み合わせる/)
  assert.doesNotMatch(html, /diagram-steps/)
  assert.doesNotMatch(await render({ ...story, inputs:[] }), /<figure/)
})
