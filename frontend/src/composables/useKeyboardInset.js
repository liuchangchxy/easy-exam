/**
 * Track the slice of the layout viewport hidden by the on-screen keyboard and
 * publish it as `--kb-inset` on <html>.
 *
 * Fixed bottom bars can then sit at `bottom: var(--kb-inset, 0px)` and lift by
 * exactly the overlap, so a focused textarea is never covered by the keyboard.
 * Browsers without `visualViewport` (and unit tests) degrade to 0.
 */
import { onBeforeUnmount, onMounted } from 'vue'

export const KEYBOARD_INSET_PROPERTY = '--kb-inset'

/**
 * Pure overlap calculation: how many pixels of the layout viewport sit below
 * the visual viewport (and are therefore covered by the keyboard).
 *
 * @param {{ height?: number, offsetTop?: number } | null} viewport
 * @param {number} layoutHeight usually `window.innerHeight`
 * @returns {number} whole pixels, never negative
 */
export function keyboardInsetFromViewport(viewport, layoutHeight) {
  if (!viewport) return 0
  const height = Number(viewport.height)
  const offsetTop = Number(viewport.offsetTop) || 0
  const layout = Number(layoutHeight)
  if (!Number.isFinite(height) || !Number.isFinite(layout) || layout <= 0) return 0
  const overlap = layout - height - offsetTop
  return overlap > 0 ? Math.round(overlap) : 0
}

function currentRoot() {
  return typeof document !== 'undefined' ? document.documentElement : null
}

export function useKeyboardInset(options = {}) {
  const property = options.property || KEYBOARD_INSET_PROPERTY
  let viewport = null
  let inset = 0

  function writeInset(value) {
    const root = currentRoot()
    if (root) root.style.setProperty(property, `${value}px`)
  }

  function measure() {
    if (typeof window === 'undefined') return 0
    inset = keyboardInsetFromViewport(window.visualViewport || null, window.innerHeight)
    writeInset(inset)
    return inset
  }

  function onViewportChange() {
    measure()
  }

  function attach() {
    if (typeof window === 'undefined') return
    viewport = window.visualViewport || null
    if (viewport && typeof viewport.addEventListener === 'function') {
      viewport.addEventListener('resize', onViewportChange)
      viewport.addEventListener('scroll', onViewportChange)
    }
    // Orientation changes and desktop window resizes can also move the visual
    // viewport without a visualViewport resize event on some engines.
    window.addEventListener('orientationchange', onViewportChange)
    window.addEventListener('resize', onViewportChange)
    measure()
  }

  function detach() {
    if (viewport && typeof viewport.removeEventListener === 'function') {
      viewport.removeEventListener('resize', onViewportChange)
      viewport.removeEventListener('scroll', onViewportChange)
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('orientationchange', onViewportChange)
      window.removeEventListener('resize', onViewportChange)
    }
    viewport = null
    inset = 0
    const root = currentRoot()
    if (root) root.style.removeProperty(property)
  }

  onMounted(attach)
  onBeforeUnmount(detach)

  return {
    measure,
    get inset() {
      return inset
    },
  }
}

export default useKeyboardInset
