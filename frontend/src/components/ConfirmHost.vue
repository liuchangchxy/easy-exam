<template>
  <AppDialog
    :open="confirmState.open"
    :title="confirmState.title"
    :aria-label="confirmState.title"
    panel-class="confirm-dialog"
    style="--app-dialog-width: 440px"
    initial-focus="[data-testid='confirm-cancel']"
    data-testid="confirm-dialog"
    @close="cancel"
  >
    <p v-if="confirmState.body" class="confirm-text">{{ confirmState.body }}</p>
    <template #foot>
      <button
        type="button"
        class="btn btn-quiet"
        data-testid="confirm-cancel"
        @click="cancel"
      >{{ confirmState.cancelLabel || t('common.cancel') }}</button>
      <button
        type="button"
        class="btn"
        :class="confirmState.danger ? 'btn-danger' : 'btn-primary'"
        data-testid="confirm-ok"
        @click="accept"
      >{{ confirmState.confirmLabel || t('common.confirm') }}</button>
    </template>
  </AppDialog>
</template>

<script setup>
import { onBeforeUnmount } from 'vue'
import AppDialog from './AppDialog.vue'
import { useLocale } from '../composables/useLocale'
import { confirmState } from '../composables/useConfirm'

const { t } = useLocale()

let pendingResolve = null

// Registered as the app-wide presenter in App.vue. The returned promise is
// settled by accept/cancel or by Escape/backdrop through AppDialog's close.
function present(options = {}) {
  if (pendingResolve) settle(false)
  confirmState.value = {
    open: true,
    title: options.title || '',
    body: options.body || '',
    confirmLabel: options.confirmLabel || '',
    cancelLabel: options.cancelLabel || '',
    danger: Boolean(options.danger),
  }
  return new Promise(resolve => {
    pendingResolve = resolve
  })
}

function settle(value) {
  const resolve = pendingResolve
  pendingResolve = null
  confirmState.value = {
    open: false,
    title: '',
    body: '',
    confirmLabel: '',
    cancelLabel: '',
    danger: false,
  }
  if (resolve) resolve(Boolean(value))
}

function accept() {
  settle(true)
}

function cancel() {
  settle(false)
}

onBeforeUnmount(() => settle(false))

defineExpose({ present, cancel, accept })
</script>

<style scoped>
.confirm-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
}
</style>
