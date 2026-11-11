<template>
  <div class="exam-setup-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <section class="exam-setup-dialog drafts-dialog" role="dialog" aria-modal="true" aria-labelledby="drafts-title">
      <div class="dialog-header-flex">
        <div>
          <div class="rule-label">{{ t('ep.settings.ai_area') }}</div>
          <h2 id="drafts-title">{{ t('ui.k0206') }}</h2>
          <p>{{ t('ui.k0207') }}</p>
        </div>
        <button type="button" class="btn-close-icon" :aria-label="t('ep.common.close')" @click="$emit('close')">
          <LinearIcon name="x" size="16" />
        </button>
      </div>

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

      <div class="dialog-actions">
        <button type="button" class="btn" @click="$emit('close')">{{ t('ui.k0134') }}</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { listDrafts, acceptDraft, discardDraft } from '../api/ai'
import { useLocale } from '../composables/useLocale.js'
import LinearIcon from './LinearIcon.vue'

const { t } = useLocale()

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
    alert(`${t('ui.k0285')}${err.detail || err.message}`)
  } finally {
    draft.processing = false
  }
}

async function handleDiscardDraft(draftId) {
  if (!confirm(t('ui.k0286'))) return
  try {
    await discardDraft(props.token, draftId)
    draftsList.value = draftsList.value.filter(d => d.id !== draftId)
  } catch (err) {
    alert(`${t('ui.k0287')}${err.detail || err.message}`)
  }
}
</script>

<style scoped>
.drafts-dialog { width: min(100%, 600px); gap: 0; }
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
.drafts-dialog .dialog-actions { margin-top: 4px; padding-top: 14px; border-top: 1px solid var(--line); }
</style>
