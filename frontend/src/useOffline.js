import { ref, onMounted, onUnmounted } from 'vue'

export function useOffline() {
  const offline = ref(false), ready = ref(false), updateReady = ref(false), failed = ref(false)
  let registration, stopped = false, reloading = false
  const cleanups = []
  function listen(target, event, listener) {
    target.addEventListener(event, listener)
    cleanups.push(() => target.removeEventListener(event, listener))
  }
  function connection() { offline.value = !window.navigator.onLine }
  function inspectWorker(worker) {
    if (!worker) return
    function stateChanged() {
      if (stopped) return
      if (worker.state === 'installed') updateReady.value = Boolean(window.navigator.serviceWorker.controller)
      if (worker.state === 'activated') ready.value = true
      if (worker.state === 'redundant' && !registration?.active) failed.value = true
    }
    listen(worker, 'statechange', stateChanged)
    stateChanged()
  }
  function refresh() {
    if (document.visibilityState === 'visible' && window.navigator.onLine) registration?.update().catch(() => {})
  }
  onMounted(async () => {
    connection()
    listen(window, 'online', connection)
    listen(window, 'offline', connection)
    if (!import.meta.env.PROD || !('serviceWorker' in window.navigator)) return
    const serviceWorker = window.navigator.serviceWorker
    const hadController = Boolean(serviceWorker.controller)
    listen(serviceWorker, 'controllerchange', () => {
      ready.value = true
      // Initial installation needs no reload. An accepted or naturally activated update does.
      if (hadController && !reloading) { reloading = true; window.location.reload() }
    })
    try {
      registration = await serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`, { updateViaCache: 'none' })
      if (stopped) return
      ready.value = registration.active?.state === 'activated'
      updateReady.value = Boolean(registration.waiting && serviceWorker.controller)
      inspectWorker(registration.installing)
      listen(registration, 'updatefound', () => inspectWorker(registration.installing))
      listen(document, 'visibilitychange', refresh)
      await registration.update()
    } catch { if (!stopped) failed.value = true }
  })
  onUnmounted(() => { stopped = true; cleanups.forEach(cleanup => cleanup()) })
  function applyUpdate() { registration?.waiting?.postMessage({ type: 'ACTIVATE_UPDATE' }) }
  return { offline, ready, updateReady, failed, applyUpdate }
}
