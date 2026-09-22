import { ref } from 'vue'

/**
 * Auto-draft storage composable using localStorage and 5-second debounced backend sync.
 *
 * Keys format: fnexam_draft_{sessionId}
 *
 * @param {string} sessionId
 * @param {string} [apiBase='']
 */
export function useDraftStorage(sessionId, apiBase = '') {
  const draftKey = `fnexam_draft_${sessionId}`
  const syncStatus = ref('idle') // 'idle' | 'pending' | 'saving' | 'synced' | 'error'
  let syncTimer = null
  let pendingData = null

  /**
   * Save draft to localStorage immediately (0ms loss prevention)
   */
  function saveLocal(data) {
    if (!sessionId) return null
    try {
      const existing = loadLocal() || {}
      const merged = {
        ...existing,
        ...data,
        updatedAt: Date.now()
      }
      localStorage.setItem(draftKey, JSON.stringify(merged))
      return merged
    } catch (err) {
      console.warn('localStorage draft save failed:', err)
      return null
    }
  }

  /**
   * Load draft from localStorage
   */
  function loadLocal() {
    if (!sessionId) return null
    try {
      const val = localStorage.getItem(draftKey)
      return val ? JSON.parse(val) : null
    } catch (err) {
      console.warn('localStorage draft read failed:', err)
      return null
    }
  }

  /**
   * Clear draft from localStorage
   */
  function clearLocal() {
    if (!sessionId) return
    try {
      localStorage.removeItem(draftKey)
    } catch (err) {
      console.warn('localStorage draft clear failed:', err)
    }
  }

  /**
   * Perform backend sync to /api/sessions/{sessionId}/sync
   */
  async function flushSync() {
    if (syncTimer) {
      clearTimeout(syncTimer)
      syncTimer = null
    }
    if (!sessionId || !pendingData) return

    const payload = { ...pendingData }
    pendingData = null
    syncStatus.value = 'saving'

    try {
      const res = await fetch(`${apiBase}/api/sessions/${sessionId}/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        syncStatus.value = 'synced'
      } else {
        syncStatus.value = 'error'
      }
    } catch (err) {
      console.warn('Remote draft sync error (will retry next turn):', err)
      syncStatus.value = 'error'
    }
  }

  /**
   * Queue sync with 5-second debounce (or immediate on question jump / finish)
   */
  function queueSync(data, immediate = false) {
    // 1. Immediately save to localStorage
    saveLocal(data)

    // 2. Prepare payload for remote sync
    pendingData = {
      ...(pendingData || {}),
      ...data
    }

    if (immediate) {
      flushSync()
    } else {
      syncStatus.value = 'pending'
      if (syncTimer) clearTimeout(syncTimer)
      syncTimer = setTimeout(() => {
        flushSync()
      }, 5000)
    }
  }

  return {
    draftKey,
    syncStatus,
    saveLocal,
    loadLocal,
    clearLocal,
    flushSync,
    queueSync
  }
}
