<template>
  <nav class="mobile-nav-bar">
    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'home' }"
      @click="$emit('navigate', 'home')"
    >
      <LinearIcon name="layers" size="18" />
      <span class="mobile-nav-label">{{ t('nav.practice') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'mistakes' }"
      @click="$emit('navigate', 'mistakes')"
    >
      <LinearIcon name="target" size="18" />
      <span class="mobile-nav-label">{{ t('nav.mistakes') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'learning' }"
      @click="$emit('navigate', 'learning')"
    >
      <LinearIcon name="chart" size="18" />
      <span class="mobile-nav-label">{{ t('nav.learning') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      :class="{ active: currentPage === 'import' }"
      @click="$emit('navigate', 'import')"
    >
      <LinearIcon name="inbox" size="18" />
      <span class="mobile-nav-label">{{ t('nav.imports') }}</span>
    </button>

    <button
      type="button"
      class="mobile-nav-item"
      @click="$emit('open-palette')"
    >
      <LinearIcon name="command" size="18" />
      <span class="mobile-nav-label">{{ t('common.actions') }}</span>
    </button>

    <ThemeToggle compact />
    <LocaleToggle compact />
  </nav>
</template>

<script setup>
import LinearIcon from './LinearIcon.vue'
import ThemeToggle from './ThemeToggle.vue'
import LocaleToggle from './LocaleToggle.vue'
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
    color: var(--text-muted);
    flex: 1 1 0;
    min-width: 0;
    min-height: 44px;
    gap: 2px;
    cursor: pointer;
    transition: color 100ms ease;
  }

  .mobile-nav-item.active {
    color: var(--primary);
  }

  .mobile-nav-label {
    font-size: 0.65rem;
    font-weight: 500;
  }

  .mobile-nav-bar :deep(.theme-toggle) {
    height: 44px;
    min-height: 44px;
    min-width: 0;
    flex: 1 1 0;
    flex-direction: column;
    gap: 2px;
    padding: 0;
    border: 0;
    border-radius: 0;
  }

  .mobile-nav-bar :deep(.theme-toggle-label) {
    font-size: 0.65rem;
    font-weight: 500;
  }
}
</style>
