<template>
  <button
    type="button"
    class="theme-toggle"
    :class="{ 'theme-toggle-compact': compact }"
    :aria-label="actionLabel"
    :title="actionLabel"
    @click="toggleTheme"
  >
    <svg v-if="theme === 'light'" aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M20.2 15.4A8.4 8.4 0 0 1 8.6 3.8 8.5 8.5 0 1 0 20.2 15.4Z" />
    </svg>
    <svg v-else aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" />
    </svg>
    <span v-if="!compact" class="theme-toggle-label">{{ actionLabel }}</span>
    <span v-else class="theme-toggle-label">{{ theme === 'light' ? t('ui.k0647') : t('ui.k0648') }}</span>
  </button>
</template>

<script setup>
import { t } from '../composables/useLocale.js'
import { computed } from 'vue'
import { useTheme } from '../composables/useTheme.js'

defineProps({
  compact: { type: Boolean, default: false },
})

const { theme, toggleTheme } = useTheme()
const actionLabel = computed(() => theme.value === 'light' ? t('ui.k0048') : t('ui.k0049'))
</script>
