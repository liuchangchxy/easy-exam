import { reactive } from 'vue'

/**
 * One transient-success channel for the app.
 *
 * Entries are queued, not stacked: only the head of the queue is visible, and
 * it dismisses itself after ~4s before the next one appears. Persistent state
 * (a failed load, a retry banner) still belongs in the view's inline notice.
 */
const DEFAULT_MS = 4000

const state = reactive({ items: [] })

let seq = 0
let timer = null

function clearTimer() {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

function schedule() {
  clearTimer()
  const head = state.items[0]
  if (!head) return
  timer = setTimeout(() => {
    dismissToast(head.id)
  }, head.duration)
}

/**
 * @param {string} message already-localized copy
 * @param {'ok'|'bad'} [kind]
 * @param {{ duration?: number }} [options]
 */
export function pushToast(message, kind = 'ok', options = {}) {
  if (!message) return null
  const entry = {
    id: ++seq,
    message: String(message),
    kind: kind === 'bad' ? 'bad' : 'ok',
    duration: Number(options.duration) > 0 ? Number(options.duration) : DEFAULT_MS,
  }
  state.items.push(entry)
  if (state.items.length === 1) schedule()
  return entry.id
}

export function dismissToast(id) {
  const index = state.items.findIndex(item => item.id === id)
  if (index === -1) return
  state.items.splice(index, 1)
  schedule()
}

export function clearToasts() {
  clearTimer()
  state.items.splice(0, state.items.length)
}

export function useToast() {
  return {
    toasts: state.items,
    success: message => pushToast(message, 'ok'),
    error: message => pushToast(message, 'bad'),
    dismiss: dismissToast,
    clear: clearToasts,
  }
}

export default useToast
