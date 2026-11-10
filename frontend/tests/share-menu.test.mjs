import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { JSDOM } from 'jsdom'
import { parse, compileScript } from '@vue/compiler-sfc'

// Install the DOM before Vue initializes runtime-dom. Compile the actual client
// template; SSR cannot exercise focus, DOM removal, or click delivery.
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'https://example.com/' })
for (const key of ['window', 'document', 'Element', 'HTMLElement', 'SVGElement', 'Node']) globalThis[key] = dom.window[key]
globalThis.IntersectionObserver = class { observe() {} disconnect() {} }
const { createApp, nextTick } = await import('vue')
const { trialStories } = await import('../src/prototype/trialStories.js')
const file = new URL('../src/prototype/FeedView.vue', import.meta.url)
const { descriptor } = parse(await readFile(file, 'utf8'))
let code = compileScript(descriptor, { id: 'share-menu-test', inlineTemplate: true }).content
code = code.replace(/import (\w+) from '([^']+\.vue)'/g, 'const $1 = { render: () => null }')
code = code.replace(/from ['"]([^'"]+)['"]/g, (_, path) => `from ${JSON.stringify(path.startsWith('.') ? new URL(path, file).href : import.meta.resolve(path))}`)
code = code.replaceAll('import.meta.env.BASE_URL', JSON.stringify('/'))
const { default: FeedView } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)

async function mount(t, { clipboard = async () => {}, share = async () => {}, story = trialStories[0] } = {}) {
  Object.defineProperty(window.navigator, 'clipboard', { configurable: true, value: { writeText: clipboard } })
  Object.defineProperty(window.navigator, 'share', { configurable: true, value: share })
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(FeedView, { stories: [story], shareEnabled: true })
  app.mount(root)
  t.after(() => { app.unmount(); root.remove() })
  await nextTick()
  const trigger = root.querySelector('.share-action > button')
  const open = async () => { trigger.click(); await nextTick() }
  const toast = () => root.querySelector('[role="status"]').textContent
  return { root, trigger, open, toast }
}
async function settle() { await new Promise(resolve => setImmediate(resolve)); await nextTick() }

for (const action of ['copy', 'share']) {
  test(`${action}: null-relatedTarget focusout before tap keeps the action mounted and delivers click`, async t => {
    const calls = []
    const view = await mount(t, { clipboard: async data => calls.push(data), share: async data => calls.push(data) })
    await view.open()
    const buttons = view.root.querySelectorAll('.share-options button')
    assert.equal(document.activeElement, buttons[0])
    const target = buttons[action === 'copy' ? 0 : 1]
    target.dispatchEvent(new window.Event('pointerdown', { bubbles: true }))
    buttons[0].dispatchEvent(new window.FocusEvent('focusout', { bubbles: true, relatedTarget: null }))
    // iOS can flush Vue's v-if update before the subsequent click.
    await nextTick()
    assert.equal(target.isConnected, true)
    target.click()
    await settle()
    assert.equal(calls.length, 1)
    assert.match(view.toast(), action === 'copy' ? /記事リンクをコピーしました/ : /共有しました/)
    assert.equal(view.root.querySelector('.share-options'), null)
  })
}

test('focus traversal does not dismiss the menu; Escape restores focus and outside pointerdown closes', async t => {
  const view = await mount(t)
  await view.open()
  const [copy, share] = view.root.querySelectorAll('.share-options button')
  share.focus()
  await nextTick()
  assert.equal(document.activeElement, share)
  assert.equal(copy.isConnected, true)
  view.root.querySelector('.source-card').focus()
  await nextTick()
  assert.equal(copy.isConnected, true)
  share.focus()
  share.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await nextTick()
  assert.equal(view.trigger.getAttribute('aria-expanded'), 'false')
  assert.equal(document.activeElement, view.trigger)
  await view.open()
  document.body.dispatchEvent(new window.Event('pointerdown', { bubbles: true }))
  await nextTick()
  assert.equal(view.root.querySelector('.share-options'), null)
})

for (const action of ['copy', 'share']) {
  test(`${action}: API rejection and invalid share data both show failure toasts`, async t => {
    const view = await mount(t, { clipboard: async () => { throw Error('denied') }, share: async () => { throw Error('denied') } })
    await view.open()
    view.root.querySelectorAll('.share-options button')[action === 'copy' ? 0 : 1].click()
    await settle()
    assert.match(view.toast(), /できませんでした/)
    const invalid = await mount(t, { story: { ...trialStories[0], url: 'javascript:invalid' } })
    await invalid.open()
    invalid.root.querySelectorAll('.share-options button')[action === 'copy' ? 0 : 1].click()
    await settle()
    assert.match(invalid.toast(), /できませんでした/)
  })
}

test('native share cancellation and clipboard fallback show their outcomes', async t => {
  const cancelled = await mount(t, { share: async () => { throw new window.DOMException('cancelled', 'AbortError') } })
  await cancelled.open()
  cancelled.root.querySelectorAll('.share-options button')[1].click()
  await settle()
  assert.match(cancelled.toast(), /キャンセルしました/)
  const calls = []
  const fallback = await mount(t, { share: undefined, clipboard: async text => calls.push(text) })
  // Override the helper default to model a browser without Web Share.
  Object.defineProperty(window.navigator, 'share', { configurable: true, value: undefined })
  await fallback.open()
  fallback.root.querySelectorAll('.share-options button')[1].click()
  await settle()
  assert.equal(calls.length, 1)
  assert.match(fallback.toast(), /共有文をコピーしました/)
})
