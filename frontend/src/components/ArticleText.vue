<script setup>
import { computed } from 'vue'
const props = defineProps({ article: {type:Object, required:true} })
const translated = computed(() => {
  const t = props.article.translation
  return t && t.language === 'ja' && typeof t.title_ja === 'string' && t.title_ja.trim() ? t : null
})
const summary = computed(() => translated.value && typeof translated.value.summary_ja === 'string' ? translated.value.summary_ja : props.article.summary)
</script>
<template>
  <h3><a :href="article.url" target="_blank" rel="noopener noreferrer">{{ translated?.title_ja || article.title }}<span class="sr-only">（新しいタブで開く）</span></a></h3>
  <p v-if="translated" class="translation-note">AI翻訳<span v-if="translated.summary_ja">・RSS説明文のAI要約</span></p>
  <details v-if="translated" class="original-title"><summary>原文タイトルを見る</summary><p lang="en">{{ article.title }}</p></details>
  <p class="summary">{{ summary || '詳しい内容は元記事でご覧ください。' }}</p>
</template>
<style scoped>
.translation-note{font-size:11px;color:#526553;margin:0 0 8px}.original-title{font-size:11px;color:#687568;margin:0 0 12px;overflow-wrap:anywhere}.original-title summary{cursor:pointer;min-height:30px}.original-title p{margin:6px 0}
</style>
