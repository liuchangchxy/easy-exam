import { onMounted, onUnmounted, ref, watch } from 'vue'
import { listEvents, appendEvents } from '../api/sync.js'

export function useSyncLoop(tokenRef, userRef) {
  let activeSyncRequestId = 0

  function getCurrentUser() {
    return typeof userRef === 'function' ? userRef() : (userRef?.value || userRef)
  }

  function getCurrentToken() {
    return typeof tokenRef === 'function' ? tokenRef() : (tokenRef?.value || tokenRef)
  }

  function getStorageKeyFor(uid) {
    return `easyexam_sync_cursor_${uid || 'anonymous'}`
  }

  const syncCursor = ref(localStorage.getItem(getStorageKeyFor(getCurrentUser()?.id)) || '')
  const isSyncing = ref(false)
  const lastSyncTime = ref(null)
  let timerId = null

  if (userRef) {
    watch(() => (typeof userRef === 'function' ? userRef() : userRef?.value), (newUser) => {
      // Invalidate any in-flight poll request initiated by previous user
      activeSyncRequestId++
      isSyncing.value = false
      const uid = newUser?.id || 'anonymous'
      syncCursor.value = localStorage.getItem(getStorageKeyFor(uid)) || ''
      if (newUser && newUser.id) {
        pollEvents()
      }
    })
  }

  async function pollEvents() {
    const user = getCurrentUser()
    const token = getCurrentToken()
    const reqUserId = user?.id || null
    if (!token || !reqUserId || isSyncing.value) return

    const requestId = ++activeSyncRequestId
    const storageKey = getStorageKeyFor(reqUserId)
    const cursor = localStorage.getItem(storageKey) || ''

    isSyncing.value = true
    try {
      const events = await listEvents(token, cursor)

      // Guard against race condition: check if user/token or active request changed while waiting for network
      const currentU = getCurrentUser()
      const currentT = getCurrentToken()
      if (requestId !== activeSyncRequestId || currentU?.id !== reqUserId || currentT !== token) {
        // Discard result: user switched accounts or logged out while in flight!
        return
      }

      if (Array.isArray(events) && events.length > 0) {
        const latest = events[events.length - 1]
        if (latest.created_at) {
          syncCursor.value = latest.created_at
          localStorage.setItem(storageKey, syncCursor.value)
        }
        lastSyncTime.value = new Date()
        window.dispatchEvent(new CustomEvent('easyexam:events-synced', {
          detail: {
            userId: reqUserId,
            events,
          },
        }))
      }
    } catch (_) {
      // Non-intrusive background sync
    } finally {
      if (requestId === activeSyncRequestId) {
        isSyncing.value = false
      }
    }
  }

  function handleFocus() {
    pollEvents()
  }

  function handleEmitSyncEvent(e) {
    const { eventType, aggregateType, aggregateId, payload } = e.detail || {}
    if (eventType && aggregateType && aggregateId) {
      emitSyncEvent(eventType, aggregateType, aggregateId, payload)
    }
  }

  onMounted(() => {
    pollEvents()
    timerId = setInterval(pollEvents, 30000)
    window.addEventListener('focus', handleFocus)
    window.addEventListener('online', handleFocus)
    window.addEventListener('easyexam:emit-sync-event', handleEmitSyncEvent)
  })

  onUnmounted(() => {
    if (timerId) clearInterval(timerId)
    window.removeEventListener('focus', handleFocus)
    window.removeEventListener('online', handleFocus)
    window.removeEventListener('easyexam:emit-sync-event', handleEmitSyncEvent)
  })

  async function emitSyncEvent(eventType, aggregateType, aggregateId, payload = {}) {
    const user = getCurrentUser()
    const token = getCurrentToken()
    const reqUserId = user?.id || null
    if (!token || !reqUserId) return
    const event = {
      id: typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `evt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      event_type: eventType,
      aggregate_type: aggregateType,
      aggregate_id: aggregateId,
      payload,
    }
    try {
      await appendEvents(token, [event])
      const currentU = getCurrentUser()
      if (currentU?.id === reqUserId) {
        await pollEvents()
      }
    } catch (e) {
      console.warn('Failed to append sync event:', e)
    }
  }

  return {
    syncCursor,
    isSyncing,
    lastSyncTime,
    pollEvents,
    emitSyncEvent,
  }
}
