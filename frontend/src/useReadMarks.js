import { ref, computed, onMounted, onUnmounted } from 'vue'
import { createReadRepository, READ_STORAGE_KEY } from './readMarks.js'
export function useReadMarks() {
  const items = ref([]), warning = ref('')
  const repository = createReadRepository(() => window.localStorage)
  const urls = computed(() => new Set(items.value.map(item => item.url)))
  function apply(state) { items.value = state.items; warning.value = state.warning }
  function refresh(event) { if (!event || event.key === READ_STORAGE_KEY || event.key === null) apply(repository.load()) }
  onMounted(() => { refresh(); window.addEventListener('storage', refresh) })
  onUnmounted(() => window.removeEventListener('storage', refresh))
  function setRead(url, read) { apply(repository.setRead(url, read)) }
  return { urls, warning, setRead }
}
