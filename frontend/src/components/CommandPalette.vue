<template>
  <div v-if="isOpen" class="cmd-palette-backdrop" @click.self="close">
    <div ref="modalRef" class="cmd-palette-modal" role="dialog" aria-modal="true">
      <!-- 搜索输入栏 -->
      <div class="cmd-palette-search-row">
        <LinearIcon name="search" size="18" class="cmd-search-icon" />
        <input
          id="cmd-palette-input"
          ref="inputRef"
          v-model="query"
          type="text"
          class="cmd-palette-input"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded="true"
          aria-controls="cmd-palette-listbox"
          :aria-activedescendant="activeOptionId"
          :aria-label="t('commands.search_placeholder')"
          :placeholder="t('commands.search_placeholder')"
          @keydown.down.prevent="moveSelection(1)"
          @keydown.up.prevent="moveSelection(-1)"
          @keydown.enter.prevent="executeSelected"
        />
        <span class="cmd-palette-esc-badge">ESC</span>
      </div>

      <!-- 搜索结果列表 -->
      <div
        id="cmd-palette-listbox"
        class="cmd-palette-list"
        role="listbox"
        :aria-label="t('commands.search_placeholder')"
      >
        <!-- 1. 题库检索结果组 -->
        <template v-if="matchedBanks.length > 0">
          <div class="cmd-group-label" role="presentation">{{ t('commands.category_banks') }}</div>
          <div
            v-for="(bank, bIdx) in matchedBanks"
            :key="'bank-' + bank.id"
            :id="optionId('bank', bIdx)"
            class="cmd-palette-item bank-item"
            role="option"
            :aria-selected="currentFlatIndex === bIdx"
            :class="{ active: currentFlatIndex === bIdx }"
            @click="selectBank(bank)"
            @mouseenter="currentFlatIndex = bIdx"
          >
            <div class="cmd-item-left">
              <div class="cmd-icon-gem bank-gem">
                <LinearIcon name="layers" size="15" />
              </div>
              <div class="cmd-item-info">
                <div class="cmd-item-title-row">
                  <span class="cmd-item-title">{{ bank.name }}</span>
                  <span v-if="bank.category" class="cmd-bank-category-pill">{{ bank.category }}</span>
                </div>
                <span class="cmd-item-desc">{{ bank.description || t('home.no_description') }}</span>
              </div>
            </div>
            <div class="cmd-item-right">
              <span class="cmd-bank-count">{{ bank.question_count }} {{ t('home.questions_count', { count: bank.question_count }) }}</span>
              <button
                type="button"
                class="cmd-bank-practice"
                @click.stop="practiceBank(bank)"
              >{{ t('commands.bank_action_practice') }}</button>
              <span class="cmd-action-hint">{{ t('commands.bank_action_open') }} ↵</span>
            </div>
          </div>
        </template>

        <!-- 2. 功能与页面导航结果组 -->
        <template v-if="matchedCommands.length > 0">
          <div class="cmd-group-label" role="presentation">{{ t('commands.category_actions') }}</div>
          <div
            v-for="(cmd, cIdx) in matchedCommands"
            :key="cmd.id"
            :id="optionId('action', cIdx)"
            class="cmd-palette-item action-item"
            role="option"
            :aria-selected="currentFlatIndex === (matchedBanks.length + cIdx)"
            :class="{ active: currentFlatIndex === (matchedBanks.length + cIdx) }"
            @click="execute(cmd)"
            @mouseenter="currentFlatIndex = matchedBanks.length + cIdx"
          >
            <div class="cmd-item-left">
              <div class="cmd-icon-gem action-gem">
                <LinearIcon :name="cmd.icon" size="15" />
              </div>
              <div class="cmd-item-info">
                <span class="cmd-item-title">{{ cmd.title }}</span>
                <span v-if="cmd.description" class="cmd-item-desc">{{ cmd.description }}</span>
              </div>
            </div>
            <div class="cmd-item-right">
              <span v-if="cmd.shortcut" class="cmd-item-shortcut">{{ cmd.shortcut }}</span>
            </div>
          </div>
        </template>

        <!-- 空状态 -->
        <div v-if="totalItemsCount === 0" class="cmd-palette-empty" role="presentation">
          <LinearIcon name="search" size="24" class="empty-icon" />
          <p>{{ t('commands.no_results') }}</p>
        </div>
      </div>

      <!-- 底部操作提示 -->
      <div class="cmd-palette-footer">
        <div class="cmd-footer-hint">
          <span class="cmd-key">↑</span><span class="cmd-key">↓</span> {{ t('commands.footer_hint_navigate') }}
          <span class="cmd-key">↵</span> {{ t('commands.footer_hint_select') }}
          <span class="cmd-key">esc</span> {{ t('commands.footer_hint_close') }}
        </div>
        <span class="cmd-footer-tag">{{ t('ui.k0757') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({
  commands: {
    type: Array,
    default: () => []
  },
  banks: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['execute', 'select-bank', 'practice-bank'])

const isOpen = ref(false)
const query = ref('')
const currentFlatIndex = ref(0)
const inputRef = ref(null)
const modalRef = ref(null)
let lastFocusedElement = null

// 匹配题库
const matchedBanks = computed(() => {
  const q = query.value.toLowerCase().trim()
  if (!q) {
    // 默认展示前 5 个题库
    return (props.banks || []).slice(0, 5)
  }
  return (props.banks || []).filter(b =>
    (b.name && b.name.toLowerCase().includes(q)) ||
    (b.category && b.category.toLowerCase().includes(q)) ||
    (b.description && b.description.toLowerCase().includes(q))
  )
})

// 匹配系统功能命令
const matchedCommands = computed(() => {
  const q = query.value.toLowerCase().trim()
  if (!q) return props.commands
  return props.commands.filter(c =>
    c.title.toLowerCase().includes(q) ||
    (c.description && c.description.toLowerCase().includes(q))
  )
})

const totalItemsCount = computed(() => matchedBanks.value.length + matchedCommands.value.length)

// Stable per-row ids so the combobox can point at the active option.
function optionId(kind, index) {
  return `cmd-palette-opt-${kind}-${index}`
}

const activeOptionId = computed(() => {
  if (totalItemsCount.value === 0) return undefined
  const bankCount = matchedBanks.value.length
  return currentFlatIndex.value < bankCount
    ? optionId('bank', currentFlatIndex.value)
    : optionId('action', currentFlatIndex.value - bankCount)
})

// Background scroll lock while the palette is open. Restores whatever the page
// had before instead of assuming it was scrollable.
let lockedBody = null
let previousOverflow = ''
let previousPaddingRight = ''

function lockBackgroundScroll() {
  const body = typeof document !== 'undefined' ? document.body : null
  if (!body || lockedBody) return
  lockedBody = body
  previousOverflow = body.style.overflow
  previousPaddingRight = body.style.paddingRight
  const root = document.documentElement
  const scrollbarWidth = globalThis.innerWidth && root
    ? Math.max(0, globalThis.innerWidth - root.clientWidth)
    : 0
  body.style.overflow = 'hidden'
  if (scrollbarWidth > 0) body.style.paddingRight = `${scrollbarWidth}px`
}

function unlockBackgroundScroll() {
  if (!lockedBody) return
  lockedBody.style.overflow = previousOverflow
  lockedBody.style.paddingRight = previousPaddingRight
  lockedBody = null
}

watch([matchedBanks, matchedCommands], () => {
  currentFlatIndex.value = 0
})

function open() {
  if (isOpen.value) return
  // Remember the trigger so Escape, outside click and row selection all return
  // focus to where the palette was opened from.
  lastFocusedElement = typeof document !== 'undefined' ? document.activeElement : null
  isOpen.value = true
  query.value = ''
  currentFlatIndex.value = 0
  lockBackgroundScroll()
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function close() {
  if (!isOpen.value) return
  isOpen.value = false
  unlockBackgroundScroll()
  const target = lastFocusedElement
  lastFocusedElement = null
  nextTick(() => {
    if (target && typeof target.focus === 'function' && document.contains(target)) target.focus()
  })
}

function moveSelection(step) {
  const total = totalItemsCount.value
  if (total === 0) return
  currentFlatIndex.value = (currentFlatIndex.value + step + total) % total
}

function selectBank(bank) {
  close()
  emit('select-bank', bank)
}

function practiceBank(bank) {
  close()
  emit('practice-bank', bank)
}

function execute(cmd) {
  close()
  emit('execute', cmd)
}

function executeSelected() {
  const bLen = matchedBanks.value.length
  if (currentFlatIndex.value < bLen) {
    const bank = matchedBanks.value[currentFlatIndex.value]
    if (bank) selectBank(bank)
  } else {
    const cIdx = currentFlatIndex.value - bLen
    const cmd = matchedCommands.value[cIdx]
    if (cmd) execute(cmd)
  }
}

function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (isOpen.value) close()
    else open()
  }
}

function getFocusableElements() {
  const root = modalRef.value
  if (!root) return []
  return Array.from(root.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  ))
}

/**
 * Document-level keys while open:
 *  - Escape closes even after focus would otherwise have left the modal.
 *  - Tab is trapped inside the modal instead of walking into the page behind it.
 */
function handleDocumentKeydown(e) {
  if (!isOpen.value) return
  if (e.key === 'Escape') {
    e.preventDefault()
    close()
    return
  }
  if (e.key !== 'Tab') return

  const focusable = getFocusableElements()
  const root = modalRef.value
  if (!focusable.length || !root) {
    e.preventDefault()
    inputRef.value?.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement
  const inside = active && root.contains(active)

  if (e.shiftKey) {
    if (!inside || active === first) {
      e.preventDefault()
      last.focus()
    }
  } else if (!inside || active === last) {
    e.preventDefault()
    first.focus()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  document.addEventListener('keydown', handleDocumentKeydown)
})

onUnmounted(() => {
  unlockBackgroundScroll()
  window.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('keydown', handleDocumentKeydown)
})

defineExpose({ open, close })
</script>

<style scoped>
.cmd-palette-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 9vh 16px 16px;
  background: color-mix(in srgb, var(--ink) 38%, transparent);
  backdrop-filter: blur(2px);
}
.cmd-palette-modal {
  width: min(100%, 600px);
  max-height: 74vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-2);
}
.cmd-palette-search-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.cmd-search-icon { color: var(--ink-3); flex-shrink: 0; }
.cmd-palette-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: 14px;
}
.cmd-palette-input::placeholder { color: var(--ink-4); }
.cmd-palette-esc-badge,
.cmd-key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 20px;
  padding: 0 5px;
  border: 1px solid var(--line-strong);
  border-bottom-width: 2px;
  border-radius: var(--r-xs);
  background: var(--surface-2);
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--ink-3);
}
.cmd-palette-list {
  overflow-y: auto;
  padding: 6px;
  display: flex;
  flex-direction: column;
}
.cmd-group-label {
  padding: 10px 10px 4px;
  font-family: var(--font-sans);
  font-size: 9.5px;
  font-weight: 650;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--ink-4);
}
.cmd-palette-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 10px;
  border-left: 2px solid transparent;
  cursor: pointer;
  user-select: none;
}
.cmd-palette-item:hover,
.cmd-palette-item.active { background: var(--surface-2); border-left-color: var(--brand); }
.cmd-item-left { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.cmd-icon-gem {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  color: var(--ink-3);
}
.bank-gem { color: var(--brand); }
.action-gem { color: var(--ink-3); }
.cmd-palette-item.active .action-gem { color: var(--brand); }
.cmd-item-info { display: flex; flex-direction: column; gap: 1px; min-width: 0; flex: 1; }
.cmd-item-title-row { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.cmd-item-title {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 550;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cmd-bank-category-pill {
  font-size: 10px;
  color: var(--ink-4);
  flex-shrink: 0;
}
.cmd-item-desc {
  font-size: 11.5px;
  color: var(--ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cmd-item-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.cmd-bank-count { font-family: var(--font-mono); font-size: 10px; color: var(--ink-4); }
.cmd-bank-practice {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: var(--r-xs);
  background: var(--surface);
  color: var(--ink-2);
  font-size: 10.5px;
  white-space: nowrap;
  transition: border-color .12s var(--ease), color .12s var(--ease);
}
.cmd-bank-practice:hover { border-color: var(--brand); color: var(--brand); }
.cmd-action-hint {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--brand);
  opacity: 0;
}
.cmd-palette-item.active .cmd-action-hint { opacity: 1; }
.cmd-item-shortcut { font-family: var(--font-mono); font-size: 10px; color: var(--ink-4); }
.cmd-palette-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 36px 16px;
  color: var(--ink-4);
  font-size: 12.5px;
}
.cmd-palette-empty p { margin: 0; }
.cmd-palette-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 14px;
  border-top: 1px solid var(--line);
  background: var(--surface-2);
  font-size: 10.5px;
  color: var(--ink-3);
}
.cmd-footer-hint { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.cmd-footer-tag { font-family: var(--font-mono); font-size: 9.5px; color: var(--ink-4); }
@media (max-width: 480px) {
  .cmd-palette-backdrop { padding-top: 6vh; }
  .cmd-footer-tag { display: none; }
  .cmd-bank-count { display: none; }
}
</style>
