<script setup>
import { computed, ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { buildArticleQuestion, questionIntents, copyArticleQuestion } from '../articleQuestion.js'

const props = defineProps({
  story:{type:Object,required:true},
  context:{type:String,default:''},
  returnFocus:{default:null},
})
const emit = defineEmits(['close','update:context'])
const dialog = ref(null), heading = ref(null), fallback = ref(null)
const intent = ref('explain'), question = ref(''), copied = ref(false), failed = ref(false), busy = ref(false)
const prompt = computed(() => buildArticleQuestion(props.story,{intent:intent.value,question:question.value,context:props.context}))
let closed = false, alive = true
watch([intent,question,() => props.context],() => { copied.value = false; failed.value = false })
function close() { dialog.value?.close() }
function afterClose() {
  if (closed) return
  closed = true
  const another = document.querySelector('dialog[open]')
  document.body.style.overflow = another ? 'hidden' : ''
  if (!another && props.returnFocus?.isConnected) props.returnFocus.focus()
  emit('close')
}
async function copy() {
  if (busy.value) return
  const value = prompt.value
  busy.value = true
  let clipboard
  try { clipboard = navigator.clipboard } catch { clipboard = null }
  const success = await copyArticleQuestion(value,clipboard)
  if (!alive) return
  busy.value = false
  copied.value = success && prompt.value === value
  failed.value = !success
  if (!success) {
    await nextTick()
    fallback.value?.focus()
    fallback.value?.select()
  }
}
onMounted(() => {
  dialog.value.showModal()
  document.body.style.overflow = 'hidden'
  heading.value.focus()
})
onUnmounted(() => {
  alive = false
  dialog.value?.close()
  document.body.style.overflow = document.querySelector('dialog[open]') ? 'hidden' : ''
})
</script>
<template>
  <dialog ref="dialog" class="comments-dialog ask-dialog" aria-labelledby="ask-heading" aria-describedby="ask-intro" @close="afterClose" @click="event => { if (event.target === dialog) close() }">
    <div class="sheet-header">
      <div><p>TAKE YOUR CURIOSITY FURTHER</p><h2 id="ask-heading" ref="heading" tabindex="-1">💬 AIに聞いてみる</h2></div>
      <button class="close" aria-label="AI相談を閉じる" @click="close">✕</button>
    </div>
    <div class="sheet-scroll ask-scroll">
      <p class="ask-article">{{ story.title.replaceAll('\n','') }}</p>
      <p id="ask-intro" class="ask-intro">相談文をコピーして、いつものAIに貼り付けます。回答はそのAIで読めます。</p>
      <div class="ask-intents" role="group" aria-label="聞きたいことの種類">
        <button v-for="item in questionIntents" :key="item.id" :aria-pressed="intent === item.id" @click="intent = item.id">{{ item.label }}</button>
      </div>
      <label class="ask-field"><span>聞きたいこと <small>任意</small></span>
        <textarea v-model="question" maxlength="600" rows="2" placeholder="例：今までの仕組みと何が違うの？"></textarea>
      </label>
      <label class="ask-field"><span>自分の前提 <small>任意</small></span>
        <textarea :value="context" @input="emit('update:context', $event.target.value)" maxlength="600" rows="2" placeholder="例：Pythonは少し使える。SNS動画で試したい。"></textarea>
      </label>
      <p class="ask-note">記事情報と、入力した質問・前提がコピーされます。架空コメントは含めません。ここではAIへの自動送信は行いません。</p>
      <details v-if="!failed" class="ask-preview">
        <summary>コピーする相談文を確認</summary>
        <textarea :value="prompt" readonly rows="8" aria-label="コピーする相談文"></textarea>
      </details>
      <div v-if="failed" class="ask-fallback">
        <p role="alert">自動コピーできませんでした。下の文章を選択して、長押しなどでコピーしてください。</p>
        <textarea ref="fallback" :value="prompt" readonly rows="8" aria-label="手動コピー用の相談文"></textarea>
      </div>
    </div>
    <div class="sheet-footer ask-footer">
      <button class="copy-question" :disabled="busy" @click="copy">{{ busy ? 'コピー中…' : copied ? '✓ 相談文をコピーしました' : '📋 相談文をコピー' }}</button>
      <p v-if="copied" class="ask-success" role="status">いつものAIに貼り付けて、送信してください。</p>
      <p v-else class="ask-copy-help">① コピー → ② いつものAIに貼り付けて送信</p>
      <a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer" class="open-ai">ChatGPTを開く ↗</a>
      <span class="ask-other">ほかのAIにも貼り付けて使えます。</span>
    </div>
  </dialog>
</template>
<style scoped>
.ask-scroll{padding-top:14px}.ask-article{font-size:13px;font-weight:700;margin:0 0 8px;color:#4c6550}.ask-intro{font-size:12px;line-height:1.8;color:#6c7868;margin:0 0 14px}.ask-intents{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}.ask-intents button{font-size:11px;border:1px solid #d6dfcf;border-radius:24px;background:#fafbf6;color:#63745c;padding:8px 11px}.ask-intents button[aria-pressed=true]{background:#e3ecdc;color:#304b35;border-color:#a2b795;font-weight:700}
.ask-field{display:grid;gap:7px;margin:0 0 14px}.ask-field>span{font-size:12px;font-weight:700}.ask-field small{font-size:10px;font-weight:400;color:#8b927f;margin-left:5px}.ask-dialog textarea{width:100%;max-width:100%;box-sizing:border-box;border:1px solid #d9dfd1;border-radius:10px;padding:10px 12px;font:inherit;font-size:12px;line-height:1.8;color:#344d3a;background:#fffefa;resize:vertical;min-height:72px}.ask-dialog textarea:focus-visible{outline:2px solid #8fa77e;outline-offset:2px}.ask-note{font-size:10px;color:#808777;line-height:1.8;margin:4px 0 12px}
.ask-preview summary{font-size:11px;color:#6a7a68;cursor:pointer;padding:10px 0}.ask-preview textarea,.ask-fallback textarea{font-size:11px;background:#f7f7f0}.ask-fallback p{font-size:11px;line-height:1.8;color:#87642e;background:#fff3df;padding:10px;border-radius:9px}.ask-footer{display:grid;justify-items:center;gap:5px;padding:13px 18px}.copy-question{width:100%;border-radius:12px;padding:12px;background:#38583f;color:#fffef9;font-size:13px;font-weight:700}.copy-question:disabled{opacity:.65;cursor:wait}.ask-copy-help,.ask-success{font-size:10px;margin:3px 0;color:#75816d;line-height:1.7}.ask-success{color:#3e6846}.open-ai{font-size:12px;min-height:36px;display:flex;align-items:center;color:#466a4a}.ask-other{font-size:9px;color:#89917d}
@media(max-width:360px){.ask-intents button{font-size:10px;padding:7px 9px}.ask-footer{padding:10px 14px}}
</style>
