<template>
  <Teleport to="body">
    <div v-if="open" class="app-dialog-layer">
      <div class="app-dialog-scrim" @click="onScrimClick"></div>
      <div
        ref="panelRef"
        v-bind="$attrs"
        class="app-dialog-panel"
        :class="panelClass"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="labelledBy"
        :aria-label="ariaLabelValue"
        tabindex="-1"
      >
        <header class="app-dialog-head">
          <slot name="head">
            <h2 v-if="title" :id="titleId" class="app-dialog-title">{{ title }}</h2>
          </slot>
          <button
            type="button"
            class="icon-btn app-dialog-close"
            :aria-label="t('common.close')"
            @click="requestClose('button')"
          >
            <LinearIcon name="x" size="16" />
          </button>
        </header>
        <div class="app-dialog-body">
          <slot />
        </div>
        <footer v-if="$slots.foot" class="app-dialog-foot">
          <slot name="foot" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, useSlots, watch } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '',
  },
  ariaLabel: {
    type: String,
    default: '',
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true,
  },
  closeOnEscape: {
    type: Boolean,
    default: true,
  },
  initialFocus: {
    type: String,
    default: '',
  },
  trapFocus: {
    type: Boolean,
    default: true,
  },
  panelClass: {
    type: [String, Array, Object],
    default: '',
  },
})

const emit = defineEmits(['close'])

const { t } = useLocale()
const slots = useSlots()

const instanceId = ++dialogInstanceSeq
const titleId = `app-dialog-title-${instanceId}`

const panelRef = ref(null)
const returnFocusEl = ref(null)

const hasCustomHead = computed(() => Boolean(slots.head))
const labelledBy = computed(() => (!hasCustomHead.value && props.title ? titleId : undefined))
const ariaLabelValue = computed(() => {
  if (props.ariaLabel) return props.ariaLabel
  if (hasCustomHead.value && props.title) return props.title
  return undefined
})

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'area[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'iframe',
  'object',
  'embed',
  'audio[controls]',
  'video[controls]',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

function focusableElements() {
  if (!panelRef.value) return []
  return Array.from(panelRef.value.querySelectorAll(FOCUSABLE_SELECTOR)).filter((el) => {
    if (el.closest('[inert]')) return false
    if (el.closest('[hidden]')) return false
    return el.getAttribute('aria-hidden') !== 'true'
  })
}

function focusInitial() {
  const panel = panelRef.value
  if (!panel) return
  if (props.initialFocus) {
    const preferred = panel.querySelector(props.initialFocus)
    if (preferred && typeof preferred.focus === 'function') {
      preferred.focus()
      return
    }
  }
  const items = focusableElements()
  if (items.length) {
    items[0].focus()
    return
  }
  panel.focus()
}

function isTopmost() {
  return dialogStack[dialogStack.length - 1] === instanceId
}

function onScrimClick() {
  if (!props.closeOnBackdrop) return
  requestClose('backdrop')
}

function requestClose(reason) {
  emit('close', reason)
}

function trapTab(event) {
  const panel = panelRef.value
  if (!panel) return
  const items = focusableElements()
  if (!items.length) {
    event.preventDefault()
    panel.focus()
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  const active = typeof document !== 'undefined' ? document.activeElement : null

  if (!active || !panel.contains(active)) {
    event.preventDefault()
    ;(event.shiftKey ? last : first).focus()
    return
  }
  if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  } else if (event.shiftKey && active === first) {
    event.preventDefault()
    last.focus()
  }
}

function onDocumentKeydown(event) {
  if (!props.open || !isTopmost()) return
  if (event.key === 'Escape' && props.closeOnEscape) {
    event.preventDefault()
    requestClose('escape')
    return
  }
  if (event.key === 'Tab' && props.trapFocus) {
    trapTab(event)
  }
}

function attachKeydown() {
  if (typeof document === 'undefined') return
  document.addEventListener('keydown', onDocumentKeydown, true)
}

function detachKeydown() {
  if (typeof document === 'undefined') return
  document.removeEventListener('keydown', onDocumentKeydown, true)
}

function registerDialog() {
  if (!dialogStack.includes(instanceId)) dialogStack.push(instanceId)
}

function unregisterDialog() {
  const index = dialogStack.indexOf(instanceId)
  if (index !== -1) dialogStack.splice(index, 1)
}

function captureReturnFocus() {
  if (typeof document === 'undefined') return
  const active = document.activeElement
  if (!active || active === document.body || active === document.documentElement) {
    returnFocusEl.value = null
    return
  }
  returnFocusEl.value = typeof active.focus === 'function' ? active : null
}

function restoreFocus() {
  const target = returnFocusEl.value
  returnFocusEl.value = null
  if (!target) return
  if (typeof target.isConnected === 'boolean' && !target.isConnected) return
  try {
    target.focus()
  } catch {
    // Focus restore is best-effort; the dialog still closed correctly.
  }
}

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      captureReturnFocus()
      registerDialog()
      lockBodyScroll()
      attachKeydown()
      await nextTick()
      focusInitial()
    } else {
      detachKeydown()
      unregisterDialog()
      unlockBodyScroll()
      restoreFocus()
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  detachKeydown()
  unregisterDialog()
  if (props.open) unlockBodyScroll()
  restoreFocus()
})
</script>

<script>
// Module-level state shared by every AppDialog instance: Escape/Tab only act on
// the topmost dialog, and body scroll stays locked until the last one closes.
let dialogInstanceSeq = 0
const dialogStack = []
let scrollLockCount = 0
let previousBodyOverflow = ''

function lockBodyScroll() {
  if (typeof document === 'undefined') return
  if (scrollLockCount === 0) {
    previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  scrollLockCount += 1
}

function unlockBodyScroll() {
  if (typeof document === 'undefined') return
  scrollLockCount = Math.max(0, scrollLockCount - 1)
  if (scrollLockCount === 0) {
    document.body.style.overflow = previousBodyOverflow
  }
}
</script>

<style scoped>
.app-dialog-layer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 20px;
}
.app-dialog-scrim {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--ink) 38%, transparent);
  backdrop-filter: blur(2px);
}
.app-dialog-panel {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  width: min(100%, var(--app-dialog-width, 640px));
  max-height: min(88vh, 960px);
  max-height: min(88dvh, 960px);
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-2);
  outline: none;
  animation: app-dialog-in 160ms var(--ease);
}
.app-dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--line);
}
.app-dialog-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: .01em;
  line-height: 1.3;
}
.app-dialog-close {
  flex: none;
  margin-left: auto;
}
.app-dialog-body {
  min-height: 0;
  padding: 16px 20px;
  overflow-y: auto;
}
.app-dialog-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--line);
  background: var(--surface);
}
@keyframes app-dialog-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  .app-dialog-panel { animation: none; }
}
@media (max-width: 600px) {
  .app-dialog-layer { padding: 10px; }
  .app-dialog-head { padding: 14px 16px 10px; }
  .app-dialog-body { padding: 14px 16px; }
  .app-dialog-foot { padding: 10px 16px; }
}
</style>
