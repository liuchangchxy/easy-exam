import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'

// Mock global browser objects for node testing
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (key) => store.get(key) || null,
    setItem: (key, val) => store.set(key, String(val)),
    removeItem: (key) => store.delete(key),
    clear: () => store.clear(),
  }
}

if (typeof globalThis.window === 'undefined') {
  const listeners = new Map()
  globalThis.window = {
    addEventListener: (type, fn) => {
      if (!listeners.has(type)) listeners.set(type, [])
      listeners.get(type).push(fn)
    },
    removeEventListener: (type, fn) => {
      const arr = listeners.get(type) || []
      const idx = arr.indexOf(fn)
      if (idx !== -1) arr.splice(idx, 1)
    },
    dispatchEvent: (ev) => {
      const arr = listeners.get(ev.type) || []
      for (const fn of arr) fn(ev)
      return true
    },
  }
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, init = {}) {
      this.type = type
      this.detail = init.detail
    }
  }
}

import { useSyncLoop } from '../src/composables/useSyncLoop.js'

test('useSyncLoop isolates storage cursor by userId', () => {
  localStorage.clear()
  const token = ref('tok_alice')
  const user = ref({ id: 'user_alice' })
  const sync = useSyncLoop(token, user)
  assert.equal(sync.syncCursor.value, '')

  // Simulate updating alice cursor
  localStorage.setItem('easyexam_sync_cursor_user_alice', '2026-09-26T12:00:00Z')
  user.value = { id: 'user_alice' }
  assert.equal(localStorage.getItem('easyexam_sync_cursor_user_alice'), '2026-09-26T12:00:00Z')

  // Switch to Bob: Bob should have empty cursor, Alice should remain intact
  user.value = { id: 'user_bob' }
  token.value = 'tok_bob'
  assert.equal(localStorage.getItem('easyexam_sync_cursor_user_bob'), null)
  assert.equal(localStorage.getItem('easyexam_sync_cursor_user_alice'), '2026-09-26T12:00:00Z')
})

test('useSyncLoop discards in-flight sync response if user switched accounts', async () => {
  localStorage.clear()
  const dispatched = []
  const listener = (e) => dispatched.push(e.detail)
  window.addEventListener('easyexam:events-synced', listener)

  let resolveAlice
  const aliceDeferredPromise = new Promise((resolve) => {
    resolveAlice = resolve
  })

  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, opts) => {
    const auth = opts?.headers?.Authorization || ''
    if (auth.includes('tok_alice')) {
      return aliceDeferredPromise
    }
    return {
      ok: true,
      status: 200,
      json: async () => [],
    }
  }

  try {
    const token = ref('tok_alice')
    const user = ref({ id: 'user_alice' })
    const sync = useSyncLoop(token, user)

    // 1. Initiate polling while Alice is active: this triggers fetch which is suspended
    const pollPromise = sync.pollEvents()
    assert.equal(sync.isSyncing.value, true, 'Alice sync request should be actively in-flight')

    // 2. While Alice request is suspended in flight, user switches to Bob
    user.value = { id: 'user_bob' }
    token.value = 'tok_bob'

    // 3. Alice's delayed network response finally arrives with Alice's private data
    resolveAlice({
      ok: true,
      status: 200,
      json: async () => [
        {
          id: 'evt-alice-secret-1',
          aggregate_type: 'BANK',
          aggregate_id: 'bank-alice-secret',
          created_at: '2026-09-26T15:30:00Z',
        },
      ],
    })

    await pollPromise
    await new Promise((r) => setTimeout(r, 20))

    // 4. Verify Bob's storage cursor was NEVER written or updated with Alice's event timestamp
    assert.equal(localStorage.getItem('easyexam_sync_cursor_user_bob'), null)

    // 5. Verify Alice's cursor was not incorrectly committed after being abandoned
    assert.equal(localStorage.getItem('easyexam_sync_cursor_user_alice'), null)

    // 6. Verify NO sync event was dispatched to the window with Alice's payload
    const leakedToBob = dispatched.filter((d) => d.userId === 'user_bob' || d.events.some((ev) => ev.id === 'evt-alice-secret-1'))
    assert.equal(leakedToBob.length, 0, 'Alice in-flight event must be completely discarded upon user switch')
  } finally {
    globalThis.fetch = originalFetch
    window.removeEventListener('easyexam:events-synced', listener)
  }
})
