<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import AskAiDialog from '../components/AskAiDialog.vue'
import ArticleActionIcon from '../components/ArticleActionIcon.vue'
import StoryDiagram from '../components/StoryDiagram.vue'
import CommentAvatar from '../components/CommentAvatar.vue'

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
const expandedComments = ref(new Set())
const asking = ref(null), askContext = ref(''), askReturnFocus = ref(null)
const notice = ref('')
function sourceDomain(url) { return new URL(url).hostname }
function replyLabel(story, parent) {
  return Number.isInteger(parent) && story.comments[parent] ? `${story.comments[parent][0]}へ` : '返信'
}
let observer, noticeTimer
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
  emit('change-view', view)
}
function openAsk(story, event) {
  askReturnFocus.value = event.currentTarget
  asking.value = story
}
function toggleComments(story) {
  const next = new Set(expandedComments.value)
  if (next.has(story.id)) next.delete(story.id)
  else next.add(story.id)
  expandedComments.value = next
}
async function closeCommentsFromEnd(story) {
  toggleComments(story)
  await nextTick()
  const trigger = document.getElementById('comments-toggle-' + story.id)
  trigger?.focus({ preventScroll: true })
  trigger?.scrollIntoView({ block: 'center', behavior: 'instant' })
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
  expandedComments.value = new Set()
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
      <button :aria-pressed="!savedView" @click="changeView('feed')">発見</button>
      <button :aria-pressed="savedView" @click="changeView('saved')">保存済み <span>{{ savedUrls.length }}</span></button>
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
      <details v-if="publicMode && edition" class="edition-status">
        <summary><span>{{ edition.generated ? `🌱 記事追加：${edition.updated}` : `🌱 見本${stories.length}件を表示中` }}</span><span class="edition-detail-label">更新の詳細</span></summary>
        <div class="edition-details"><p>朝6時までの更新を目標に、前夜23:17と午前0:17に実行を予約しています。合格した記事を1日最大3件追加します。開始の遅れや生成の失敗により、朝6時までに追加できない場合があります。</p><p>{{ edition.message }}<br>更新確認：{{ edition.checked }}</p><p>{{ edition.generated ? '説明・図・会話はAI生成です。事実は元記事でご確認ください。' : '初回の生成が通るまでは、2026/10/24の見本5件を表示します。' }}</p></div>
      </details>
      <p v-else-if="publicMode" class="trial-banner">🌱 まずは5件から、先行公開<br><small>2026/10/24時点の固定記事です。コメントはAIによる架空の会話。ニュースの自動更新は準備中です。</small></p>
    </template>
    <article v-for="(story, index) in stories" :id="`story-${index}`" :key="story.id" :data-index="index" class="story" :class="story.theme" :aria-labelledby="`title-${story.id}`">
      <div class="story-top">
        <span class="publisher-avatar" aria-hidden="true">{{ story.emoji }}</span>
        <div class="publisher"><strong>{{ story.source }}</strong><span class="topic">{{ story.category }} · {{ story.date }}</span></div>
        <span class="number">{{ String(index + 1).padStart(2, '0') }} / {{ countLabel }}</span>
      </div>
      <h2 :id="`title-${story.id}`">{{ story.title }}</h2>
      <p v-if="story.saved_snapshot" class="snapshot-note">🔖 保存時の内容 · 現在のフィード掲載外</p>
      <p class="lead">{{ story.lead }}</p>
      <StoryDiagram :story="story" />
      <div class="explanation">
        <p v-if="story.reviewNote" class="review-note">🔎 {{ story.reviewNote }}</p>
        <section><h3>🔎 何が変わった？</h3><p>{{ story.changed }}</p></section>
        <section class="example"><h3>💡 例えば、こんなこと</h3><p>{{ story.example }}</p></section>
        <section class="context"><h3>📌 知っておきたいこと</h3><p>{{ story.caution }}</p></section>
      </div>
      <a class="source-card" :href="story.url" target="_blank" rel="noopener noreferrer" :aria-label="'元記事を読む：' + story.title.replaceAll('\n', '') + '（新しいタブ）'">
        <span class="source-card-text"><strong>元記事を読む</strong><span>{{ story.source }} · {{ sourceDomain(story.url) }}</span></span>
        <span class="source-card-arrow" aria-hidden="true">↗</span>
      </a>
      <section v-if="!expandedComments.has(story.id)" class="comment-preview" :aria-label="`${story.category}の架空コメントの抜粋`">
        <div class="comment-preview-heading"><strong>💬 ちょっと気になる会話</strong><span>AIの架空コメント</span></div>
        <p class="teaser"><CommentAvatar :name="story.comments[0][0]" /><span>{{ story.teaser }}</span></p>
        <p class="second-teaser"><CommentAvatar :name="story.comments[story.id === 'sonnet' ? 3 : 1][0]" /><span>↳ {{ story.comments[story.id === 'sonnet' ? 3 : 1][1] }}</span></p>
      </section>
      <div class="actions">
        <button :id="'comments-toggle-' + story.id" class="read-comments" :aria-expanded="expandedComments.has(story.id)" :aria-controls="'comments-' + story.id" @click="toggleComments(story)"><ArticleActionIcon name="conversation" /><span class="action-label">{{ expandedComments.has(story.id) ? '閉じる' : '会話を読む' }}</span><span class="action-count">{{ story.comments.length }}</span></button>
        <button v-if="saveEnabled" class="save-story" :aria-pressed="isSaved(story)" :aria-label="(isSaved(story) ? '保存を解除：' : '保存する：') + story.title.replace('\n', '')" @click="toggleSave(story)"><ArticleActionIcon name="bookmark" /><span class="action-label">{{ isSaved(story) ? '保存済み' : '保存する' }}</span></button>
        <button v-if="publicMode" :id="'ask-' + story.id" class="ask-story" :aria-label="'AIに聞く：' + story.title.replaceAll('\n', '')" @click="openAsk(story, $event)"><ArticleActionIcon name="ai" /><span class="action-label">AIに聞く</span></button>
      </div>
      <section v-show="expandedComments.has(story.id)" :id="'comments-' + story.id" class="inline-conversation" :aria-label="`${story.category}の架空の会話`">
        <p class="fiction-notice">AIによる架空の会話 · 全{{ story.comments.length }}件<br>実在の投稿・利用者の声ではありません。</p>
        <ol class="comments">
          <li v-for="([name, text, reply, parent], commentIndex) in story.comments" :key="commentIndex" :class="{ reply }">
            <CommentAvatar :name="name" />
            <div class="comment-body"><span class="comment-name">{{ name }}</span><span v-if="reply" class="reply-marker"> ↳ {{ replyLabel(story, parent) }}</span><p>{{ text }}</p></div>
          </li>
        </ol>
        <div class="conversation-end-actions">
          <button @click="closeCommentsFromEnd(story)">会話を閉じる ↑</button>
          <button v-if="index < stories.length - 1" @click="go(index + 1)">次の記事へ ↓</button>
        </div>
      </section>
      <button v-if="index < stories.length - 1 && !expandedComments.has(story.id)" class="next" @click="go(index + 1)">次の発見へ ↓</button>
      <p v-if="index === stories.length - 1" class="end-note">☕ ひとまずここまで。どの会話が気になった？</p>
    </article>
    <section v-if="savedView && legacySaved.length" class="legacy-saved">
      <h2>以前の画面で保存した記事</h2>
      <p>説明・図・会話の保存がない記事は、元記事から読めます。</p>
      <div v-for="item in legacySaved" :key="item.url" class="legacy-saved-card">
        <a :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.article.title }} ↗</a>
        <span>{{ item.article.source }}</span>
        <button class="ask-story" :aria-label="'AIに聞く：' + item.article.title" @click="openAsk(item.article, $event)">💬 AIに聞く</button>
        <button :aria-label="'保存を解除：' + item.article.title" @click="emit('remove-legacy', item.article)">保存を解除</button>
      </div>
    </section>
    <footer v-if="!publicMode">ローカル試作 · {{ generatedMode ? '取得済みの実生成結果を表示・継続更新は未接続' : '自動収集・自動生成は未接続' }}<br><a href="./catchup-preview.html">最初の3件の見本へ</a><br><a href="./">通常のフィードへ戻る</a></footer>
    <footer v-if="publicMode">☕ AI Catchup Hub{{ edition ? ` · 記事追加：${edition.updated}` : ' · 2026/10/24版' }}<br>記事の事実・利用条件はリンク先でご確認ください。<br>コメントは実在する人の投稿ではありません。</footer>
  </main>
  <nav class="progress" aria-label="ニュースの位置"><button v-for="(story, index) in stories" :key="story.id" :aria-label="`${index + 1}件目：${story.category}`" :aria-current="active === index ? 'step' : undefined" @click="go(index)"><span></span></button></nav>
  <div class="toast" role="status">{{ notice }}</div>
  <AskAiDialog v-if="asking" :story="asking" v-model:context="askContext" :return-focus="askReturnFocus" @close="asking = null" />
</template>
