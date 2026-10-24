<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import FeedView from './prototype/FeedView.vue'
import { trialStories } from './prototype/trialStories.js'
import feed from './daily-feed.json'
import { dailyStories, displayTime } from './dailyStories.js'
import { useSavedArticles } from './useSavedArticles.js'
import { savedReaderStories } from './readerSnapshots.js'

// Rendering tests reject invalid exported data before deployment.
const generated = dailyStories(feed)
const stories = generated.length ? generated : trialStories
const saved = useSavedArticles()
const savedView = ref(false)
const savedUrls = computed(() => saved.items.value.map(item => item.url))
const visibleStories = computed(() => savedView.value ? savedReaderStories(saved.items.value, stories) : stories)
const legacySaved = computed(() => saved.items.value.filter(item => !item.article.reader_story))
function readView() { savedView.value = window.location.hash === '#saved' }
function selectView(view) {
  savedView.value = view === 'saved'
  window.history.replaceState(null, '', savedView.value ? '#saved' : '#feed')
  window.scrollTo({ top:0, behavior:'instant' })
}
function toggleSave(story) {
  saved.bookmark({ url:story.url, title:story.title, source:story.source, reader_story:story })
}
onMounted(() => { readView(); window.addEventListener('hashchange', readView) })
onUnmounted(() => window.removeEventListener('hashchange', readView))
const messages = {
  waiting: '初回の自動更新を待っています。',
  ready: '新しい記事を追加しました。',
  no_new: '今回は追加できる新着記事がありませんでした。',
  budget_limit: '本日の送信上限に達しました。公開済みの記事を表示しています。',
  generation_paused: '生成の設定確認が必要なため、新しい生成を一時停止しています。',
  source_unavailable: '記事本文を取得できなかったため、公開済みの記事を表示しています。',
  invalid_outputs: '生成結果がチェックを通らなかったため、公開済みの記事を表示しています。',
  rate_limit: 'AIの利用上限に達したため、公開済みの記事を表示しています。',
  provider_error: 'AI生成に失敗したため、公開済みの記事を表示しています。',
}
const edition = {
  generated: generated.length > 0,
  updated: displayTime(feed.updated_at),
  checked: displayTime(feed.checked_at),
  message: messages[feed.status],
}
</script>
<template>
  <FeedView :stories="visibleStories" public-mode :edition="edition" save-enabled
    :saved-view="savedView" :saved-urls="savedUrls" :legacy-saved="legacySaved"
    :storage-warning="saved.warning.value"
    @change-view="selectView" @toggle-save="toggleSave" @remove-legacy="saved.bookmark" />
</template>
