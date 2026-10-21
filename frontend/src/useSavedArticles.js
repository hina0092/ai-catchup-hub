import { ref, onMounted, onUnmounted } from 'vue'
import { createSavedRepository, STORAGE_KEY } from './savedArticles.js'
export function useSavedArticles() {
  const items=ref([]),warning=ref(''),notice=ref('')
  const repository=createSavedRepository(()=>window.localStorage)
  function apply(state) {items.value=state.items;warning.value=state.warning}
  function refresh(event) {if(!event||event.key===STORAGE_KEY||event.key===null) apply(repository.load())}
  onMounted(()=>{refresh();window.addEventListener('storage',refresh)})
  onUnmounted(()=>window.removeEventListener('storage',refresh))
  function labels(article) {return items.value.find(s=>s.url===article.url)?.labels||[]}
  function toggle(article,kind) {
    const had=labels(article).includes(kind)
    apply(repository.toggle(article,kind))
    notice.value=warning.value?'保存状態を確認してください。':had?'保存区分を解除しました。':'このブラウザーに保存しました。'
  }
  return {items,warning,notice,labels,toggle}
}
