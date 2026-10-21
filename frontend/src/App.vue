<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import ArticleText from './components/ArticleText.vue'
import DiscussionDetail from './components/DiscussionDetail.vue'
import { discussionFor, discussionHash, routeFromHash } from './discussion.js'
import { selectFeed, highlights, commentCount, recommendationReason, applicationIdea } from './feed.js'
import { safeUrl, saveKinds } from './savedArticles.js'
import { useSavedArticles } from './useSavedArticles.js'
import SaveControls from './components/SaveControls.vue'
import FeedTabs from './components/FeedTabs.vue'
const saved = useSavedArticles()
const tab = ref('recommended')
const discussionsOnly = ref(false)
const savedKind = ref('all')
const now = ref(Date.now())
let clockTimer
const allKnown = computed(() => {
  const known = new Map(saved.items.value.map(s=>[s.url,{...s.article,saved_snapshot:true}]))
  articles.value.forEach(a=>known.set(a.url,a))
  return [...known.values()]
})
const route = ref('')
const articles = ref([])
const detailArticle = computed(() => allKnown.value.find(a => a.url === route.value))
function syncRoute() { route.value = routeFromHash(window.location.hash) }
const selected = ref('all')
const loading = ref(true)
const error = ref(false)
watch([route, () => loading.value], async () => {
  await nextTick()
  document.getElementById(route.value ? 'discussion-heading' : 'feed-heading')?.focus()
})
const categories = [ ['all', 'すべて'], ['ai-tools', '新ツール'], ['business', '業務改善'], ['techniques', 'テクニック'] ]
const label = id => categories.find(c => c[0] === id)?.[1] || 'その他'
const visible = computed(() => selectFeed(articles.value, {
  tab:tab.value, category:selected.value, discussionsOnly:discussionsOnly.value,
  savedKind:savedKind.value, savedItems:saved.items.value, now:now.value,
}))
const spotlight = computed(() => highlights(articles.value,now.value))
const categoryPool = computed(() => selectFeed(articles.value,{tab:tab.value,savedItems:saved.items.value,now:now.value}))
const sortLabel = computed(() => ({
  recommended:'関心分野・新しさ・コメント数で選定',
  hot:'コメント数の多い順（確認できた議論のみ）',
  new:'公開日の新しい順', saved:'保存区分を変更した順',
}[tab.value]))
function resetFilters() { selected.value='all';discussionsOnly.value=false;savedKind.value='all' }
watch(tab,resetFilters)
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
onMounted(() => { syncRoute(); window.addEventListener('hashchange', syncRoute); clockTimer=setInterval(()=>{now.value=Date.now()},60000); load() })
onUnmounted(() => {window.removeEventListener('hashchange', syncRoute);clearInterval(clockTimer)})
</script>

<template>
  <a class="skip" href="#feed">記事一覧へ</a>
  <header class="topbar"><a class="brand" href="./"><span class="brand-mark" aria-hidden="true">✳</span> AI Catchup Hub<span class="edition">PERSONAL FEED</span></a><span class="header-note">小さな発見、大きなヒント。</span></header>
  <main>
    <p v-if="saved.warning.value" class="storage-warning" role="alert">{{ saved.warning.value }}</p>
    <p class="sr-only" role="status">{{ saved.notice.value }}</p>
    <template v-if="route && detailArticle && !loading">
      <SaveControls :article="detailArticle" :labels="saved.labels(detailArticle)" @toggle="saved.toggle(detailArticle,$event)" />
      <p v-if="detailArticle.saved_snapshot" class="saved-note">保存時の情報です。現在のフィードには含まれていません。</p>
      <DiscussionDetail :article="detailArticle" />
    </template>
    <section v-else-if="route && !loading" class="state"><h1 id="discussion-heading" tabindex="-1">この記事は現在のフィードにありません</h1><a href="#feed">記事一覧へ戻る</a></section>
    <section v-show="!route" class="intro" aria-labelledby="headline">
      <div class="eyebrow"><span></span> YOUR WINDOW INTO AI</div>
      <h1 id="headline">気になるAIを、<br>ひとつ見つけよう。</h1>
      <p>全部追わなくていい。<br class="mobile-break">興味が湧いたものから、少しずつ。</p>
      <div class="intro-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><span class="spark">✳</span><span class="art-dot"></span><span class="art-label">a little curiosity.</span></div>
    </section>
    <section v-if="!route && !loading && !error && spotlight.items.length" class="spotlight" aria-labelledby="spotlight-heading">
      <div class="spotlight-heading"><h2 id="spotlight-heading">{{ spotlight.today ? '今日の注目ニュース' : '直近の注目ニュース' }}</h2><span>最大3件 · {{ spotlight.today ? '日本時間の当日公開分' : '当日公開分がないため掲載中の記事から選定' }}</span></div>
      <ol class="spotlight-grid"><li v-for="(article,index) in spotlight.items" :key="article.url">
        <span class="spotlight-number">0{{ index+1 }}</span>
        <p class="spotlight-reason">{{ recommendationReason(article) }}</p>
        <h3><a :href="article.url" target="_blank" rel="noopener noreferrer">{{ article.translation?.title_ja || article.title }}<span class="sr-only">（元記事を新しいタブで開く）</span></a></h3>
        <small>{{ article.source }} · {{ dateLabel(article.published_at) }}</small>
      </li></ol>
    </section>
    <section v-show="!route || loading" id="feed"  aria-labelledby="feed-heading">
      <div class="feed-heading"><h2 id="feed-heading" tabindex="-1">発見のフィード <span>DISCOVER</span></h2><span class="updated" v-if="latest">収集 {{ dateLabel(latest, true) }} JST</span></div>
      <FeedTabs v-model="tab" :saved-count="saved.items.value.length" />
      <p v-if="tab==='saved'" class="saved-note">保存はこのブラウザー内だけです。別端末とは同期されません。掲載終了した記事は保存時の情報を表示します。</p>
      <nav class="filters" aria-label="記事カテゴリ">
        <button v-for="[id,name] in categories" :key="id" :class="{active:selected===id}" :aria-pressed="selected===id" @click="selected=id">{{ name }}<span>{{ id==='all' ? categoryPool.length : categoryPool.filter(a=>a.category===id).length }}</span></button>
      </nav>
      <div class="feed-options">
        <label class="discussion-filter"><input v-model="discussionsOnly" type="checkbox"> 議論ありのみ</label>
        <label v-if="tab==='saved'" class="saved-filter">保存区分 <select v-model="savedKind"><option value="all">すべて</option><option v-for="[id,label] in saveKinds" :key="id" :value="id">{{ label }}</option></select></label>
        <button v-if="selected!=='all'||discussionsOnly||savedKind!=='all'" class="clear-filter" @click="resetFilters">絞り込みを解除</button>
      </div>
      <div class="feed-meta"><span>{{ sortLabel }}</span><span>分類・おすすめはルールによる目安です</span></div>
      <div v-if="loading" class="state" role="status"><span class="loading-dot"></span>記事を読み込んでいます</div>
      <div v-else-if="error && tab!=='saved'" class="state" role="alert"><h3>記事を読み込めませんでした</h3><p>保存済みの記事は「保存済み」から閲覧できます。</p><button class="retry" @click="load">もう一度読み込む</button></div>
      <div v-else-if="!visible.length" class="state" role="status">
        <span class="empty-icon" aria-hidden="true">○</span>
        <h3>{{ tab==='saved' && !saved.items.value.length ? '保存した記事はまだありません' : tab==='hot' ? 'コメント付きの議論はまだ見つかっていません' : '表示条件に合う記事はありません' }}</h3>
        <p>{{ tab==='saved' ? '記事の「あとで読む」「試したい」「仕事に使えそう」で保存できます。' : '別のフィードに切り替えるか、絞り込み条件を変更してください。' }}</p>
        <button v-if="selected!=='all'||discussionsOnly||savedKind!=='all'" class="retry" @click="resetFilters">絞り込みを解除</button>
      </div>
      <template v-else>
        <p class="sr-only" role="status">{{ visible.length }}件の記事</p>
        <div class="cards">
          <article v-for="article in visible" :key="article.url" class="card" :class="{'tool-card':article.category==='ai-tools'}">
            <div class="card-top"><span class="category">{{ label(article.category) }}</span><span class="source-mark" aria-hidden="true">{{ article.source.startsWith('Zenn') ? 'Z' : '✳' }}</span></div>
            <p v-if="article.saved_snapshot" class="saved-note">保存時の情報 · 現在のフィード掲載外</p>
            <ArticleText :article="article" />
            <p v-if="tab==='recommended'" class="recommendation-note">{{ recommendationReason(article) }}</p>
            <aside v-if="applicationIdea(article)" class="application-idea"><strong>活用アイデア（提案）</strong><p>{{ applicationIdea(article) }}</p><small>記事の事実とは別の、関心分野に基づく提案です。</small></aside>
            <a v-if="discussionFor(article)" class="discussion-link" :href="discussionHash(article)" :aria-label="article.title + ' の議論を見る'">{{ commentCount(article)===null ? 'コメント数不明' : commentCount(article)+'件のコメント' }} · 議論を見る →</a>
            <SaveControls :article="article" :labels="saved.labels(article)" @toggle="saved.toggle(article,$event)" />
            <div class="card-footer"><div><span class="source">{{ article.source }}</span><time v-if="article.published_at" :datetime="article.published_at">{{ dateLabel(article.published_at) }}</time><span v-else class="date">公開日不明</span></div><a class="read-link" :href="article.url" target="_blank" rel="noopener noreferrer" :aria-label="article.title+' の元記事を読む（新しいタブ）'">元記事へ <span aria-hidden="true">↗</span></a></div>
          </article>
        </div>
      </template>
    </section>
    <footer><span class="footer-mark">✳</span><p>今日は、ひとつの発見で十分。</p><small>AI翻訳・要約にはラベルを表示しています。正確な内容は元記事でご確認ください。</small></footer>
  </main>
</template>

<style scoped>
.application-idea{font-size:12px;border-left:3px solid #b7caa6;padding:8px 12px;background:#f5f8f0;margin:0 0 16px;overflow-wrap:anywhere}.application-idea strong{font-size:11px;color:#4d6543}.application-idea p{margin:5px 0;line-height:1.8}.application-idea small{font-size:10px;color:#6a7863}
.spotlight{margin:0 0 32px}.spotlight-heading{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:14px}.spotlight-heading>span{font-size:11px;color:#687568}.spotlight-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;list-style:none;margin:0;padding:0}.spotlight-grid li{border:1px solid #d4dfca;background:#edf2e7;border-radius:14px;padding:20px;overflow-wrap:anywhere}.spotlight-number{font-size:12px;letter-spacing:2px;color:#6b8060}.spotlight-grid h3{font-size:15px;line-height:1.8;margin:6px 0 12px}.spotlight-grid h3 a{text-decoration:none}.spotlight-grid h3 a:hover{text-decoration:underline}.spotlight-grid small{font-size:10px;color:#5d6e56}.spotlight-reason,.recommendation-note{font-size:11px;color:#59704b;margin:8px 0}.feed-options{display:flex;align-items:center;flex-wrap:wrap;gap:14px;margin:12px 0}.discussion-filter,.saved-filter{font-size:12px;display:flex;align-items:center;gap:7px;min-height:44px}.discussion-filter input{width:18px;height:18px;accent-color:#34543e}.saved-filter select{font:inherit;min-height:44px;border:1px solid #cbd7c4;border-radius:7px;background:#fff;padding:7px}.clear-filter{min-height:44px;border:0;background:transparent;font-size:12px;text-decoration:underline;color:#496046}.saved-note{font-size:12px;line-height:1.8;color:#6b7863}.storage-warning{padding:16px;border:1px solid #d5ba86;background:#fff6df;border-radius:10px;font-size:13px;margin-top:20px}@media(max-width:700px){.spotlight-grid{grid-template-columns:minmax(0,1fr)}.spotlight-grid li{padding:16px}.spotlight{margin-bottom:24px}.spotlight-heading>span{font-size:10px}}
.discussion-link{display:inline-block;color:#365843;background:#edf2e8;border-radius:8px;padding:12px 14px;margin:0 0 16px;font-size:13px;text-decoration:none}.discussion-link:hover{background:#e0ead9}.discussion-link:focus-visible{outline:2px solid #365843;outline-offset:3px}
</style>
