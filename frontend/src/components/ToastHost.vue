<template>
  <div id="toast-root" aria-live="polite" aria-atomic="true">
    <div
      v-if="head"
      :key="head.id"
      class="toast"
      :class="head.kind"
      role="status"
      data-testid="toast"
    >
      <span class="toast-text">{{ head.message }}</span>
      <button
        type="button"
        class="toast-dismiss"
        :aria-label="t('common.dismiss')"
        @click="dismiss(head.id)"
      >
        <LinearIcon name="x" size="12" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { useLocale } from '../composables/useLocale'
import { useToast } from '../composables/useToast'

const { t } = useLocale()
const { toasts, dismiss } = useToast()

// One at a time: the queue advances only when the visible entry leaves.
const head = computed(() => toasts[0] || null)
</script>

<style scoped>
.toast { pointer-events: auto; }
.toast-text { min-width: 0; overflow-wrap: anywhere; }
.toast-dismiss {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 2px;
  background: transparent;
  color: inherit;
  opacity: .65;
  cursor: pointer;
}
.toast-dismiss:hover { opacity: 1; }
</style>
