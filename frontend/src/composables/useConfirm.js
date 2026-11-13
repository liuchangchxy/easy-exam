import { ref } from 'vue'

/**
 * One confirmation flow for the whole app.
 *
 * The app registers a dialog presenter (ConfirmHost) once, so production always
 * shows the editorial AppDialog. When a view is mounted on its own — as the
 * component tests do — no presenter is registered and the fallback is the
 * native `window.confirm(title)`. That keeps every existing test that stubs
 * `confirm` valid without rewriting an assertion.
 *
 * The fallback receives the title only: that is the single string those stubs
 * assert on, so callers must pass the same catalog sentence they always did.
 */
let confirmPresenter = null
let noticePresenter = null

export function setConfirmPresenter(fn) {
  confirmPresenter = typeof fn === 'function' ? fn : null
}

export function resetConfirmPresenter() {
  confirmPresenter = null
}

export function setNoticePresenter(fn) {
  noticePresenter = typeof fn === 'function' ? fn : null
}

export function resetNoticePresenter() {
  noticePresenter = null
}

/**
 * @param {{ title: string, body?: string, confirmLabel?: string, cancelLabel?: string, danger?: boolean }} options
 * @returns {Promise<boolean>} true when the user accepts
 */
export function askConfirm(options = {}) {
  const request = {
    title: options.title || '',
    body: options.body || '',
    confirmLabel: options.confirmLabel || '',
    cancelLabel: options.cancelLabel || '',
    danger: Boolean(options.danger),
  }
  if (confirmPresenter) {
    return Promise.resolve(confirmPresenter(request)).then(Boolean)
  }
  if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
    return Promise.resolve(Boolean(window.confirm(request.title)))
  }
  return Promise.resolve(false)
}

/**
 * Callback form of `askConfirm` for handlers that must stay synchronous when
 * the native fallback answers (as it does in single-view tests). `onAccept`
 * runs only after an accepted confirmation; its return value is passed through
 * for callers that want to chain a promise.
 *
 * @param {object} options see `askConfirm`
 * @param {() => any} onAccept
 * @returns {boolean|Promise<any>} false when declined, otherwise onAccept's result
 */
export function withConfirm(options, onAccept) {
  const handler = typeof onAccept === 'function' ? onAccept : () => undefined
  const request = {
    title: options?.title || '',
    body: options?.body || '',
    confirmLabel: options?.confirmLabel || '',
    cancelLabel: options?.cancelLabel || '',
    danger: Boolean(options?.danger),
  }
  if (confirmPresenter) {
    return Promise.resolve(confirmPresenter(request)).then(ok => (ok ? handler() : false))
  }
  if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
    return window.confirm(request.title) ? handler() : false
  }
  return false
}

/**
 * A blocking error that has no better in-page home. The app presenter renders
 * it as a transient error toast; the standalone fallback is `window.alert`.
 *
 * @param {{ title: string, body?: string, danger?: boolean }} options
 */
export function askNotice(options = {}) {
  const request = {
    title: options.title || '',
    body: options.body || '',
    danger: Boolean(options.danger),
  }
  if (noticePresenter) {
    noticePresenter(request)
    return
  }
  if (typeof window !== 'undefined' && typeof window.alert === 'function') {
    window.alert(request.title)
  }
}

// Reactive mirror of the host state, for the host component itself.
export const confirmState = ref({
  open: false,
  title: '',
  body: '',
  confirmLabel: '',
  cancelLabel: '',
  danger: false,
})

export function useConfirm() {
  return { ask: askConfirm, confirm: withConfirm, notify: askNotice }
}

export default useConfirm
