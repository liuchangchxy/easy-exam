// The app shell keeps its own copy of the bank list for the switcher, the
// command palette and the breadcrumb. Views that create, rename, archive or
// leave a bank announce it here so the shell never shows a name the page has
// already replaced.
export const BANKS_CHANGED_EVENT = 'easyexam:banks-changed'

export function notifyBanksChanged() {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  window.dispatchEvent(new CustomEvent(BANKS_CHANGED_EVENT))
}
