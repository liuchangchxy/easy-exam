<template>
  <div v-if="isOpen" class="cmd-palette-backdrop" @click.self="close" @keydown.esc="close">
    <div class="cmd-palette-modal" role="dialog" aria-modal="true">
      <!-- 搜索输入栏 -->
      <div class="cmd-palette-search-row">
        <LinearIcon name="search" size="18" class="cmd-search-icon" />
        <input
          ref="inputRef"
          v-model="query"
          type="text"
          :placeholder="t('commands.search_placeholder')"
          class="cmd-palette-input"
          @keydown.down.prevent="moveSelection(1)"
          @keydown.up.prevent="moveSelection(-1)"
          @keydown.enter.prevent="executeSelected"
        />
        <span class="cmd-palette-esc-badge">ESC</span>
      </div>

      <!-- 搜索结果列表 -->
      <div class="cmd-palette-list">
        <!-- 1. 题库检索结果组 -->
        <template v-if="matchedBanks.length > 0">
          <div class="cmd-group-label">{{ t('commands.category_banks') }}</div>
          <div
            v-for="(bank, bIdx) in matchedBanks"
            :key="'bank-' + bank.id"
            class="cmd-palette-item bank-item"
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
              <span class="cmd-action-hint">{{ t('commands.bank_action_practice') }} ↵</span>
            </div>
          </div>
        </template>

        <!-- 2. 功能与页面导航结果组 -->
        <template v-if="matchedCommands.length > 0">
          <div class="cmd-group-label">{{ t('commands.category_actions') }}</div>
          <div
            v-for="(cmd, cIdx) in matchedCommands"
            :key="cmd.id"
            class="cmd-palette-item action-item"
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
        <div v-if="totalItemsCount === 0" class="cmd-palette-empty">
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

const emit = defineEmits(['execute', 'select-bank'])

const isOpen = ref(false)
const query = ref('')
const currentFlatIndex = ref(0)
const inputRef = ref(null)

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

watch([matchedBanks, matchedCommands], () => {
  currentFlatIndex.value = 0
})

function open() {
  isOpen.value = true
  query.value = ''
  currentFlatIndex.value = 0
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function close() {
  isOpen.value = false
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

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

defineExpose({ open, close })
</script>

<style scoped>
.cmd-palette-backdrop {
  position: fixed;
  inset: 0;
  background: color-mix(in srgb, var(--text-main) 45%, transparent);
  backdrop-filter: blur(10px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 10vh;
  animation: cmdFadeIn 140ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cmdFadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.cmd-palette-modal {
  width: min(100% - 2rem, 640px);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.22);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.cmd-palette-search-row {
  display: flex;
  align-items: center;
  padding: 0.95rem 1.15rem;
  border-bottom: 1px solid var(--border-subtle);
  gap: 0.75rem;
  background: var(--bg-page);
}

.cmd-search-icon {
  color: var(--primary);
  flex-shrink: 0;
}

.cmd-palette-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-main);
  font-size: 0.95rem;
  font-family: inherit;
}

.cmd-palette-input::placeholder {
  color: var(--text-tertiary);
  font-size: 0.88rem;
}

.cmd-palette-esc-badge {
  padding: 2px 7px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 0.68rem;
  font-family: var(--linear-mono, monospace);
  color: var(--text-muted);
}

.cmd-palette-list {
  max-height: 380px;
  overflow-y: auto;
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cmd-group-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
  padding: 0.45rem 0.65rem 0.25rem;
}

.cmd-palette-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 90ms ease;
  user-select: none;
  gap: 0.75rem;
}

.cmd-palette-item:hover,
.cmd-palette-item.active {
  background: var(--primary-light);
}

.cmd-palette-item.active .cmd-item-title {
  color: var(--primary);
}

.cmd-item-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
  flex: 1;
}

.cmd-icon-gem {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bank-gem {
  background: var(--primary-light);
  color: var(--primary);
  border: 1px solid var(--primary-border);
}

.action-gem {
  background: var(--bg-subtle);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.cmd-palette-item.active .action-gem {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.cmd-item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.cmd-item-title-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}

.cmd-item-title {
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cmd-bank-category-pill {
  font-size: 0.68rem;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--bg-subtle);
  color: var(--text-muted);
  border: 1px solid var(--border);
  flex-shrink: 0;
}

.cmd-item-desc {
  font-size: 0.75rem;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cmd-item-right {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}

.cmd-bank-count {
  font-size: 0.75rem;
  font-family: var(--linear-mono, monospace);
  color: var(--text-muted);
}

.cmd-action-hint {
  font-size: 0.72rem;
  color: var(--primary);
  font-weight: 500;
  opacity: 0;
  transition: opacity 100ms ease;
}

.cmd-palette-item.active .cmd-action-hint {
  opacity: 1;
}

.cmd-item-shortcut {
  font-size: 0.68rem;
  font-family: var(--linear-mono, monospace);
  color: var(--text-tertiary);
  opacity: 0.8;
}

.cmd-palette-empty {
  padding: 2.5rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.65rem;
  color: var(--text-tertiary);
  font-size: 0.85rem;
}

.empty-icon {
  opacity: 0.4;
}

.cmd-palette-footer {
  padding: 0.65rem 1rem;
  background: var(--bg-page);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

.cmd-footer-hint {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.cmd-key {
  padding: 1px 4px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-family: var(--linear-mono, monospace);
  font-size: 0.68rem;
  color: var(--text-muted);
}

.cmd-footer-tag {
  font-family: var(--linear-mono, monospace);
  font-size: 0.68rem;
  opacity: 0.7;
}
</style>
