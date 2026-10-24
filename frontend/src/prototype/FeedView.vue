<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  stories: { type: Array, required: true },
  publicMode: Boolean,
  generatedMode: Boolean,
  trialMode: Boolean,
  generatedError: Boolean,
  homeUrl: { type: String, default: './' },
  edition: { type: Object, default: null },
  saveEnabled: Boolean,
  savedView: Boolean,
  savedUrls: { type:Array, default:() => [] },
  legacySaved: { type:Array, default:() => [] },
  storageWarning: { type:String, default:'' },
})
const emit = defineEmits(['toggle-save','change-view','remove-legacy'])
const { publicMode, generatedMode, trialMode, generatedError, homeUrl } = props
const stories = computed(() => props.stories)
const countLabel = computed(() => String(props.stories.length).padStart(2, '0'))

const active = ref(0)
const opened = ref(null)
const preferred = ref(new Set())
const notice = ref('')
const dialog = ref(null)
const heading = ref(null)
const commentItems = computed(() => opened.value?.comments || [])
function avatarIndex(name) { return [...new Set(commentItems.value.map(comment => comment[0]))].indexOf(name) % 4 }
function replyLabel(parent) {
  return Number.isInteger(parent) && commentItems.value[parent] ? `${commentItems.value[parent][0]}へ` : '返信'
}
let lastTrigger, observer, noticeTimer
function notify(message) {
  notice.value = message
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => notice.value = '', 4500)
}
function isSaved(story) { return props.savedUrls.includes(story.url) }
async function toggleSave(story) {
  emit('toggle-save', story)
  await nextTick()
  notify(props.storageWarning ? '保存状態を確認してください。' : isSaved(story) ? 'このブラウザーに保存しました。' : '保存を解除しました。')
}
function changeView(view) {
  closeComments()
  emit('change-view', view)
}
function moreLike(story) {
  const next = new Set(preferred.value)
  if (next.has(story.id)) next.delete(story.id)
  else next.add(story.id)
  preferred.value = next
  notice.value = next.has(story.id) ? `「${story.category}」が好き、を選びました。目印を付けました。並び順には反映されません。` : '好みの選択を解除しました。'
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => notice.value = '', 4500)
}
async function openComments(story, event) {
  lastTrigger = event.currentTarget
  opened.value = story
  await nextTick()
  dialog.value.showModal()
  heading.value.focus()
  document.body.style.overflow = 'hidden'
}
function closeComments() { dialog.value?.close() }
function afterClose() {
  document.body.style.overflow = ''
  opened.value = null
  lastTrigger?.focus()
}
function go(index) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  document.getElementById(`story-${index}`)?.scrollIntoView({ behavior: reduce ? 'instant' : 'smooth', block: 'start' })
}
function observeStories() {
  observer?.disconnect()
  document.querySelectorAll('[data-index]').forEach(el => observer?.observe(el))
}
watch(() => props.stories, async () => {
  active.value = 0
  if (opened.value && !props.stories.some(s => s.url === opened.value.url)) closeComments()
  await nextTick()
  observeStories()
})
onMounted(() => {
  observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) active.value = Number(entry.target.dataset.index)
  }, { rootMargin: '-15% 0px -45% 0px', threshold: 0 })
  observeStories()
})
onUnmounted(() => { observer?.disconnect(); clearTimeout(noticeTimer); document.body.style.overflow = '' })
</script>

<template>
  <a href="#story-0" class="skip-link">ニュースへ進む</a>
  <header class="app-header" :class="{ 'reader-header':saveEnabled }">
    <a class="wordmark" :href="homeUrl"><span aria-hidden="true">✳</span> AI Catchup Hub</a>
    <nav v-if="saveEnabled" class="reader-tabs" aria-label="記事の表示">
      <button :aria-pressed="!savedView" @click="changeView('feed')">✨ 発見</button>
      <button :aria-pressed="savedView" @click="changeView('saved')">🔖 保存済み <span>{{ savedUrls.length }}</span></button>
    </nav>
    <span v-else class="preview-badge">{{ publicMode ? '先行公開' : 'LOCAL PREVIEW' }}</span>
  </header>
  <aside class="desktop-note">
    <p class="eyebrow">YOUR DAILY CURIOSITY</p>
    <h1>ちょっと気になる。<br>読んだら、わかる。</h1>
    <p v-if="savedView">気になった記事を、<br>あとからもう一度。</p>
    <p v-else>最新AIの話を、<br>図とコメントでひとつずつ。</p>
    <div class="sample-label">{{ publicMode ? '☕ 図と会話で、ひと息キャッチアップ' : '🧪 あなた向けの画面試作' }}</div>
    <p v-if="savedView" class="fine">保存 {{ savedUrls.length }}件<br>このブラウザー内だけに保存します。<br>別端末への同期はありません。</p>
    <p v-else class="fine">実記事{{ stories.length }}件・{{ generatedMode ? 'Gemini実生成（修正前）' : (edition?.generated ? 'AIによる説明・図・会話' : publicMode ? '編集済みの見本' : '固定サンプル') }}<br>コメントはすべてAIによる架空の会話<br>{{ edition ? `記事追加：${edition.updated}` : '確認日：2026/10/24' }}</p>
    <p v-if="generatedMode" class="trial-status">初回の実生成結果をそのまま表示。<br>関西弁・事実チェックの修正版ではありません。</p>
    <p v-if="trialMode && !publicMode" class="trial-status">このチャットで生成・編集した見本です。<br>Gemini実生成へ切り替えて見比べられます。</p>
    <nav aria-label="ニュースを選ぶ" class="desktop-nav">
      <button v-for="(story, index) in stories" :key="story.id" :aria-current="active === index ? 'step' : undefined" @click="go(index)"><span>{{ story.emoji }}</span><span>{{ story.category }}</span><span>0{{ index + 1 }}</span></button>
    </nav>
    <a v-if="!publicMode" href="./" class="original-link">通常のフィードを見る ↗</a>
    <a v-if="!publicMode" :href="trialMode ? './catchup-preview.html' : './catchup-preview.html?trial=1'" class="original-link">{{ trialMode ? '最初の3件の見本へ ↗' : '実記事5件のお試しへ ↗' }}</a>
  </aside>
  <main class="feed" :aria-label="`実記事${stories.length}件のフィード`">
    <div class="feed-intro"><span>{{ savedView ? '🔖 あなたの保存一覧' : '✨ あなたの発見フィード' }}</span><span>{{ savedView ? '保存した順に' : 'スクロールで次へ ↓' }}</span></div>
    <p v-if="storageWarning" class="storage-warning" role="alert">{{ storageWarning }}</p>
    <p v-if="savedView" class="saved-help">このブラウザー内だけに保存します。端末間の同期はありません。ブラウザーの保存データを消すと、記事の保存も失われます。</p>
    <section v-if="savedView && !stories.length && !legacySaved.length" class="saved-empty">
      <span aria-hidden="true">🔖</span><h2>保存した記事はまだありません</h2>
      <p>気になる記事の「保存する」を押すと、ここから読み返せます。</p>
      <button @click="changeView('feed')">✨ 発見フィードへ</button>
    </section>
    <nav v-if="!publicMode" class="comparison-nav" aria-label="同じ画面で内容を比較">
      <a href="./catchup-preview.html?trial=1" :aria-current="trialMode ? 'page' : undefined">💡 見本の5件</a>
      <a href="./catchup-preview.html?gemini=1" :aria-current="generatedMode ? 'page' : undefined">🧪 Geminiの実生成</a>
    </nav>
    <p v-if="generatedMode" class="trial-banner generated-banner">🧪 Geminiの初回生成 · 内容は確認中<br><small>2026/10/24の結果を未修正で表示。関西弁・事実チェックの修正版は未生成です。</small></p>
    <p v-if="generatedError" class="trial-banner" role="alert">生成結果を表示できませんでした。見本へ切り替えて確認してください。</p>
    <p v-if="trialMode && !publicMode" class="trial-banner">💡 実記事5件の見本 · このチャットで生成<br><small>このページの内容はGeminiの出力ではありません</small></p>
    <template v-if="!savedView">
      <p v-if="publicMode && edition" class="trial-banner">🌱 毎日19:17に、次の発見を<br><small>最大3記事を自動更新予定。実行時刻は前後することがあります。<br>{{ edition.message }}<br>更新確認：{{ edition.checked }}<br>{{ edition.generated ? '説明・図・会話はAI生成です。事実は元記事でご確認ください。' : '初回の生成が通るまでは、2026/10/24の見本5件を表示します。' }}</small></p>
      <p v-else-if="publicMode" class="trial-banner">🌱 まずは5件から、先行公開<br><small>2026/10/24時点の固定記事です。コメントはAIによる架空の会話。ニュースの自動更新は準備中です。</small></p>
    </template>
    <article v-for="(story, index) in stories" :id="`story-${index}`" :key="story.id" :data-index="index" class="story" :class="story.theme" :aria-labelledby="`title-${story.id}`">
      <div class="story-top"><span class="topic">{{ story.emoji }} {{ story.category }}</span><span class="number">{{ String(index + 1).padStart(2, '0') }} / {{ countLabel }}</span></div>
      <h2 :id="`title-${story.id}`">{{ story.title }}</h2>
      <p v-if="story.saved_snapshot" class="snapshot-note">🔖 保存時の内容 · 現在のフィード掲載外</p>
      <p class="lead">{{ story.lead }}</p>
      <figure v-if="story.inputs.length" class="visual" :aria-label="`${story.category}の仕組みの図解`">
        <div class="visual-head"><span>ひと目でわかる</span><span aria-hidden="true">✦</span></div>
        <div class="question"><span aria-hidden="true">💬</span> {{ story.question }}</div>
        <div class="connector" aria-hidden="true">↓</div>
        <div v-if="story.id === 'earth'" class="plan">🧠 分析の段取りを考える</div>
        <div class="input-nodes" :class="{ sequential: story.layout === 'steps' }"><div v-for="item in story.inputs" :key="item">{{ item }}</div></div>
        <div class="connector merge" aria-hidden="true">↓</div>
        <div class="result">{{ story.result }}</div>
        <div v-if="story.id === 'skills'" class="destinations"><span>↙ AIサービスA</span><span>AIサービスB ↘</span></div>
        <figcaption>{{ story.diagramNote }}</figcaption>
      </figure>
      <div class="explanation">
        <p v-if="story.reviewNote" class="review-note">🔎 {{ story.reviewNote }}</p>
        <section><h3>🔎 何が変わった？</h3><p>{{ story.changed }}</p></section>
        <section class="example"><h3>💡 例えば、こんなこと</h3><p>{{ story.example }}</p></section>
        <section class="context"><h3>📌 知っておきたいこと</h3><p>{{ story.caution }}</p></section>
      </div>
      <div class="source"><span>{{ story.source }} · {{ story.date }}</span><a :href="story.url" target="_blank" rel="noopener noreferrer">{{ story.sourceLabel || '公式記事' }} ↗</a></div>
      <section class="comment-preview" :aria-label="`${story.category}の架空コメントの抜粋`">
        <div class="comment-preview-heading"><strong>💬 ちょっと気になる会話</strong><span>AIの架空コメント</span></div>
        <p class="teaser">{{ story.teaser }}</p>
        <p class="second-teaser">↳ {{ story.comments[story.id === 'sonnet' ? 3 : 1][1] }}</p>
        <button class="read-comments" @click="openComments(story, $event)">コメントを読む <span>{{ story.comments.length }}件 <span aria-hidden="true">↗</span></span></button>
      </section>
      <div class="actions">
        <button v-if="saveEnabled" class="save-story" :aria-pressed="isSaved(story)" :aria-label="(isSaved(story) ? '保存を解除：' : '保存する：') + story.title.replace('\n', '')" @click="toggleSave(story)">{{ isSaved(story) ? '🔖 保存済み' : '🔖 保存する' }}</button>
        <button v-if="!savedView" class="more-like" :aria-pressed="preferred.has(story.id)" @click="moreLike(story)">{{ preferred.has(story.id) ? '✓ 好きなテーマ' : '＋ もっとこれ' }}</button><span v-if="!saveEnabled">読むだけでOK ☕</span>
      </div>
      <button v-if="index < stories.length - 1" class="next" @click="go(index + 1)">次の発見へ ↓</button>
      <p v-else class="end-note">☕ ひとまずここまで。どの会話が気になった？</p>
    </article>
    <section v-if="savedView && legacySaved.length" class="legacy-saved">
      <h2>以前の画面で保存した記事</h2>
      <p>説明・図・会話の保存がない記事は、元記事から読めます。</p>
      <div v-for="item in legacySaved" :key="item.url" class="legacy-saved-card">
        <a :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.article.title }} ↗</a>
        <span>{{ item.article.source }}</span>
        <button :aria-label="'保存を解除：' + item.article.title" @click="emit('remove-legacy', item.article)">保存を解除</button>
      </div>
    </section>
    <footer v-if="!publicMode">ローカル試作 · {{ generatedMode ? '取得済みの実生成結果を表示・継続更新は未接続' : '自動収集・自動生成は未接続' }}<br><a href="./catchup-preview.html">最初の3件の見本へ</a><br><a href="./">通常のフィードへ戻る</a></footer>
    <footer v-if="publicMode">☕ AI Catchup Hub{{ edition ? ` · 記事追加：${edition.updated}` : ' · 2026/10/24版' }}<br>記事の事実・利用条件はリンク先でご確認ください。<br>コメントは実在する人の投稿ではありません。</footer>
  </main>
  <nav class="progress" aria-label="ニュースの位置"><button v-for="(story, index) in stories" :key="story.id" :aria-label="`${index + 1}件目：${story.category}`" :aria-current="active === index ? 'step' : undefined" @click="go(index)"><span></span></button></nav>
  <div class="toast" role="status">{{ notice }}</div>
  <dialog ref="dialog" class="comments-dialog" aria-labelledby="comments-heading" aria-describedby="fiction-notice" @close="afterClose" @click="event => { if (event.target === dialog) closeComments() }">
    <template v-if="opened">
      <div class="sheet-header"><div><p>READ THE CONVERSATION</p><h2 id="comments-heading" ref="heading" tabindex="-1">💬 コメント <span>{{ opened.comments.length }}</span></h2></div><button class="close" aria-label="コメント欄を閉じる" @click="closeComments">✕</button></div>
      <div class="sheet-scroll">
        <p id="fiction-notice" class="fiction-notice">🪄 AIによる架空の会話です。<br>実在の投稿・利用者の声ではありません。</p>
        <p v-if="generatedMode" class="generation-note">初回の実生成を未修正で表示しています。内容は確認中です。</p>
        <p class="sheet-title">{{ opened.title.replace('\n', '') }}</p>
        <p v-if="opened.reviewNote" class="review-note">🔎 {{ opened.reviewNote }}</p>
        <ol class="comments">
          <li v-for="([name, text, reply, parent], index) in commentItems" :key="index" :class="{ reply }">
            <span class="avatar" :class="`avatar-${avatarIndex(name)}`" aria-hidden="true">{{ ['🐈','🌿','🍊','🪐'][avatarIndex(name)] }}</span>
            <div><span class="comment-name">{{ name }}</span><span v-if="reply" class="reply-marker"> ↳ {{ replyLabel(parent) }}</span><p>{{ text }}</p></div>
          </li>
        </ol>
        <p class="conversation-end">ここまで読んだら、ニュースがちょっと身近に。☕</p>
        <a class="sheet-source" :href="opened.url" target="_blank" rel="noopener noreferrer">🔗 事実は{{ opened.sourceLabel || '公式記事' }}で確認する ↗</a>
      </div>
      <div class="sheet-footer">読む専用のコメント欄 · 返信しなくて大丈夫</div>
    </template>
  </dialog>
</template>

<style scoped>
.reader-tabs{display:flex;gap:4px;flex-shrink:0}.reader-tabs button{border-radius:24px;background:transparent;color:#617359;padding:7px 12px;font-size:12px;border:1px solid transparent}.reader-tabs button[aria-pressed=true]{background:#e3ecdc;border-color:#b8c9aa;color:#304b35;font-weight:700}.reader-tabs span{font-size:10px;margin-left:3px}
.actions{gap:8px;flex-wrap:wrap}.save-story{border:1px solid #c1d0b6;border-radius:30px;background:#f0f5e9;color:#375333;padding:8px 16px;font-size:12px}.save-story[aria-pressed=true]{background:#dae8cc;border-color:#91ac7c}.more-like{margin-left:auto}.saved-help,.snapshot-note{font-size:11px;color:#77836e;line-height:1.8}.saved-help{margin:0 4px 20px}.snapshot-note{padding:8px 11px;background:#edf1e6;border-radius:8px}.storage-warning{font-size:12px;line-height:1.8;padding:13px 16px;border:1px solid #dbc29e;border-radius:12px;background:#fff3df;color:#795d36}
.saved-empty,.legacy-saved{background:#fffef9;border:1px solid #dce4d5;border-radius:22px;padding:26px;margin-bottom:24px}.saved-empty{text-align:center;scroll-snap-align:start}.saved-empty>span{font-size:32px}.saved-empty h2,.legacy-saved h2{font-size:18px}.saved-empty p,.legacy-saved>p{font-size:12px;color:#6c7868;line-height:1.8}.saved-empty button{border-radius:24px;padding:10px 18px;background:#e3ecdc;color:#304b35;margin-top:10px}.legacy-saved-card{display:grid;gap:8px;padding:16px 0;border-top:1px solid #e5eadd}.legacy-saved-card a{font-size:14px;font-weight:700;overflow-wrap:anywhere}.legacy-saved-card>span{font-size:11px;color:#77836e}.legacy-saved-card button{justify-self:start;border:1px solid #d9e2d0;border-radius:24px;font-size:11px;padding:7px 12px;background:transparent;color:#6a7a68}
@media(max-width:560px){.reader-header{padding-inline:12px;gap:6px}.reader-header .wordmark{font-size:12px;gap:4px}.reader-header .wordmark>span{font-size:25px}.reader-tabs button{font-size:10px;padding:6px 8px}}
.trial-banner{scroll-snap-align:start;scroll-margin-top:8px}
.comparison-nav{scroll-snap-align:start;scroll-margin-top:8px}
.input-nodes>div{white-space:normal;overflow-wrap:anywhere;min-width:0}
.comparison-nav{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}.comparison-nav a{display:flex;align-items:center;justify-content:center;flex:1;min-width:130px;padding:10px;border:1px solid #d6dfcf;border-radius:12px;text-decoration:none;font-size:11px;color:#617359;background:#fafbf6}.comparison-nav a[aria-current]{background:#e3ecdc;border-color:#a2b795;color:#304b35;font-weight:700}
.generated-banner{background:#f4ecdc!important;border-color:#e7d5b2!important;color:#725c38!important}.review-note{padding:11px 13px;border-left:3px solid #c8a361;background:#faf3e6;font-size:11px;line-height:1.8;color:#81663d}.generation-note{font-size:10px;color:#8b7656;margin:12px 0}
.trial-banner{background:#e7eddf;border:1px solid #d2dec6;border-radius:12px;padding:12px 15px;margin:0 0 16px;font-size:12px;color:#4b6548;line-height:1.8}
.trial-banner small{font-size:10px;color:#72806b}
.trial-status{font-size:11px;line-height:1.8;color:#756282;padding:10px 12px;background:#eee8f5;border-radius:10px}
.sequential{gap:15px}
.sequential>div{position:relative}
.sequential>div:not(:last-child)::after{content:'→';position:absolute;right:-13px;top:50%;transform:translateY(-50%);color:var(--deep);font-size:11px}
.original-link{margin-right:12px}
@media(max-width:360px){.sequential{gap:12px}.sequential>div:not(:last-child)::after{right:-11px}}
</style>
