<template>
  <div v-if="isOpen" class="cmd-palette-backdrop" @click.self="close" @keydown.esc="close">
    <div class="cmd-palette-modal" role="dialog" aria-modal="true">
      <div class="cmd-palette-search-row">
        <LinearIcon name="search" size="18" class="cmd-search-icon" />
        <input
          ref="inputRef"
          v-model="query"
          type="text"
          placeholder="键入指令或跳转模块... (ESC 关闭, ↑↓ 移动, ↵ 确认)"
          class="cmd-palette-input"
          @keydown.down.prevent="moveSelection(1)"
          @keydown.up.prevent="moveSelection(-1)"
          @keydown.enter.prevent="executeSelected"
        />
        <span class="cmd-palette-badge">ESC</span>
      </div>

      <div class="cmd-palette-list">
        <div
          v-for="(cmd, index) in filteredCommands"
          :key="cmd.id"
          class="cmd-palette-item"
          :class="{ active: index === selectedIndex }"
          @click="execute(cmd)"
          @mouseenter="selectedIndex = index"
        >
          <div class="cmd-item-left">
            <LinearIcon :name="cmd.icon" size="16" class="cmd-item-icon" />
            <span class="cmd-item-title">{{ cmd.title }}</span>
            <span v-if="cmd.description" class="cmd-item-desc">{{ cmd.description }}</span>
          </div>
          <span v-if="cmd.shortcut" class="cmd-item-shortcut">{{ cmd.shortcut }}</span>
        </div>

        <div v-if="filteredCommands.length === 0" class="cmd-palette-empty">
          无匹配指令
        </div>
      </div>

      <div class="cmd-palette-footer">
        <div class="cmd-footer-hint">
          <span class="cmd-key">↑</span><span class="cmd-key">↓</span> 导航
          <span class="cmd-key">↵</span> 选择
          <span class="cmd-key">esc</span> 退出
        </div>
        <span class="cmd-footer-tag">Linear Command Palette</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import LinearIcon from './LinearIcon.vue'

const props = defineProps({
  commands: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['execute'])

const isOpen = ref(false)
const query = ref('')
const selectedIndex = ref(0)
const inputRef = ref(null)

const filteredCommands = computed(() => {
  if (!query.value.trim()) return props.commands
  const q = query.value.toLowerCase().trim()
  return props.commands.filter(c =>
    c.title.toLowerCase().includes(q) ||
    (c.description && c.description.toLowerCase().includes(q)) ||
    (c.keywords && c.keywords.some(k => k.toLowerCase().includes(q)))
  )
})

watch(filteredCommands, () => {
  selectedIndex.value = 0
})

function open() {
  isOpen.value = true
  query.value = ''
  selectedIndex.value = 0
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function close() {
  isOpen.value = false
}

function moveSelection(step) {
  if (filteredCommands.value.length === 0) return
  selectedIndex.value = (selectedIndex.value + step + filteredCommands.value.length) % filteredCommands.value.length
}

function execute(cmd) {
  close()
  emit('execute', cmd)
}

function executeSelected() {
  if (filteredCommands.value[selectedIndex.value]) {
    execute(filteredCommands.value[selectedIndex.value])
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
  background: color-mix(in srgb, var(--text-main) 40%, transparent);
  backdrop-filter: blur(8px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
  animation: cmdFadeIn 120ms ease-out;
}

@keyframes cmdFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.cmd-palette-modal {
  width: min(100% - 2rem, 580px);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow-xl);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.cmd-palette-search-row {
  display: flex;
  align-items: center;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  gap: 0.75rem;
}

.cmd-search-icon {
  color: var(--text-muted);
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
}

.cmd-palette-badge {
  padding: 2px 6px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 0.7rem;
  font-family: var(--linear-mono, monospace);
  color: var(--text-muted);
}

.cmd-palette-list {
  max-height: 320px;
  overflow-y: auto;
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cmd-palette-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 80ms ease;
  user-select: none;
}

.cmd-palette-item:hover,
.cmd-palette-item.active {
  background: var(--bg-subtle);
}

.cmd-palette-item.active .cmd-item-title {
  color: var(--primary);
}

.cmd-item-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.cmd-item-icon {
  color: var(--text-muted);
}

.cmd-palette-item.active .cmd-item-icon {
  color: var(--primary);
}

.cmd-item-title {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-main);
}

.cmd-item-desc {
  font-size: 0.775rem;
  color: var(--text-muted);
  margin-left: 0.5rem;
}

.cmd-item-shortcut {
  font-size: 0.7rem;
  font-family: var(--linear-mono, monospace);
  color: var(--text-muted);
  background: var(--bg-page);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-subtle);
}

.cmd-palette-empty {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.cmd-palette-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: var(--bg-page);
  border-top: 1px solid var(--border-subtle);
  font-size: 0.725rem;
  color: var(--text-muted);
}

.cmd-footer-hint {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.cmd-key {
  display: inline-block;
  padding: 1px 4px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-family: var(--linear-mono, monospace);
  font-size: 0.675rem;
}

.cmd-footer-tag {
  font-family: var(--linear-mono, monospace);
  color: var(--text-tertiary);
}
</style>
