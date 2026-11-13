<template>
  <AppDialog
    :open="show"
    :title="t('ep.practice.start_blocked_title')"
    panel-class="start-study-dialog"
    style="--app-dialog-width: 460px"
    initial-focus=".start-study-continue"
    data-testid="start-study-panel"
    @close="emitCancel"
  >
    <p class="confirm-text">{{ t('ep.practice.start_blocked_desc') }}</p>
    <ul v-if="sessions.length" class="start-study-list">
      <li v-for="session in sessions" :key="session.id" class="start-study-session" data-testid="start-study-session">
        <span class="tag">{{ formatMode(session.mode) }}</span>
        <span class="start-study-bank">{{ session.bank_name }}</span>
        <span class="start-study-progress mono">{{ session.answered_count }} / {{ session.total_questions }}</span>
      </li>
    </ul>
    <template #foot>
      <button type="button" class="btn btn-quiet" data-testid="start-study-cancel" :disabled="busy" @click="emitCancel">
        {{ t('ep.common.cancel') }}
      </button>
      <button type="button" class="btn start-study-continue" data-testid="start-study-continue" :disabled="busy" @click="emit('continue')">
        {{ t('ep.practice.start_blocked_continue') }}
      </button>
      <button type="button" class="btn btn-primary" data-testid="start-study-end-and-start" :disabled="busy" @click="emit('end-and-start')">
        {{ t('ep.practice.start_blocked_end_and_start') }}
      </button>
    </template>
  </AppDialog>
</template>

<script setup>
import AppDialog from './AppDialog.vue'
import { useLocale } from '../composables/useLocale'

const props = defineProps({
  show: { type: Boolean, default: false },
  sessions: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['continue', 'end-and-start', 'cancel'])
const { t } = useLocale()

function emitCancel() {
  if (props.busy) return
  emit('cancel')
}

function formatMode(mode) {
  const map = {
    PRACTICE: t('ep.practice.mode_practice'),
    MISTAKE: t('ep.practice.mode_mistake'),
    FSRS: t('ep.practice.mode_fsrs'),
    ELIMINATION: t('ep.practice.mode_elimination'),
    EXAM: t('ep.nav.exams'),
  }
  return map[mode] || mode || ''
}
</script>

<style scoped>
.start-study-list {
  display: flex;
  flex-direction: column;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid var(--line);
}
.start-study-session {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  border-bottom: 1px solid var(--line);
}
.start-study-bank {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.start-study-progress {
  flex: none;
  color: var(--ink-3);
  font-size: 12px;
}
</style>
