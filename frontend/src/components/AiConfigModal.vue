<template>
  <div class="exam-setup-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 36rem);" aria-modal="true">
      <h2>{{ t('ui.k0257') }}</h2>
      <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
        {{ t('ui.k0258') }}
      </p>

      <div
        v-if="aiConfigNotice"
        :style="{
          padding: '0.6rem 0.8rem',
          borderRadius: '6px',
          fontSize: '0.85rem',
          marginBottom: '0.75rem',
          background: aiConfigNotice.includes(t('ui.k0259')) ? 'var(--success-light)' : 'var(--danger-light)',
          color: aiConfigNotice.includes(t('ui.k0259')) ? 'var(--success)' : 'var(--danger)'
        }"
      >
        {{ aiConfigNotice }}
      </div>

      <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1rem;">
        <label style="font-size: 0.85rem; font-weight: 500;">
          {{ t('ui.k0260') }}
          <select v-model="aiConfigForm.ai_provider" style="width: 100%; margin-top: 0.25rem;">
            <option value="openai">{{ t('ui.k0261') }}</option>
            <option value="ollama">{{ t('ui.k0262') }}</option>
          </select>
        </label>

        <label style="font-size: 0.85rem; font-weight: 500;">
          {{ t('ui.k0756') }}
          <input v-model="aiConfigForm.ai_api_base" type="text" placeholder="https://api.openai.com/v1" style="width: 100%; margin-top: 0.25rem;" />
        </label>

        <label style="font-size: 0.85rem; font-weight: 500;">
          {{ t('ui.k0263') }}
          <input v-model="aiConfigForm.ai_model" type="text" :placeholder="t('ui.k0264')" style="width: 100%; margin-top: 0.25rem;" />
        </label>

        <label style="font-size: 0.85rem; font-weight: 500;">
          {{ t('ui.k0265') }}
          <input v-model="aiConfigForm.ai_api_key" type="password" placeholder="sk-..." style="width: 100%; margin-top: 0.25rem;" />
        </label>

        <label style="font-size: 0.85rem; font-weight: 500;">
          {{ t('ui.k0266') }}
          <select v-model="aiConfigForm.search_provider" style="width: 100%; margin-top: 0.25rem;">
            <option value="open-webSearch">{{ t('ui.k0267') }}</option>
            <option value="offline">{{ t('ui.k0268') }}</option>
          </select>
        </label>

        <label v-if="aiConfigForm.search_provider === 'open-webSearch'" style="font-size: 0.85rem; font-weight: 500;">
          {{ t('ui.k0269') }}
          <input v-model="aiConfigForm.search_api_base" type="text" placeholder="http://localhost:8000/v1/search" style="width: 100%; margin-top: 0.25rem;" />
        </label>
      </div>

      <div class="bank-actions">
        <button type="button" @click="$emit('close')">{{ t('ui.k0134') }}</button>
        <button type="button" class="primary" :disabled="aiConfigLoading" @click="saveAiConfigAction">
          {{ aiConfigLoading ? t('ui.k0687') : t('ui.k0688') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getAiConfig, updateAiConfig } from '../api/ai'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({
  token: { type: String, required: true }
})

defineEmits(['close'])

const aiConfigForm = ref({
  ai_provider: 'openai',
  ai_api_base: 'https://api.openai.com/v1',
  ai_model: 'gpt-4o-mini',
  ai_api_key: '',
  search_provider: 'open-webSearch',
  search_api_key: '',
  search_api_base: 'http://localhost:8000/v1/search',
})
const aiConfigNotice = ref('')
const aiConfigLoading = ref(false)

onMounted(async () => {
  aiConfigNotice.value = ''
  try {
    const res = await getAiConfig(props.token)
    aiConfigForm.value = {
      ai_provider: res.ai_provider || 'openai',
      ai_api_base: res.ai_api_base || 'https://api.openai.com/v1',
      ai_model: res.ai_model || 'gpt-4o-mini',
      ai_api_key: res.ai_api_key || '',
      search_provider: res.search_provider || 'open-webSearch',
      search_api_key: res.search_api_key || '',
      search_api_base: res.search_api_base || 'http://localhost:8000/v1/search',
    }
  } catch (e) {
    aiConfigNotice.value = t('ui.k0319') + (e.message || e)
  }
})

async function saveAiConfigAction() {
  aiConfigLoading.value = true
  aiConfigNotice.value = ''
  try {
    const updated = await updateAiConfig(props.token, aiConfigForm.value)
    aiConfigForm.value.ai_api_key = updated.ai_api_key
    aiConfigForm.value.search_api_key = updated.search_api_key
    aiConfigNotice.value = t('ui.k0320')
  } catch (e) {
    aiConfigNotice.value = t('ui.k0321') + (e.message || e)
  } finally {
    aiConfigLoading.value = false
  }
}
</script>
