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

    <!-- 更多/设置次级弹出菜单 (收纳导入与设置，彻底减负一级底栏) -->
    <div class="mobile-nav-more-container">
      <button
        type="button"
        class="mobile-nav-item mobile-nav-item-more"
        :class="{ active: currentPage === 'import' || currentPage === 'settings' || showMorePopup }"
        :aria-label="t('nav_short.actions')"
        :title="t('nav_short.actions')"
        @click="showMorePopup = !showMorePopup"
      >
        <LinearIcon name="settings" size="18" />
        <span class="mobile-nav-label">{{ t('nav_short.actions') }}</span>
      </button>

      <!-- 优雅紧凑的次级菜单卡片 -->
      <div v-if="showMorePopup" class="mobile-nav-more-popup" @click="showMorePopup = false">
        <button
          type="button"
          class="more-popup-item"
          :class="{ active: currentPage === 'import' }"
          @click="$emit('navigate', 'import')"
        >
          <LinearIcon name="inbox" size="16" />
          <span>{{ t('nav.imports') }}</span>
        </button>
        <button
          type="button"
          class="more-popup-item"
          :class="{ active: currentPage === 'settings' }"
          @click="$emit('navigate', 'settings')"
        >
          <LinearIcon name="settings" size="16" />
          <span>{{ t('nav.settings') }}</span>
        </button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()
const showMorePopup = ref(false)

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

  .mobile-nav-more-container {
    flex: 1 1 0;
    display: flex;
    position: relative;
    justify-content: center;
  }

  .mobile-nav-item-more {
    width: 100%;
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

  .mobile-nav-more-popup {
    position: absolute;
    bottom: 100%;
    right: 0.5rem;
    margin-bottom: 0.5rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    min-width: 8rem;
    z-index: 950;
    overflow: hidden;
  }

  .more-popup-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.65rem 0.9rem;
    font-size: 0.85rem;
    color: var(--text-main);
    background: transparent;
    border: none;
    border-bottom: 1px solid var(--border-subtle);
    cursor: pointer;
    text-align: left;
    white-space: nowrap;
  }

  .more-popup-item:last-child {
    border-bottom: none;
  }

  .more-popup-item:hover, .more-popup-item:active {
    background: var(--bg-muted);
  }

  .more-popup-item.active {
    color: var(--primary-fg, var(--primary));
    font-weight: 600;
  }
}
</style>
