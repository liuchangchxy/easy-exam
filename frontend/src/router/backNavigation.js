import { computed, ref } from 'vue'

// In-app navigation stack. The browser history is the source of truth for the
// actual back action; this stack only answers one question: has the user moved
// inside the app since this page loaded? If yes, "back" means history.back();
// if not (a deep link), the page falls back to a static destination.
const stack = ref([])

export function recordNavigation(to, from) {
  const target = to?.fullPath
  if (!target) return
  const s = stack.value
  // First navigation of the session (or after a full reload).
  if (!from || !from.matched || from.matched.length === 0) {
    stack.value = [target]
    return
  }
  // A browser/page back lands on the entry below the current one: pop instead
  // of pushing so the depth does not drift upwards over time.
  if (s.length > 1 && s[s.length - 2] === target) {
    s.pop()
    return
  }
  if (s[s.length - 1] === target) return
  s.push(target)
}

export function resetNavigationStack(fullPath = '') {
  stack.value = fullPath ? [fullPath] : []
}

export const navigationDepth = computed(() => stack.value.length)

export const canGoBack = computed(() => stack.value.length > 1)
