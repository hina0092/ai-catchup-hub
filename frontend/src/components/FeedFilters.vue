<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import ArticleActionIcon from './ArticleActionIcon.vue'
const props = defineProps({ filters: Object, options: Object, count: Number, total: Number })
const emit = defineEmits(['change', 'clear'])
const expanded = ref(false)
const opened = ref(false)
const input = ref(null), trigger = ref(null), root = ref(null)
const active = computed(() => Boolean(props.filters.query || props.filters.source || props.filters.category || props.filters.unreadOnly))
async function openSearch() {
  opened.value = !opened.value
  if (opened.value) { await nextTick(); input.value?.focus() }
}
function closeSearch() {
  expanded.value = false
  if (opened.value) { opened.value = false; trigger.value?.focus() }
}
function outside(event) {
  if (!root.value?.contains(event.target)) { opened.value = false; expanded.value = false }
}
onMounted(() => document.addEventListener('pointerdown', outside))
onUnmounted(() => document.removeEventListener('pointerdown', outside))
</script>

<template>
  <section ref="root" class="feed-filters" aria-label="記事を探す" @keydown.esc.stop.prevent="closeSearch">
    <button ref="trigger" class="search-open" aria-label="記事を検索" :aria-expanded="opened" aria-controls="feed-search-panel" @click="openSearch"><ArticleActionIcon name="search" /><span v-if="active" class="search-active-dot" aria-label="検索条件あり" /></button>
    <div id="feed-search-panel" class="search-panel" :class="{ 'is-open': opened }">
      <div class="search-shell">
        <ArticleActionIcon name="search" />
        <label class="search-label"><span class="filter-search-title">記事を探す</span><input ref="input" type="search" :value="filters.query" placeholder="キーワードで記事を検索" @input="emit('change', { query: $event.target.value })"></label>
        <button class="filter-toggle" :class="{ 'is-active': expanded || filters.source || filters.category || filters.unreadOnly }" aria-label="絞り込み" :aria-expanded="expanded" aria-controls="feed-filter-fields" @click="expanded = !expanded"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M4 7h9m4 0h3M4 17h3m4 0h9" /><circle cx="15" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></svg></button>
      </div>
      <div v-if="expanded || active" class="search-extras">
        <div v-if="expanded" id="feed-filter-fields" class="filter-fields">
          <label>出典<select :value="filters.source" @change="emit('change', { source: $event.target.value })"><option value="">すべて</option><option v-for="source in options.sources" :key="source">{{ source }}</option></select></label>
          <label>カテゴリ<select :value="filters.category" @change="emit('change', { category: $event.target.value })"><option value="">すべて</option><option v-for="category in options.categories" :key="category">{{ category }}</option></select></label>
          <slot />
        </div>
        <div v-if="active" class="filter-result"><span role="status">{{ total }}件中 {{ count }}件</span><button @click="emit('clear')">条件をクリア</button></div>
      </div>
    </div>
  </section>
</template>
