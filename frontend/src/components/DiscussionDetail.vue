<script setup>
import { computed } from 'vue'
import { categories, discussionFor, hnUrl, sectionsFor } from '../discussion.js'
const props = defineProps({ article: {type:Object, required:true} })
const discussion = computed(() => discussionFor(props.article))
const sections = computed(() => sectionsFor(props.article))
const analysis = computed(() => props.article.discussion_analysis)
const count = computed(() => Number.isSafeInteger(discussion.value?.comment_count) && discussion.value.comment_count >= 0 ? discussion.value.comment_count : null)
const sample = computed(() => Number.isSafeInteger(analysis.value?.sample_count) && analysis.value.sample_count >= 0 ? analysis.value.sample_count : null)
const sourceUrl = computed(() => {
  try { const u = new URL(props.article.url); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : null } catch { return null }
})
function dateLabel(value) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('ja-JP', {timeZone:'Asia/Tokyo',year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(value)) : '日時不明'
}
</script>
<template>
  <section class="discussion-detail" aria-labelledby="discussion-heading">
    <a class="back-link" href="#feed">← 記事一覧へ戻る</a>
    <p class="detail-eyebrow">HACKER NEWS · DISCUSSION</p>
    <h1 id="discussion-heading" tabindex="-1">{{ article.translation?.title_ja || article.title }}</h1>
    <div class="detail-links">
      <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener noreferrer">元記事を読む ↗</a>
      <a v-if="discussion" :href="hnUrl(discussion.story_id)" target="_blank" rel="noopener noreferrer">HNの議論を読む ↗</a>
    </div>
    <p v-if="discussion" class="detail-meta">{{ count === null ? 'コメント数不明' : `${count}件のコメント` }} · 確認 {{ dateLabel(discussion.checked_at) }} JST</p>
    <template v-if="sections.length">
      <p class="analysis-notice">AIによる議論分析 · {{ sample === null ? '取得できた' : `${sample}件の` }}コメントを対象にしています。議論全体の総意ではありません。</p>
      <p class="detail-meta">根拠を確認した日時：{{ dateLabel(analysis.checked_at) }} JST。解釈は元コメントでもご確認ください。</p>
      <section v-for="section in sections" :key="section.kind" class="analysis-section">
        <h2>{{ categories[section.kind] }}</h2>
        <ul><li v-for="(point, index) in section.points" :key="index">
          <p>{{ point.text_ja }}</p>
          <details><summary>根拠のコメントを見る（{{ point.evidence.length }}件）</summary>
            <div v-for="e in point.evidence" :key="e.comment_id" class="evidence">
              <blockquote>{{ e.quote }}</blockquote>
              <a :href="hnUrl(e.comment_id)" target="_blank" rel="noopener noreferrer">コメント #{{ e.comment_id }} ↗</a>
            </div>
          </details>
        </li></ul>
      </section>
    </template>
    <div v-else class="analysis-empty" role="status">
      <h2>表示できる分析はまだありません</h2>
      <p>分析が未実行、取得に失敗、または根拠が十分でない可能性があります。HNの元の議論をご覧ください。</p>
    </div>
  </section>
</template>
<style scoped>
.discussion-detail{max-width:760px;margin:36px auto 64px;overflow-wrap:anywhere}.back-link,.detail-links a,.evidence a{color:#365843;text-underline-offset:4px}.back-link{display:inline-block;padding:12px 0}.detail-eyebrow{font-size:11px;letter-spacing:.15em;color:#5c7163;margin-top:24px}.discussion-detail h1{font-size:clamp(24px,5vw,36px);line-height:1.5;margin:12px 0 20px}.detail-links{display:flex;gap:16px;flex-wrap:wrap}.detail-links a{padding:10px 0}.detail-meta{font-size:12px;color:#667467;line-height:1.8}.analysis-notice{background:#e9efe5;border-radius:12px;padding:18px;font-size:14px;line-height:1.8;margin-top:28px}.analysis-section,.analysis-empty{background:#fffefa;border:1px solid #e3e7dc;border-radius:16px;padding:24px;margin-top:20px}.analysis-section h2,.analysis-empty h2{font-size:18px;margin:0 0 16px}.analysis-section ul{padding-left:20px}.analysis-section li{margin-bottom:20px;line-height:1.8}.analysis-section summary{cursor:pointer;color:#47624d;font-size:13px;padding:10px 0;min-height:44px;box-sizing:border-box}.evidence{border-left:3px solid #d6e1cf;padding:8px 12px;margin:12px 0;font-size:13px}.evidence blockquote{margin:0 0 8px;white-space:pre-wrap}.analysis-empty p{line-height:1.8;font-size:14px}@media(max-width:600px){.analysis-section,.analysis-empty{padding:18px}.discussion-detail{margin-top:20px}}
</style>
