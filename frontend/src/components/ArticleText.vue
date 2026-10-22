<script setup>
import { computed } from 'vue'
import { enrichment } from '../enrichment.js'
const props = defineProps({ article: {type:Object, required:true} })
const ai = computed(() => enrichment(props.article))
const translated = computed(() => {
  const t = props.article.translation
  return t && t.language === 'ja' && typeof t.title_ja === 'string' && t.title_ja.trim() ? t : null
})
const summary = computed(() => translated.value && typeof translated.value.summary_ja === 'string' ? translated.value.summary_ja : props.article.summary)
</script>
<template>
  <h3><a :href="article.url" target="_blank" rel="noopener noreferrer">{{ ai?.title_ja || translated?.title_ja || article.title }}<span class="sr-only">（新しいタブで開く）</span></a></h3>
  <p v-if="ai" class="translation-note">AI生成 · {{ ai.source_basis==='article' ? '取得できた本文の範囲を要約' : 'RSS情報のみを要約' }} · 正確な内容は元記事で確認</p>
  <p v-else-if="translated" class="translation-note">AI翻訳<span v-if="translated.summary_ja">・RSS説明文のAI要約</span></p>
  <details v-if="(ai && ai.title_ja!==article.title) || (!ai && translated)" class="original-title"><summary>原文タイトルを見る</summary><p>{{ article.title }}</p></details>
  <p class="summary" :class="{'ai-summary':ai}">{{ ai?.summary_ja || summary || '詳しい内容は元記事でご覧ください。' }}</p>
  <details v-if="ai" class="ai-details"><summary>詳しく見る · 重要ポイントと活用アイデア</summary><h4>重要ポイント</h4>
    <ul><li v-for="point in ai.key_points" :key="point">{{ point }}</li></ul>
    <aside class="work-idea"><strong>仕事での活用アイデア</strong><p>{{ ai.work_idea }}</p><small>AIによる提案です。記事で実証された事実とは異なります。</small></aside>
  </details>
</template>
<style scoped>
.translation-note{font-size:11px;color:#526553;margin:0 0 8px}.original-title{font-size:11px;color:#687568;margin:0 0 12px;overflow-wrap:anywhere}.original-title summary{cursor:pointer;min-height:30px}.original-title p{margin:6px 0}
.ai-details{font-size:13px;line-height:1.8;overflow-wrap:anywhere;margin:10px 0 16px}.ai-details>summary{cursor:pointer;min-height:44px;padding:10px 0;color:#365440}.ai-details h4{margin:10px 0}.ai-details ul{padding-left:20px}.work-idea{background:#edf3e6;padding:14px;border-radius:12px;margin-top:14px}.work-idea p{margin:8px 0}.work-idea small{color:#526553}
.summary.ai-summary{display:block;-webkit-line-clamp:unset;max-height:none;overflow:visible}
</style>
