import {test,after} from 'node:test'
import assert from 'node:assert/strict'
import {createServer} from 'vite'
import {createSSRApp} from 'vue'
import {renderToString} from 'vue/server-renderer'
import {enrichment} from '../src/enrichment.js'
import {snapshot,decodeSaved,STORAGE_KEY} from '../src/savedArticles.js'
const server=await createServer({server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'})
after(()=>server.close())
const {default:ArticleText}=await server.ssrLoadModule('/src/components/ArticleText.vue')
const row={title:'Original English title',url:'https://example.com/article',source:'Fixture',title_ja:'日本語の見出し',summary_ja:'記事に書かれた内容を日本語で説明します。'.repeat(9),key_points:['特徴を根拠に沿って説明します。','効果について入力の範囲で説明します。','注意点について原文を確認します。'].map(s=>s.repeat(3)),work_idea:'直接的な業務活用例は未確認',ai_status:'completed',ai_model:'gemini-3.5-flash-lite',ai_version:1,source_basis:'article',ai_generated_at:'2026-10-22T00:00:00+09:00'}
test('Japanese summary, collapsible points, proposal label and original title',async()=>{
  assert.ok(enrichment(row))
  const html=await renderToString(createSSRApp(ArticleText,{article:row}))
  for(const text of ['日本語の見出し','Original English title','詳しく見る','重要ポイント','仕事での活用アイデア','AIによる提案','取得できた本文']) assert.ok(html.includes(text),text)
  assert.match(html,/<details class="ai-details"[^>]*>/)
})
test('invalid AI data falls back and Japanese original is preserved',async()=>{
  assert.equal(enrichment({...row,key_points:['invalid']}),null)
  assert.equal(enrichment({...row,title:'日本語の原題'}).title_ja,'日本語の原題')
  const html=await renderToString(createSSRApp(ArticleText,{article:{...row,key_points:[]}}))
  assert.ok(html.includes('Original English title')); assert.ok(!html.includes('仕事での活用アイデア'))
})
test('saved snapshots retain validated enrichment and legacy storage stays compatible',()=>{
  const saved=snapshot(row)
  const decoded=decodeSaved(JSON.stringify({version:1,items:[{url:row.url,article:saved,labels:['read'],saved_at:'2026-10-22T00:00:00Z'}]}))
  assert.deepEqual(decoded[0].article.key_points,row.key_points)
  assert.equal(decoded[0].article.work_idea,row.work_idea)
  assert.equal(STORAGE_KEY,'ai-catchup-hub.saved.v1')
  assert.equal(snapshot({title:'legacy',url:row.url}).ai_status,undefined)
})
