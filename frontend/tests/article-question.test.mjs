import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { buildArticleQuestion, questionArticle, questionIntents, copyArticleQuestion } from '../src/articleQuestion.js'
import { trialStories } from '../src/prototype/trialStories.js'
import { readerSnapshot } from '../src/readerSnapshots.js'

const story = trialStories[0]
const server = await createServer({server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'})
after(() => server.close())
const {default:AskAiDialog} = await server.ssrLoadModule('/src/components/AskAiDialog.vue')
const {default:FeedView} = await server.ssrLoadModule('/src/prototype/FeedView.vue')

test('question includes source and card data while distinguishing AI explanation from the original', () => {
  const prompt = buildArticleQuestion(story)
  const data = questionArticle(story)
  assert.equal(data.url,story.url)
  assert.equal(data.title,story.title)
  assert.equal(data.card_explanation.changed,story.changed)
  assert.deepEqual(data.schematic_diagram.nodes,story.inputs)
  assert.match(prompt,/開けない場合は、読んだと装わず/)
  assert.match(prompt,/カードだけで事実を確定せず/)
  assert.match(prompt,/新しい公開日だけを根拠に新機能/)
  assert.match(prompt,/架空コメントはこの相談文に含めていません/)
  assert.ok(!prompt.includes(story.comments[0][1]))
})
test('only explicitly entered question and context are included', () => {
  const input = {intent:'apply',question:'SNS動画で使える？',context:'Pythonを少し使えます。'}
  const prompt = buildArticleQuestion(story,input)
  const json = JSON.parse(prompt.slice(prompt.indexOf('{\n')))
  assert.equal(json.my_question,input.question)
  assert.equal(json.my_context,input.context)
  assert.equal(JSON.parse(buildArticleQuestion(story).split('\n\n').at(-1)).my_context,'未入力')
  assert.equal(questionIntents.length,3)
})
test('saved snapshots and old source-only saves work without inventing missing article contents', () => {
  const old = {url:'https://example.com/old',title:'以前の記事',source:'RSS'}
  const data = questionArticle(old)
  assert.equal(data.card_explanation,undefined)
  assert.equal(data.schematic_diagram,undefined)
  assert.equal(data.published_on,'未確認')
  const saved = {...readerSnapshot(story),saved_snapshot:true}
  assert.match(buildArticleQuestion(saved),/掲載終了後の保存時のカード/)
})
test('blank optional fields are accepted and invalid inputs cannot create a prompt', () => {
  assert.ok(buildArticleQuestion(story,{question:'  ',context:'\n'}))
  for (const bad of [
    {...story,url:'javascript:alert(1)'},
    {...story,url:'https://user:password@example.com/'},
    {...story,title:''},
    {...story,inputs:Array(9).fill('入力')},
  ]) assert.throws(() => buildArticleQuestion(bad))
  assert.throws(() => buildArticleQuestion(story,{intent:'unknown'}))
  assert.throws(() => buildArticleQuestion(story,{question:'あ'.repeat(601)}))
  assert.throws(() => buildArticleQuestion(story,{context:{secret:'unexpected'}}))
})
test('unknown private data and raw extraction are excluded from the copied payload', () => {
  const prompt = buildArticleQuestion({...story,api_key:'PRIVATE_TOKEN',source_text:'RAW_SOURCE_SECRET',grounding:[{quote:'GROUNDING_SECRET'}],personal_profile:'PRIVATE_PROFILE'})
  for (const secret of ['PRIVATE_TOKEN','RAW_SOURCE_SECRET','GROUNDING_SECRET','PRIVATE_PROFILE']) assert.ok(!prompt.includes(secret))
})
test('clipboard success copies the exact generated prompt, failure is reported without a fake success', async () => {
  const prompt = buildArticleQuestion(story)
  let written
  assert.equal(await copyArticleQuestion(prompt,{writeText:async value=>{written=value}}),true)
  assert.equal(written,prompt)
  assert.equal(await copyArticleQuestion(prompt,null),false)
  assert.equal(await copyArticleQuestion(prompt,{writeText:async()=>{throw new Error('denied')}}),false)
  assert.equal(await copyArticleQuestion('',{writeText:async()=>{throw new Error('should not be called')}}),false)
})
test('consultation dialog renders optional inputs and a blank ChatGPT link, with no automatic submission', async () => {
  const html = await renderToString(createSSRApp(AskAiDialog,{story}))
  assert.match(html,/相談文をコピー/)
  assert.match(html,/聞きたいこと/)
  assert.match(html,/自分の前提/)
  assert.match(html,/AIへの自動送信は行いません/)
  assert.match(html,/href="https:\/\/chatgpt.com\/"/)
  assert.doesNotMatch(html,/chatgpt\.com\/\?q=|PRIVATE_PROFILE/)
})
test('article, saved snapshot, legacy save and comments expose the AI-question entry', async () => {
  for (const savedView of [false,true]) {
    const html = await renderToString(createSSRApp(FeedView,{stories:[story],publicMode:true,saveEnabled:true,savedView}))
    assert.match(html,/AIに聞く：/)
  }
  const legacy = await renderToString(createSSRApp(FeedView,{stories:[],publicMode:true,saveEnabled:true,savedView:true,legacySaved:[{url:'https://example.com/old',article:{url:'https://example.com/old',title:'以前の記事',source:'RSS'}}]}))
  assert.match(legacy,/AIに聞く：以前の記事/)
})
