<template>
  <button
    type="button"
    class="theme-toggle locale-toggle"
    :class="{ 'theme-toggle-compact': compact }"
    :aria-label="t('locale.switch_language')"
    :title="t('locale.switch_language')"
    @click="toggleLocale"
  >
    <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
    <span v-if="!compact" class="theme-toggle-label">{{ locale === 'zh-CN' ? 'English' : t('ui.k0645') }}</span>
    <span v-else class="theme-toggle-label">{{ locale === 'zh-CN' ? 'EN' : t('ui.k0646') }}</span>
  </button>
</template>

<script setup>
import { useLocale } from '../composables/useLocale.js'

defineProps({
  compact: { type: Boolean, default: false },
})

const { locale, toggleLocale, t } = useLocale()
</script>
