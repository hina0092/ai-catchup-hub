<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import AskAiDialog from '../components/AskAiDialog.vue'
import ArticleActionIcon from '../components/ArticleActionIcon.vue'
import StoryDiagram from '../components/StoryDiagram.vue'
import CommentAvatar from '../components/CommentAvatar.vue'
import TopicSticker from '../components/TopicSticker.vue'
import { topicIcon } from '../readerIcons.js'
import { buildShareData, shareArticle, copyText } from '../shareText.js'

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
  readEnabled: Boolean,
  shareEnabled: Boolean,
  readUrls: { type: Set, default: () => new Set() },
})
const emit = defineEmits(['toggle-save','change-view','remove-legacy','toggle-read','dismiss-feedback'])
const brandBase = `${import.meta.env.BASE_URL}brand/`
const { publicMode, generatedMode, trialMode, generatedError, homeUrl } = props
const stories = computed(() => props.stories)
const countLabel = computed(() => String(props.stories.length).padStart(2, '0'))

const activeId = ref(null)
const active = computed(() => Math.max(0, props.stories.findIndex(story => story.id === activeId.value)))
const expandedComments = ref(new Set())
const asking = ref(null), askContext = ref(''), askReturnFocus = ref(null)
const notice = ref('')
const sharing = ref(null)
const nativeShare = ref(false)
async function toggleShare(story) {
  sharing.value = sharing.value === story.id ? null : story.id
  await nextTick()
  if (sharing.value) document.getElementById(`copy-share-${story.id}`)?.focus({ preventScroll: true })
}
function closeShare(id, returnFocus = false) {
  sharing.value = null
  if (returnFocus) document.getElementById(`share-${id}`)?.focus({ preventScroll: true })
}
function outsideShare(event) {
  if (!event.target.closest?.('.share-action')) sharing.value = null
}
function leaveShare(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) sharing.value = null
}
function sourceDomain(url) { return new URL(url).hostname }
function replyLabel(story, parent) {
  return Number.isInteger(parent) && story.comments[parent] ? `${story.comments[parent][0]}へ` : '返信'
}
let observer, noticeTimer
function notify(message) {
  emit('dismiss-feedback')
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
async function toggleComments(story) {
  const next = new Set(expandedComments.value)
  if (next.has(story.id)) next.delete(story.id)
  else next.add(story.id)
  expandedComments.value = next
  await nextTick()
  if (next.has(story.id)) document.getElementById('comments-' + story.id)?.focus({ preventScroll: true })
}
async function closeCommentsFromEnd(story) {
  toggleComments(story)
  await nextTick()
  const trigger = document.getElementById('comments-toggle-' + story.id)
  trigger?.focus({ preventScroll: true })
  trigger?.scrollIntoView({ block: 'center', behavior: 'instant' })
}
function go(index) {
  navigateTo(props.stories[index]?.id)
}
function navigateTo(id) {
  if (!id) return
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  document.getElementById(`story-${id}`)?.scrollIntoView({ behavior: reduce ? 'instant' : 'smooth', block: 'start' })
  document.getElementById(`title-${id}`)?.focus({ preventScroll: true })
}
defineExpose({ navigateTo })
async function copyLink(story) {
  const data = buildShareData(story, window.location.href)
  notify(await copyText(data.url, window.navigator.clipboard) ? (story.saved_snapshot ? '元記事のリンクをコピーしました。' : '記事リンクをコピーしました。') : 'コピーできませんでした。ブラウザーの権限を確認してください。')
  closeShare(story.id, true)
}
async function share(story) {
  const result = await shareArticle(story, window.location.href, window.navigator)
  if (result !== 'cancelled') notify({ shared: '共有しました。', copied: '共有文をコピーしました。', failed: '共有できませんでした。リンクのコピーをお試しください。' }[result])
  closeShare(story.id, true)
}
function observeStories() {
  observer?.disconnect()
  document.querySelectorAll('[data-index]').forEach(el => observer?.observe(el))
}
watch(() => props.stories, async () => {
  if (!props.stories.some(story => story.id === activeId.value)) activeId.value = props.stories[0]?.id ?? null
  await nextTick()
  observeStories()
})
onMounted(() => {
  nativeShare.value = typeof window.navigator.share === 'function'
  document.addEventListener('pointerdown', outsideShare)
  observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
    if (visible.length) activeId.value = visible[0].target.dataset.storyId
  }, { rootMargin: '-15% 0px -45% 0px', threshold: 0 })
  observeStories()
})
onUnmounted(() => { observer?.disconnect(); clearTimeout(noticeTimer); document.removeEventListener('pointerdown', outsideShare); document.body.style.overflow = '' })
</script>

<template>
  <div class="desktop-sky" aria-hidden="true"><span class="sky-star">✦</span><span class="sky-star">✧</span><span class="sky-star">✦</span></div>
  <a :href="stories.length ? `#story-${stories[0].id}` : '#feed-content'" class="skip-link">ニュースへ進む</a>
  <div class="reader-toolbar">
  <header class="app-header" :class="{ 'reader-header':saveEnabled }">
    <a class="wordmark" :href="homeUrl" aria-label="Techmin Feed ホーム">
      <img :src="brandBase + 'icon-48.png?v=2'" width="48" height="48" alt="">
      <div class="brand-type"><h1 class="brand-name">Tech<span class="brand-mint">min</span> Feed</h1><span class="brand-tagline">YOUR DAILY TECH FIX</span></div>
    </a>
    <slot name="search" />
    <span v-if="!saveEnabled" class="preview-badge">{{ publicMode ? '先行公開' : 'LOCAL PREVIEW' }}</span>
  </header>
  <nav v-if="saveEnabled" class="reader-tabs" aria-label="記事の表示">
    <button :aria-pressed="!savedView" @click="changeView('feed')"><img class="nav-art" :src="brandBase + 'discover-pc.svg'" width="38" height="38" alt=""><span class="view-label">発見</span></button>
    <button :aria-pressed="savedView" @click="changeView('saved')"><img class="nav-art" :src="brandBase + 'saved-folder.svg'" width="38" height="38" alt=""><span class="view-label">保存済み <span class="view-count">{{ savedUrls.length }}</span></span></button>
  </nav>
  </div>
  <aside class="desktop-note">
    <div class="brand-window-title" aria-hidden="true"><span>TECHMIN / little discoveries</span><span>− □ ×</span></div>
    <img class="brand-characters" :src="brandBase + 'mint-loppy-game.jpg'" alt="片耳がミント色の猫・ミントと、青いフロッピーディスク・ロッピー" width="1024" height="558">
    <p class="eyebrow">YOUR DAILY TECH FIX</p>
    <p v-if="savedView">気になった記事を、<br>あとからもう一度。</p>
    <p v-else>AI・テクノロジーの話題を、<br>図とみんなの会話でひとつずつ。</p>
    <div v-if="!publicMode" class="sample-label">あなた向けの画面試作</div>
    <p v-if="savedView" class="fine">保存 {{ savedUrls.length }}件<br>このブラウザー内だけに保存します。<br>別端末への同期はありません。</p>
    <p v-if="generatedMode" class="trial-status">初回の実生成結果をそのまま表示。<br>関西弁・事実チェックの修正版ではありません。</p>
    <p v-if="trialMode && !publicMode" class="trial-status">このチャットで生成・編集した見本です。<br>Gemini実生成へ切り替えて見比べられます。</p>
    <nav aria-label="ニュースを選ぶ" class="desktop-nav">
      <div class="file-list-heading" aria-hidden="true"><span><ArticleActionIcon name="folder" />記事フォルダー</span><span>{{ countLabel }}件</span></div>
      <button v-for="(story, index) in stories" :key="story.id" :aria-label="`${index + 1}件目：${story.title}`" :title="story.title.replaceAll('\n', '')" :aria-current="active === index ? 'step' : undefined" @click="go(index)"><span class="topic-icon"><TopicSticker :name="topicIcon(story)" /></span><span class="nav-story"><strong>{{ story.title }}</strong><span>{{ story.category }}</span></span><span>{{ String(index + 1).padStart(2, '0') }}</span></button>
    </nav>
    <p v-if="!savedView" class="fine">実記事{{ stories.length }}件・{{ generatedMode ? 'Gemini実生成（修正前）' : (edition?.generated ? 'AIによる説明・図・会話' : publicMode ? '編集済みの見本' : '固定サンプル') }}<br>コメントはすべてAIによる架空の会話<br>{{ edition ? `記事追加：${edition.updated}` : '確認日：2026/10/24' }}</p>
    <a v-if="!publicMode" href="./" class="original-link">通常のフィードを見る ↗</a>
    <a v-if="!publicMode" :href="trialMode ? './catchup-preview.html' : './catchup-preview.html?trial=1'" class="original-link">{{ trialMode ? '最初の3件の見本へ ↗' : '実記事5件のお試しへ ↗' }}</a>
  </aside>
  <main id="feed-content" class="feed" tabindex="-1" :aria-label="`実記事${stories.length}件のフィード`">
    <div class="feed-intro"><span class="icon-label"><ArticleActionIcon :name="savedView ? 'bookmark' : 'ai'" />{{ savedView ? 'あなたの保存一覧' : 'あなたの発見フィード' }}</span><span class="feed-intro-side"><span class="feed-direction">{{ savedView ? '保存した順に' : 'スクロールで次へ ↓' }}</span><img class="feed-mascots" :src="brandBase + 'mint-loppy-game.jpg'" width="74" height="40" alt="ミントとロッピー"></span></div>
    <p v-if="storageWarning" class="storage-warning" role="alert">{{ storageWarning }}</p>
    <p v-if="savedView" class="saved-help">このブラウザー内だけに保存します。端末間の同期はありません。ブラウザーの保存データを消すと、記事の保存も失われます。</p>
    <slot name="filters" />
    <slot name="empty">
    <section v-if="savedView && !stories.length && !legacySaved.length" class="saved-empty">
      <ArticleActionIcon name="bookmark" /><h2>保存した記事はまだありません</h2>
      <p>気になる記事の「保存する」を押すと、ここから読み返せます。</p>
      <button @click="changeView('feed')">発見フィードへ</button>
    </section>
    </slot>
    <nav v-if="!publicMode" class="comparison-nav" aria-label="同じ画面で内容を比較">
      <a href="./catchup-preview.html?trial=1" :aria-current="trialMode ? 'page' : undefined">見本の5件</a>
      <a href="./catchup-preview.html?gemini=1" :aria-current="generatedMode ? 'page' : undefined">Geminiの実生成</a>
    </nav>
    <p v-if="generatedMode" class="trial-banner generated-banner">Geminiの初回生成 · 内容は確認中<br><small>2026/10/24の結果を未修正で表示。関西弁・事実チェックの修正版は未生成です。</small></p>
    <p v-if="generatedError" class="trial-banner" role="alert">生成結果を表示できませんでした。見本へ切り替えて確認してください。</p>
    <p v-if="trialMode && !publicMode" class="trial-banner">実記事5件の見本 · このチャットで生成<br><small>このページの内容はGeminiの出力ではありません</small></p>
    <template v-if="!savedView">
      <details v-if="publicMode && edition" class="edition-status">
        <summary><span class="icon-label"><ArticleActionIcon name="refresh" />{{ edition.additions?.label || (edition.generated ? `記事追加：${edition.updated}` : `見本${edition.count ?? stories.length}件を表示中`) }}</span><span class="edition-detail-label">更新の詳細</span></summary>
        <div class="edition-details"><p>毎朝の更新を目指して、1日最大3件を追加します。</p><p v-if="edition.additions && !edition.additions.complete">以前の追加記録が揃っていないため、確認できた件数を表示しています。</p><p v-if="edition.message">{{ edition.message }}</p><p>更新確認：{{ edition.checked }}</p><slot name="offline-status" /><p v-if="!edition.generated">初回の生成が通るまでは、2026/10/24の見本5件を表示します。</p></div>
      </details>
      <p v-else-if="publicMode" class="trial-banner">まずは5件から、先行公開<br><small>2026/10/24時点の固定記事です。コメントはAIによる架空の会話。ニュースの自動更新は準備中です。</small></p>
    </template>
    <article v-for="(story, index) in stories" :id="`story-${story.id}`" :key="story.id" :data-index="index" :data-story-id="story.id" class="story" :class="story.theme" :aria-labelledby="`title-${story.id}`">
      <div class="story-top">
        <span class="publisher-avatar" aria-hidden="true"><TopicSticker :name="topicIcon(story)" /></span>
        <div class="publisher"><strong>{{ story.source }}</strong><span class="topic"><span class="topic-tag">{{ story.category }}</span><span class="topic-date">{{ story.date }}</span></span></div>
        <span class="number">{{ String(index + 1).padStart(2, '0') }} / {{ countLabel }}</span>
      </div>
      <h2 :id="`title-${story.id}`" tabindex="-1">{{ story.title }}</h2>
      <p v-if="readUrls.has(story.url)" class="read-badge">✓ 読んだ</p>
      <p v-if="story.saved_snapshot" class="snapshot-note icon-label"><ArticleActionIcon name="bookmark" />保存時の内容 · 現在のフィード掲載外</p>
      <p class="lead">{{ story.lead }}</p>
      <StoryDiagram :story="story" />
      <div class="explanation">
        <p v-if="story.reviewNote" class="review-note"><ArticleActionIcon name="search" /> {{ story.reviewNote }}</p>
        <section><h3 class="icon-label"><ArticleActionIcon name="search" />ここがポイント</h3><p>{{ story.changed }}</p></section>
        <section class="example"><h3 class="icon-label"><ArticleActionIcon name="idea" />例えば、こんなこと</h3><p>{{ story.example }}</p></section>
        <section class="context"><h3 class="icon-label"><ArticleActionIcon name="info" />知っておきたいこと</h3><p>{{ story.caution }}</p></section>
      </div>
      <a class="source-card" :href="story.url" target="_blank" rel="noopener noreferrer" :aria-label="'元記事を読む：' + story.title.replaceAll('\n', '') + '（新しいタブ）'">
        <span class="source-card-icon" aria-hidden="true"><ArticleActionIcon name="article" /></span>
        <span class="source-card-text"><strong>元記事を読む <span class="source-stamp" aria-hidden="true">SOURCE</span></strong><span>{{ story.source }} · {{ sourceDomain(story.url) }}</span></span>
        <span class="source-card-arrow" aria-hidden="true"><ArticleActionIcon name="external" /></span>
      </a>
      <section v-if="!expandedComments.has(story.id)" :id="'comments-toggle-' + story.id" class="comment-preview" role="button" tabindex="0" aria-expanded="false" :aria-controls="'comments-' + story.id" :aria-label="`全${story.comments.length}件の架空の会話を開く`" @click="toggleComments(story)" @keydown.enter.prevent="toggleComments(story)" @keydown.space.prevent="toggleComments(story)">
        <div class="comment-preview-heading"><strong class="icon-label"><span class="preview-dots" aria-hidden="true"><i></i><i></i><i></i></span>ちょっと気になる会話</strong><span>AIの架空コメント</span></div>
        <p class="teaser"><CommentAvatar :name="story.comments[0][0]" /><span class="preview-bubble"><span class="preview-speaker">{{ story.comments[0][0] }}</span><span class="preview-line">{{ story.teaser }}</span></span></p>
        <p class="second-teaser"><CommentAvatar :name="story.comments[story.id === 'sonnet' ? 3 : 1][0]" /><span class="preview-bubble"><span class="preview-speaker">↳ {{ story.comments[story.id === 'sonnet' ? 3 : 1][0] }}</span><span class="preview-line">{{ story.comments[story.id === 'sonnet' ? 3 : 1][1] }}</span></span></p>
        <span class="conversation-open-hint"><span>全{{ story.comments.length }}件の会話を開く</span><svg class="conversation-open-arrow" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m3 4.5 3 3 3-3" /></svg></span>
      </section>
      <section v-show="expandedComments.has(story.id)" :id="'comments-' + story.id" class="inline-conversation" tabindex="-1" :aria-label="`${story.category}の架空の会話`">
        <div class="conversation-title"><strong class="icon-label"><span class="preview-dots" aria-hidden="true"><i></i><i></i><i></i></span>会話ルーム</strong><span class="fiction-notice">AIの架空会話 · 全{{ story.comments.length }}件</span></div>
        <ol class="comments">
          <li v-for="([name, text, reply, parent], commentIndex) in story.comments" :key="commentIndex" :class="{ reply }">
            <CommentAvatar :name="name" />
            <div class="comment-body preview-bubble"><div class="comment-meta"><span class="comment-name">{{ name }}</span><span v-if="reply" class="reply-marker">↳ {{ replyLabel(story, parent) }}</span></div><p>{{ text }}</p></div>
          </li>
        </ol>
        <div class="conversation-end-actions">
          <button @click="closeCommentsFromEnd(story)">会話を閉じる ↑</button>
          <button v-if="index < stories.length - 1" @click="go(index + 1)">次の記事へ ↓</button>
        </div>
      </section>
      <div class="actions">
        <button v-if="readEnabled" :id="`read-${story.id}`" :aria-pressed="readUrls.has(story.url)" @click="emit('toggle-read', story)"><ArticleActionIcon name="check" /><span class="action-label">{{ readUrls.has(story.url) ? '未読に戻す' : '読んだ' }}</span></button>
        <button v-if="saveEnabled" class="save-story" :aria-pressed="isSaved(story)" :aria-label="(isSaved(story) ? '保存を解除：' : '保存する：') + story.title.replace('\n', '')" @click="toggleSave(story)"><ArticleActionIcon name="bookmark" /><span class="action-label">{{ isSaved(story) ? '保存済み' : '保存する' }}</span></button>
        <button v-if="publicMode" :id="'ask-' + story.id" class="ask-story" :aria-label="'AIに聞く：' + story.title.replaceAll('\n', '')" @click="openAsk(story, $event)"><ArticleActionIcon name="ai" /><span class="action-label">AIに聞く</span></button>
        <div v-if="shareEnabled" class="share-action" @keydown.esc.stop.prevent="closeShare(story.id, true)" @focusout="leaveShare">
          <button :id="`share-${story.id}`" :aria-expanded="sharing === story.id" :aria-controls="`share-options-${story.id}`" @click="toggleShare(story)"><ArticleActionIcon name="external" /><span class="action-label">シェア</span></button>
          <div v-if="sharing === story.id" :id="`share-options-${story.id}`" class="share-options" role="group" aria-label="この記事をシェア">
            <button :id="`copy-share-${story.id}`" @click="copyLink(story)"><ArticleActionIcon name="copy" />リンクをコピー</button>
            <button @click="share(story)"><ArticleActionIcon name="external" />{{ nativeShare ? 'ほかのアプリで共有' : '共有文をコピー' }}</button>
          </div>
        </div>
      </div>
      <p v-if="index === stories.length - 1" class="end-note">ひとまずここまで。どの会話が気になった？</p>
    </article>
    <section v-if="savedView && legacySaved.length" class="legacy-saved">
      <h2>以前の画面で保存した記事</h2>
      <p>説明・図・会話の保存がない記事は、元記事から読めます。</p>
      <div v-for="item in legacySaved" :key="item.url" class="legacy-saved-card">
        <a :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.article.title }} ↗</a>
        <span>{{ item.article.source }}</span>
        <button v-if="readEnabled" :aria-pressed="readUrls.has(item.url)" @click="emit('toggle-read', item.article)">{{ readUrls.has(item.url) ? '未読に戻す' : '読んだ' }}</button>
        <button class="ask-story icon-label" :aria-label="'AIに聞く：' + item.article.title" @click="openAsk(item.article, $event)"><ArticleActionIcon name="ai" />AIに聞く</button>
        <button :aria-label="'保存を解除：' + item.article.title" @click="emit('remove-legacy', item.article)">保存を解除</button>
      </div>
    </section>
    <footer v-if="!publicMode">ローカル試作 · {{ generatedMode ? '取得済みの実生成結果を表示・継続更新は未接続' : '自動収集・自動生成は未接続' }}<br><a href="./catchup-preview.html">最初の3件の見本へ</a><br><a href="./">通常のフィードへ戻る</a></footer>
    <footer v-if="publicMode"><slot v-if="savedView" name="offline-status" />Techmin Feed{{ edition ? ` · 記事追加：${edition.updated}` : ' · 2026/10/24版' }}<br>記事の事実・利用条件はリンク先でご確認ください。<br>コメントは実在する人の投稿ではありません。</footer>
  </main>
  <nav class="progress" aria-label="ニュースの位置"><button v-for="(story, index) in stories" :key="story.id" :aria-label="`${index + 1}件目：${story.category}`" :aria-current="active === index ? 'step' : undefined" @click="go(index)"><span></span></button></nav>
  <div class="toast" :class="{ 'toast-actionable': !!$slots.feedback }" role="status"><slot name="feedback">{{ notice }}</slot></div>
  <AskAiDialog v-if="asking" :story="asking" v-model:context="askContext" :return-focus="askReturnFocus" @close="asking = null" />
</template>
