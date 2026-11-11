import { ref, unref } from 'vue'

/**
 * Reusable "discard unsaved changes?" guard for dialogs and editors.
 *
 * The composable owns the confirmation flow only — the caller renders the
 * prompt (usually an AppDialog) and binds it to `discardPromptOpen`. Callers
 * keep full ownership of their own close path:
 *
 *   const guard = useDirtyGuard(() => isDirty.value, () => emit('close'))
 *   // every close trigger routes through the guard
 *   function handleClose() { guard.confirmDiscard() }
 *
 * @param {(() => boolean) | import('vue').Ref<boolean>} isDirty
 *   Getter or ref reporting whether the current draft has unsaved changes.
 * @param {(...args: any[]) => any} requestClose
 *   Performs the actual close/discard. Called immediately when clean, or only
 *   after the user accepts the confirmation when dirty. Its return value is
 *   forwarded by `confirmDiscard`/`confirmDiscardAccept`.
 * @returns {{
 *   confirmDiscard: (...args: any[]) => boolean,
 *   discardPromptOpen: import('vue').Ref<boolean>,
 *   confirmDiscardAccept: () => any,
 *   confirmDiscardCancel: () => void,
 * }}
 */
export function useDirtyGuard(isDirty, requestClose) {
  const discardPromptOpen = ref(false)
  let pendingArgs = null

  function evaluateDirty() {
    return Boolean(typeof isDirty === 'function' ? isDirty() : unref(isDirty))
  }

  function confirmDiscard(...args) {
    if (!evaluateDirty()) {
      if (typeof requestClose === 'function') requestClose(...args)
      return false
    }
    pendingArgs = args
    discardPromptOpen.value = true
    return true
  }

  function confirmDiscardAccept() {
    if (pendingArgs === null) {
      discardPromptOpen.value = false
      return undefined
    }
    const args = pendingArgs
    pendingArgs = null
    discardPromptOpen.value = false
    if (typeof requestClose === 'function') return requestClose(...args)
    return undefined
  }

  function confirmDiscardCancel() {
    pendingArgs = null
    discardPromptOpen.value = false
  }

  return {
    confirmDiscard,
    discardPromptOpen,
    confirmDiscardAccept,
    confirmDiscardCancel,
  }
}

export default useDirtyGuard
