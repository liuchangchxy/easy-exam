<template>
  <AppDialog
    :open="true"
    :title="t('ui.k0206')"
    panel-class="exam-setup-dialog drafts-dialog"
    style="--app-dialog-width: 600px"
    @close="$emit('close')"
  >
    <template #head>
      <div class="drafts-head">
        <div class="rule-label">{{ t('ep.settings.ai_area') }}</div>
        <h2 id="drafts-title">{{ t('ui.k0206') }}</h2>
        <p>{{ t('ui.k0207') }}</p>
      </div>
    </template>

    <div v-if="loadingDrafts" class="drafts-state">{{ t('ui.k0208') }}</div>
    <div v-else-if="loadError" class="drafts-state drafts-error" role="alert">
      <span>{{ loadError }}</span>
      <button type="button" class="btn btn-sm" @click="fetchDrafts">{{ t('ep.common.retry') }}</button>
    </div>
    <div v-else-if="!draftsList.length" class="drafts-state">{{ t('ui.k0209') }}</div>

    <div v-else class="drafts-list">
      <article v-for="d in draftsList" :key="d.id" class="draft-row">
        <header class="draft-head">
          <span class="draft-kind mono">{{ d.type }} · {{ t('ep.banks.difficulty') }} {{ d.difficulty }}</span>
          <span class="draft-time">{{ d.created_at }}</span>
        </header>

        <div class="draft-bank">
          <span class="label">{{ t('ep.library.target_bank') }}</span>
          <span class="draft-bank-name">{{ d.target_bank_name || t('ep.common.none') }}</span>
        </div>

        <label class="field">
          <span class="label">{{ t('ui.k0211') }}</span>
          <textarea v-model="d.stem" class="textarea" rows="2"></textarea>
        </label>

        <div v-if="d.options && d.options.length" class="field">
          <span class="label">{{ t('ui.k0212') }}</span>
          <div v-for="(opt, idx) in d.options" :key="idx" class="draft-option-row">
            <input v-model="opt.key" class="input draft-opt-key mono" :aria-label="t('ep.practice.edit_option_key')" />
            <input v-model="opt.text" class="input" :aria-label="t('ep.practice.edit_option_text')" />
          </div>
        </div>

        <div class="draft-grid">
          <label class="field">
            <span class="label">{{ t('ui.k0080') }}</span>
            <input v-model="d.answer" class="input" />
          </label>
        </div>

        <label class="field">
          <span class="label">{{ t('ui.k0213') }}</span>
          <textarea v-model="d.explanation" class="textarea" rows="2"></textarea>
        </label>

        <p v-if="!d.can_manage" class="draft-locked">{{ t('ep.library.draft_bank_locked') }}</p>

        <footer class="draft-actions">
          <button type="button" class="btn btn-sm btn-quiet draft-discard" :disabled="d.processing" @click="handleDiscardDraft(d.id)">
            {{ t('ui.k0214') }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-primary"
            :disabled="d.processing || !d.can_manage"
            @click="handleAcceptDraft(d)"
          >
            {{ d.processing ? t('ui.k0678') : t('ui.k0679') }}
          </button>
        </footer>
      </article>
    </div>

    <template #foot>
      <button type="button" class="btn" @click="$emit('close')">{{ t('ui.k0134') }}</button>
    </template>
  </AppDialog>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AppDialog from './AppDialog.vue'
import { listDrafts, acceptDraft, discardDraft } from '../api/ai'
import { useLocale } from '../composables/useLocale.js'
import { useConfirm } from '../composables/useConfirm.js'

const { t } = useLocale()
const { confirm: confirmAction, notify } = useConfirm()

const props = defineProps({
  token: { type: String, required: true },
  bankId: { type: String, default: '' },
})

const emit = defineEmits(['close', 'accepted'])

const draftsList = ref([])
const loadingDrafts = ref(false)
const loadError = ref('')

onMounted(async () => {
  await fetchDrafts()
})

async function fetchDrafts() {
  loadingDrafts.value = true
  loadError.value = ''
  try {
    const drafts = await listDrafts(props.token, 'DRAFT', props.bankId)
    draftsList.value = (drafts || []).map(d => ({
      ...d,
      processing: false,
      can_manage: Boolean(d.can_manage),
    }))
  } catch (err) {
    draftsList.value = []
    loadError.value = `${t('ui.k0284')}${err.detail || err.message}`
  } finally {
    loadingDrafts.value = false
  }
}

async function handleAcceptDraft(draft) {
  if (!draft.can_manage) return
  draft.processing = true
  try {
    const modifications = {
      stem: draft.stem,
      options: draft.options,
      answer: draft.answer,
      explanation: draft.explanation,
    }
    const result = await acceptDraft(props.token, draft.id, modifications)
    draftsList.value = draftsList.value.filter(d => d.id !== draft.id)
    emit('accepted', result?.question || draft)
  } catch (err) {
    notify({ title: `${t('ui.k0285')}${err.detail || err.message}`, danger: true })
  } finally {
    draft.processing = false
  }
}

async function handleDiscardDraft(draftId) {
  const accepted = await confirmAction({ title: t('ui.k0286'), danger: true }, () => true)
  if (accepted !== true) return
  try {
    await discardDraft(props.token, draftId)
    draftsList.value = draftsList.value.filter(d => d.id !== draftId)
  } catch (err) {
    notify({ title: `${t('ui.k0287')}${err.detail || err.message}`, danger: true })
  }
}
</script>

<style scoped>
.drafts-state { padding: 40px 16px; text-align: center; color: var(--ink-4); font-size: 12.5px; }
.drafts-error { display: flex; flex-direction: column; align-items: center; gap: 12px; color: var(--bad); }
.drafts-list { display: flex; flex-direction: column; }
.draft-row { padding: 16px 0; border-bottom: 1px solid var(--line); display: flex; flex-direction: column; gap: 10px; }
.draft-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.draft-kind { font-size: 10.5px; color: var(--ink-3); letter-spacing: .04em; }
.draft-time { font-size: 10.5px; color: var(--ink-4); }
.draft-bank { display: flex; align-items: baseline; gap: 8px; font-size: 11.5px; color: var(--ink-2); }
.draft-bank .label { margin: 0; }
.draft-bank-name { color: var(--ink); }
.draft-locked { margin: 0; font-size: 11.5px; color: var(--bad); }
.draft-option-row { display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 6px; margin-top: 6px; }
.draft-opt-key { text-align: center; }
.draft-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
.draft-actions { display: flex; justify-content: flex-end; gap: 8px; }
.draft-discard { color: var(--bad); }
/* AppDialog owns the modal behaviour; keep the legacy box metrics and the
   border-only panel the drafts list has always used. */
:global(.app-dialog-panel.drafts-dialog) {
  width: min(100%, 600px);
  padding: 0;
  gap: 0;
  overflow: hidden;
}
:global(.app-dialog-panel.drafts-dialog .app-dialog-head) {
  padding: 22px 22px 0;
  border-bottom: 0;
}
:global(.app-dialog-panel.drafts-dialog .app-dialog-body) {
  padding: 0 22px 6px;
}
:global(.app-dialog-panel.drafts-dialog .app-dialog-foot) {
  padding: 12px 22px 18px;
}
</style>
