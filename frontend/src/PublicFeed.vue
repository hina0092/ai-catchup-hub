<script setup>
import { computed, ref, nextTick, onMounted, onUnmounted } from 'vue'
import FeedView from './prototype/FeedView.vue'
import { trialStories } from './prototype/trialStories.js'
import feed from './daily-feed.json'
import { dailyStories, displayTime, additionSummary } from './dailyStories.js'
import { useSavedArticles } from './useSavedArticles.js'
import { savedReaderStories } from './readerSnapshots.js'
import { emptyFilters, filterStories, filterOptions } from './feedFilter.js'
import FeedFilters from './components/FeedFilters.vue'
import { useReadMarks } from './useReadMarks.js'
import { parseFeedRoute, resolveCard } from './feedRoute.js'
import { useOffline } from './useOffline.js'
import ArticleActionIcon from './components/ArticleActionIcon.vue'

// Rendering tests reject invalid exported data before deployment.
const generated = dailyStories(feed)
const stories = generated.length ? generated : trialStories
const saved = useSavedArticles()
const read = useReadMarks()
const offline = useOffline()
const undoRead = ref(null)
const undoButton = ref(null)
async function toggleRead(story) {
  const wasRead = read.urls.value.has(story.url)
  read.setRead(story.url, !wasRead)
  undoRead.value = { url: story.url, wasRead }
  await nextTick()
  if (!visibleStories.value.some(item => item.url === story.url) && !legacySaved.value.some(item => item.url === story.url)) undoButton.value?.focus()
}
async function dismissRead() {
  const story = visibleStories.value.find(story => story.url === undoRead.value?.url)
  undoRead.value = null
  await nextTick()
  const target = story ? document.getElementById(`read-${story.id}`) : document.getElementById('feed-content')
  target?.focus({ preventScroll: true })
}
async function restoreRead() {
  if (undoRead.value) read.setRead(undoRead.value.url, undoRead.value.wasRead)
  await nextTick()
  await dismissRead()
}
const savedView = ref(false)
const feedView = ref(null)
const routeNotice = ref('')
let routeSequence = 0
let lastRouteHash = null
const savedUrls = computed(() => saved.items.value.map(item => item.url))
const filtersByView = ref({ feed: emptyFilters(), saved: emptyFilters() })
const filters = computed(() => filtersByView.value[savedView.value ? 'saved' : 'feed'])
const baseStories = computed(() => savedView.value ? savedReaderStories(saved.items.value, stories) : stories)
const baseLegacy = computed(() => savedView.value ? saved.items.value.filter(item => !item.article.reader_story) : [])
const allSearchable = computed(() => [...baseStories.value, ...baseLegacy.value.map(item => item.article)])
const options = computed(() => filterOptions(allSearchable.value))
const visibleStories = computed(() => filterStories(baseStories.value, filters.value, read.urls.value))
const legacySaved = computed(() => {
  const urls = new Set(filterStories(baseLegacy.value.map(item => item.article), filters.value, read.urls.value).map(article => article.url))
  return baseLegacy.value.filter(item => urls.has(item.url))
})
function changeFilters(change) { Object.assign(filters.value, change) }
function clearFilters() { Object.assign(filters.value, emptyFilters()) }
async function readView(event) {
  if (event?.type === 'hashchange' && lastRouteHash === window.location.hash) return
  lastRouteHash = window.location.hash
  const route = parseFeedRoute(window.location.hash)
  if (!route) return
  const sequence = ++routeSequence
  routeNotice.value = ''
  if (route.id) {
    const target = resolveCard(route.id, stories, savedReaderStories(saved.items.value, stories))
    if (target) {
      savedView.value = target.view === 'saved'
      clearFilters()
      await nextTick()
      if (sequence === routeSequence) feedView.value?.navigateTo(target.story.id)
      return
    }
    routeNotice.value = window.navigator.onLine ? '現在の掲載記事と、このブラウザーの保存記事に見つかりません。' : 'オフラインで利用できる記事に見つかりません。接続後にもう一度お試しください。'
  } else if (route.invalid) routeNotice.value = '記事リンクの形式を確認してください。'
  savedView.value = route.view === 'saved'
  await nextTick()
  if (sequence === routeSequence && event?.type === 'popstate') window.scrollTo({ top: window.history.state?.feedScroll ?? 0, behavior: 'instant' })
}
function selectView(view) {
  routeSequence++
  routeNotice.value = ''
  window.history.replaceState({ ...window.history.state, feedScroll: window.scrollY }, '')
  savedView.value = view === 'saved'
  window.history.pushState(null, '', savedView.value ? '#saved' : '#feed')
  window.scrollTo({ top:0, behavior:'instant' })
}
function toggleSave(story) {
  saved.bookmark({ url:story.url, title:story.title, source:story.source, reader_story:story })
}
onMounted(() => { readView(); window.addEventListener('hashchange', readView); window.addEventListener('popstate', readView) })
onUnmounted(() => { window.removeEventListener('hashchange', readView); window.removeEventListener('popstate', readView) })
const messages = {
  waiting: '初回の自動更新を待っています。',
  ready: '',
  no_new: '今回は追加できる新着記事がありませんでした。',
  budget_limit: '本日の送信上限に達しました。公開済みの記事を表示しています。',
  generation_paused: '生成の設定確認が必要なため、新しい生成を一時停止しています。',
  source_unavailable: '記事本文を取得できなかったため、公開済みの記事を表示しています。',
  invalid_outputs: '生成結果がチェックを通らなかったため、公開済みの記事を表示しています。',
  rate_limit: 'AIの利用上限に達したため、公開済みの記事を表示しています。',
  provider_error: 'AI生成に失敗したため、公開済みの記事を表示しています。',
}
const edition = {
  count: stories.length,
  additions: additionSummary(feed),
  generated: generated.length > 0,
  updated: displayTime(feed.updated_at),
  checked: displayTime(feed.checked_at),
  message: messages[feed.status],
}
</script>
<template>
  <FeedView ref="feedView" :stories="visibleStories" public-mode :edition="edition" save-enabled share-enabled
    :saved-view="savedView" :saved-urls="savedUrls" :legacy-saved="legacySaved"
    :storage-warning="[saved.warning.value, read.warning.value].filter(Boolean).join(' ')" :read-urls="read.urls.value" read-enabled
    @toggle-read="toggleRead" @dismiss-feedback="undoRead = null"
    @change-view="selectView" @toggle-save="toggleSave" @remove-legacy="saved.bookmark">
    <template #search><FeedFilters :filters="filters" :options="options" :count="visibleStories.length + legacySaved.length" :total="allSearchable.length" @change="changeFilters" @clear="clearFilters"><label class="unread-filter"><input type="checkbox" :checked="filters.unreadOnly" @change="changeFilters({ unreadOnly: $event.target.checked })">未読だけ</label></FeedFilters></template>
    <template #offline-status><p v-if="offline.ready.value && !offline.offline.value" class="offline-ready">✓ オフラインの準備ができています</p></template>
    <template #filters>
      <p v-if="offline.offline.value" class="reader-message" role="status">オフラインで表示中 · この版の更新確認：{{ edition.checked }}<br>保存記事はこのブラウザー内の内容です。</p>
      <div v-if="offline.updateReady.value" class="update-notice" role="status"><span class="update-notice-label"><ArticleActionIcon name="refresh" />新しい更新があります</span><button @click="offline.applyUpdate">更新する</button></div>
      <p v-if="offline.failed.value" class="reader-message" role="status">オフライン用の更新を準備できませんでした。接続中は通常どおり読めます。</p>
      <p v-if="routeNotice" class="reader-message" role="status">{{ routeNotice }} <button @click="selectView('feed')">発見フィードへ</button></p>
    </template>
    <template v-if="undoRead" #feedback><div class="read-feedback"><ArticleActionIcon name="check" /><span class="read-feedback-label">{{ undoRead.wasRead ? '未読に戻しました' : '読了にしました' }}</span><button ref="undoButton" class="undo-read" @click="restoreRead">元に戻す</button><button class="dismiss-read" aria-label="通知を閉じる" @click="dismissRead"><span aria-hidden="true">×</span></button></div></template>
    <template v-if="allSearchable.length && !visibleStories.length && !legacySaved.length" #empty><section class="saved-empty"><h2>{{ filters.unreadOnly && !filters.query && !filters.source && !filters.category ? '全部読んだ！' : '条件に合う記事がありません' }}</h2><button @click="clearFilters">条件をクリア</button></section></template>
  </FeedView>
</template>
