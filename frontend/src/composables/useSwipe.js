import { onMounted, onUnmounted, ref } from 'vue'

/**
 * Modern touch swipe gesture composable with vertical scroll protection.
 *
 * Requirements:
 * - Horizontal swipe threshold: |Δx| >= 40px
 * - Direction ratio protection: |Δx / Δy| >= 1.73 (prevents vertical page scrolling from triggering accidental question jumps)
 *
 * @param {import('vue').Ref<HTMLElement|null>} targetRef
 * @param {Object} options
 * @param {() => void} [options.onSwipeLeft] Triggered when swiping left (next question)
 * @param {() => void} [options.onSwipeRight] Triggered when swiping right (previous question)
 * @param {number} [options.threshold=40]
 * @param {number} [options.ratio=1.73]
 */
export function useSwipe(targetRef, options = {}) {
  const {
    onSwipeLeft,
    onSwipeRight,
    threshold = 40,
    ratio = 1.73
  } = options

  const isSwiping = ref(false)
  let startX = 0
  let startY = 0

  function handleTouchStart(e) {
    if (!e.touches || e.touches.length !== 1) return
    const touch = e.touches[0]
    startX = touch.clientX
    startY = touch.clientY
    isSwiping.value = true
  }

  function handleTouchEnd(e) {
    if (!isSwiping.value) return
    isSwiping.value = false
    if (!e.changedTouches || e.changedTouches.length === 0) return

    const touch = e.changedTouches[0]
    const deltaX = touch.clientX - startX
    const deltaY = touch.clientY - startY
    const absX = Math.abs(deltaX)
    const absY = Math.abs(deltaY)

    // Check minimum horizontal distance
    if (absX < threshold) return

    // Vertical scroll protection: |Δx / Δy| >= 1.73
    const safeY = absY === 0 ? 0.0001 : absY
    if (absX / safeY < ratio) return

    if (deltaX < 0) {
      onSwipeLeft?.()
    } else {
      onSwipeRight?.()
    }
  }

  function handleTouchCancel() {
    isSwiping.value = false
  }

  onMounted(() => {
    const el = targetRef?.value || window
    el.addEventListener('touchstart', handleTouchStart, { passive: true })
    el.addEventListener('touchend', handleTouchEnd, { passive: true })
    el.addEventListener('touchcancel', handleTouchCancel, { passive: true })
  })

  onUnmounted(() => {
    const el = targetRef?.value || window
    el.removeEventListener('touchstart', handleTouchStart)
    el.removeEventListener('touchend', handleTouchEnd)
    el.removeEventListener('touchcancel', handleTouchCancel)
  })

  return {
    isSwiping
  }
}
