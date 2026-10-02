<template>
  <div class="exam-setup-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 46rem); max-height: 85vh; overflow-y: auto;">
      <h2>{{ t('ui.k0206') }}</h2>
      <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem;">
        {{ t('ui.k0207') }}
      </p>
      <div v-if="loadingDrafts" style="text-align: center; color: var(--text-tertiary); padding: 1.5rem;">{{ t('ui.k0208') }}</div>
      <div v-else-if="!draftsList.length" style="text-align: center; color: var(--text-tertiary); padding: 2rem;">
        {{ t('ui.k0209') }}
      </div>
      <div v-else style="display: flex; flex-direction: column; gap: 1rem;">
        <div v-for="d in draftsList" :key="d.id" style="border: 1px solid var(--border); border-radius: 8px; padding: 1rem; background: var(--bg-subtle);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <span style="font-size: 0.75rem; padding: 0.15rem 0.4rem; background: var(--primary-light); color: var(--linear-cyan); border-radius: 4px; font-weight: 600; font-family: var(--linear-mono);">
              {{ d.type }} {{ t('ui.k0210') }} {{ d.difficulty }}
            </span>
            <span style="font-size: 0.75rem; color: var(--text-tertiary);">{{ d.created_at }}</span>
          </div>
          <label style="font-size: 0.8rem; font-weight: 600;">{{ t('ui.k0211') }}
            <textarea v-model="d.stem" rows="2" style="font-size: 0.85rem; margin-top: 0.2rem;"></textarea>
          </label>
          <div v-if="d.options && d.options.length" style="margin: 0.5rem 0;">
            <span style="font-size: 0.8rem; font-weight: 600;">{{ t('ui.k0212') }}</span>
            <div v-for="(opt, idx) in d.options" :key="idx" style="display: flex; gap: 0.4rem; margin-top: 0.2rem;">
              <input v-model="opt.key" style="width: 3rem; font-size: 0.8rem;" />
              <input v-model="opt.text" style="flex: 1; font-size: 0.8rem;" />
            </div>
          </div>
          <div style="display: flex; gap: 1rem; margin-top: 0.5rem;">
            <label style="flex: 1; font-size: 0.8rem; font-weight: 600;">{{ t('ui.k0080') }}
              <input v-model="d.answer" style="font-size: 0.85rem;" />
            </label>
          </div>
          <label style="font-size: 0.8rem; font-weight: 600; margin-top: 0.5rem;">{{ t('ui.k0213') }}
            <textarea v-model="d.explanation" rows="2" style="font-size: 0.85rem; margin-top: 0.2rem;"></textarea>
          </label>
          <div style="display: flex; justify-content: flex-end; gap: 0.6rem; margin-top: 0.75rem;">
            <button type="button" style="color: var(--danger);" :disabled="d.processing" @click="handleDiscardDraft(d.id)">
              {{ t('ui.k0214') }}
            </button>
            <button type="button" class="primary" :disabled="d.processing" @click="handleAcceptDraft(d)">
              {{ d.processing ? t('ui.k0678') : t('ui.k0679') }}
            </button>
          </div>
        </div>
      </div>
      <div class="bank-actions" style="margin-top: 1rem;">
        <button type="button" @click="$emit('close')">{{ t('ui.k0134') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { listDrafts, acceptDraft, discardDraft } from '../api/ai'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({
  token: { type: String, required: true }
})

const emit = defineEmits(['close', 'accepted'])

const draftsList = ref([])
const loadingDrafts = ref(false)

onMounted(async () => {
  await fetchDrafts()
})

async function fetchDrafts() {
  loadingDrafts.value = true
  try {
    const drafts = await listDrafts(props.token, 'DRAFT')
    draftsList.value = (drafts || []).map(d => ({
      ...d,
      processing: false,
    }))
  } catch (err) {
    console.error(t('ui.k0284'), err)
  } finally {
    loadingDrafts.value = false
  }
}

async function handleAcceptDraft(draft) {
  draft.processing = true
  try {
    const modifications = {
      stem: draft.stem,
      options: draft.options,
      answer: draft.answer,
      explanation: draft.explanation,
    }
    await acceptDraft(props.token, draft.id, modifications)
    draftsList.value = draftsList.value.filter(d => d.id !== draft.id)
    emit('accepted', draft)
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
