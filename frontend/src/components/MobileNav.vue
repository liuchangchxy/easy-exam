<template>
  <nav class="mobile-nav-bar">
    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'home' }"
      :aria-label="t('nav.home')"
      :title="t('nav.home')"
      @click="$emit('navigate', 'home')"
    >
      <LinearIcon name="layers" size="18" />
      <span class="mobile-nav-label">{{ t('nav_short.home') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'mistakes' }"
      :aria-label="t('nav.mistakes')"
      :title="t('nav.mistakes')"
      @click="$emit('navigate', 'mistakes')"
    >
      <LinearIcon name="target" size="18" />
      <span class="mobile-nav-label">{{ t('nav_short.mistakes') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'learning' }"
      :aria-label="t('nav.learning')"
      :title="t('nav.learning')"
      @click="$emit('navigate', 'learning')"
    >
      <LinearIcon name="chart" size="18" />
      <span class="mobile-nav-label">{{ t('nav_short.learning') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'notes' }"
      :aria-label="t('nav.notes')"
      :title="t('nav.notes')"
      @click="$emit('navigate', 'notes')"
    >
      <LinearIcon name="edit" size="18" />
      <span class="mobile-nav-label">{{ t('nav_short.notes') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'import' }"
      :aria-label="t('nav.imports')"
      :title="t('nav.imports')"
      @click="$emit('navigate', 'import')"
    >
      <LinearIcon name="inbox" size="18" />
      <span class="mobile-nav-label">{{ t('nav_short.imports') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :aria-label="t('common.actions')"
      :title="t('common.actions')"
      @click="$emit('open-palette')"
    >
      <LinearIcon name="command" size="18" />
      <span class="mobile-nav-label">{{ t('nav_short.actions') }}</span>
    </button>
  </nav>
</template>

<script setup>
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

defineProps({
  currentPage: {
    type: String,
    default: 'home'
  }
})

defineEmits(['navigate', 'open-palette'])
</script>

<style scoped>
.mobile-nav-bar {
  display: none;
}

@media (max-width: 768px) {
  .mobile-nav-bar {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 52px;
    background: color-mix(in srgb, var(--bg-card) 94%, transparent);
    backdrop-filter: blur(12px);
    border-top: 1px solid var(--border);
    z-index: 900;
    align-items: center;
    justify-content: space-evenly;
    padding-bottom: env(safe-area-inset-bottom, 0);
  }

  .mobile-nav-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    padding: 2px 2px;
    color: var(--text-muted);
    flex: 1 1 0;
    min-width: 0;
    min-height: 44px;
    gap: 2px;
    cursor: pointer;
    transition: color 100ms ease;
  }

  .mobile-nav-item.active {
    color: var(--primary-fg, var(--primary));
  }

  .mobile-nav-label {
    font-size: 0.68rem;
    font-weight: 500;
    white-space: nowrap;
    line-height: 1.1;
    max-width: 100%;
    padding: 0 1px;
    text-align: center;
  }
}
</style>
