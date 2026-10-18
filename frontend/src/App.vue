<script setup>
import { ref, computed, onMounted } from 'vue'
const articles = ref([])
const selected = ref('all')
const loading = ref(true)
const error = ref(false)
const categories = [ ['all', 'すべて'], ['ai-tools', '新ツール'], ['business', '業務改善'], ['techniques', 'テクニック'] ]
const label = id => categories.find(c => c[0] === id)?.[1] || 'その他'
function safeUrl(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null } catch { return null }
}
const visible = computed(() => articles.value.filter(a => selected.value === 'all' || a.category === selected.value))
const latest = computed(() => articles.value.map(a => a.collected_at).filter(d => d && Number.isFinite(Date.parse(d))).sort((a,b) => Date.parse(b)-Date.parse(a))[0])
function dateLabel(value, time = false) {
  if (!value || !Number.isFinite(Date.parse(value))) return '公開日不明'
  return new Intl.DateTimeFormat('ja-JP', { timeZone: 'Asia/Tokyo', year: 'numeric', month: 'numeric', day: 'numeric', ...(time ? {hour:'2-digit',minute:'2-digit'} : {}) }).format(new Date(value))
}
async function load() {
  loading.value = true; error.value = false
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}data/articles.json`, { cache: 'no-cache', signal: controller.signal })
    if (!response.ok) throw new Error('load')
    const data = await response.json()
    if (!Array.isArray(data)) throw new Error('format')
    articles.value = data.filter(a => a && typeof a.title === 'string' && a.title.trim() && safeUrl(a.url)).map(a => ({...a, url:safeUrl(a.url), source:typeof a.source === 'string' ? a.source : '情報源不明', summary:typeof a.summary === 'string' ? a.summary : ''})).sort((a,b) => (Date.parse(b.published_at) || 0) - (Date.parse(a.published_at) || 0))
    if (data.length && !articles.value.length) throw new Error('invalid entries')
  } catch { error.value = true } finally { clearTimeout(timer); loading.value = false }
}
onMounted(load)
</script>

<template>
  <a class="skip" href="#feed">記事一覧へ</a>
  <header class="topbar"><a class="brand" href="./"><span class="brand-mark" aria-hidden="true">✳</span> AI Catchup Hub<span class="edition">PERSONAL FEED</span></a><span class="header-note">小さな発見、大きなヒント。</span></header>
  <main>
    <section class="intro" aria-labelledby="headline">
      <div class="eyebrow"><span></span> YOUR WINDOW INTO AI</div>
      <h1 id="headline">気になるAIを、<br>ひとつ見つけよう。</h1>
      <p>全部追わなくていい。<br class="mobile-break">興味が湧いたものから、少しずつ。</p>
      <div class="intro-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><span class="spark">✳</span><span class="art-dot"></span><span class="art-label">a little curiosity.</span></div>
    </section>
    <section id="feed" aria-labelledby="feed-heading">
      <div class="feed-heading"><h2 id="feed-heading">発見のフィード <span>DISCOVER</span></h2><span class="updated" v-if="latest">収集 {{ dateLabel(latest, true) }} JST</span></div>
      <nav class="filters" aria-label="記事カテゴリ"><button v-for="[id, name] in categories" :key="id" :class="{active:selected===id}" :aria-pressed="selected===id" @click="selected=id">{{ name }}<span>{{ id==='all' ? articles.length : articles.filter(a=>a.category===id).length }}</span></button></nav>
      <div class="feed-meta"><span>公開日の新しい順</span><span>分類は情報源をもとにした目安です</span></div>
      <div v-if="loading" class="state" role="status"><span class="loading-dot"></span>記事を読み込んでいます</div>
      <div v-else-if="error" class="state" role="alert"><h3>記事を読み込めませんでした</h3><p>少し待ってから、もう一度お試しください。</p><button class="retry" @click="load">もう一度読み込む</button></div>
      <div v-else-if="!visible.length" class="state" role="status"><span class="empty-icon" aria-hidden="true">○</span><h3>{{ articles.length ? 'このカテゴリの記事はまだありません' : '記事はまだ届いていません' }}</h3><p>{{ articles.length ? 'ほかのカテゴリから、気になる話題を探してみましょう。' : '記事が追加されると、ここに表示されます。' }}</p><button v-if="selected!=='all'" class="retry" @click="selected='all'">すべての記事を見る</button></div>
      <template v-else><p class="sr-only" role="status">{{ visible.length }}件の記事</p><div class="cards"><article v-for="article in visible" :key="article.id || article.url" class="card" :class="{'tool-card':article.category==='ai-tools'}"><div class="card-top"><span class="category">{{ label(article.category) }}</span><span class="source-mark" aria-hidden="true">{{ article.source.startsWith('Zenn') ? 'Z' : 'G' }}</span></div><h3><a :href="article.url" target="_blank" rel="noopener noreferrer">{{ article.title }}<span class="sr-only">（新しいタブで開く）</span></a></h3><p class="summary">{{ article.summary || '概要はありません。気になる内容は元記事でご覧ください。' }}</p><div class="card-footer"><div><span class="source">{{ article.source }}</span><time v-if="article.published_at" :datetime="article.published_at">{{ dateLabel(article.published_at) }}</time><span v-else class="date">公開日不明</span></div><a class="read-link" :href="article.url" target="_blank" rel="noopener noreferrer" :aria-label="`${article.title} の元記事を読む（新しいタブ）`">元記事へ <span aria-hidden="true">↗</span></a></div></article></div></template>
    </section>
    <footer><span class="footer-mark">✳</span><p>今日は、ひとつの発見で十分。</p><small>概要は配信元の文章です。詳しい内容は元記事でご確認ください。</small></footer>
  </main>
</template>
