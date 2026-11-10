<template>
  <div class="exam-setup-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <section class="exam-setup-dialog ai-config-dialog" role="dialog" aria-modal="true" aria-labelledby="ai-config-title">
      <div class="dialog-header-flex">
        <div>
          <div class="rule-label">{{ t('ep.settings.ai_area') }}</div>
          <h2 id="ai-config-title">{{ t('ui.k0257') }}</h2>
          <p>{{ t('ui.k0258') }}</p>
        </div>
        <button type="button" class="btn-close-icon" :aria-label="t('ep.common.close')" @click="$emit('close')">
          <LinearIcon name="x" size="16" />
        </button>
      </div>

      <div v-if="aiConfigNotice" class="notice" :class="aiConfigNoticeIsError ? 'bad' : 'ok'">
        {{ aiConfigNotice }}
      </div>

      <div class="ai-config-status" :class="{ 'is-ready': aiConfigured }">
        {{ aiConfigured ? t('ep.settings.ai_configured') : t('ep.settings.ai_unconfigured') }}
      </div>

      <div class="ai-config-form">
        <label class="field">
          <span class="label">{{ t('ui.k0260') }}</span>
          <select v-model="aiConfigForm.ai_provider" class="select">
            <option value="openai">{{ t('ui.k0261') }}</option>
            <option value="ollama">{{ t('ui.k0262') }}</option>
          </select>
        </label>

        <label class="field">
          <span class="label">{{ t('ui.k0756') }}</span>
          <input v-model="aiConfigForm.ai_api_base" class="input" type="text" placeholder="https://api.openai.com/v1" />
        </label>

        <div class="field-row">
          <label class="field">
            <span class="label">{{ t('ui.k0263') }}</span>
            <input v-model="aiConfigForm.ai_model" class="input" type="text" :placeholder="t('ui.k0264')" />
          </label>
          <label class="field">
            <span class="label">{{ t('ui.k0265') }}</span>
            <input v-model="aiConfigForm.ai_api_key" class="input" type="password" placeholder="sk-..." />
          </label>
        </div>

        <label class="field">
          <span class="label">{{ t('ui.k0266') }}</span>
          <select v-model="aiConfigForm.search_provider" class="select">
            <option value="open-webSearch">{{ t('ui.k0267') }}</option>
            <option value="offline">{{ t('ui.k0268') }}</option>
          </select>
        </label>

        <label v-if="aiConfigForm.search_provider === 'open-webSearch'" class="field">
          <span class="label">{{ t('ui.k0269') }}</span>
          <input v-model="aiConfigForm.search_api_base" class="input" type="text" placeholder="http://localhost:8000/v1/search" />
        </label>

        <label v-if="aiConfigForm.search_provider === 'open-webSearch'" class="field">
          <span class="label">{{ t('ep.settings.web_key') }}</span>
          <input v-model="aiConfigForm.search_api_key" class="input" type="password" :placeholder="t('ep.settings.ai_key_placeholder')" />
        </label>
      </div>

      <div class="dialog-actions">
        <button type="button" class="btn" @click="$emit('close')">{{ t('ui.k0134') }}</button>
        <button type="button" class="btn btn-primary" :disabled="aiConfigLoading" @click="saveAiConfigAction">
          {{ aiConfigLoading ? t('ui.k0687') : t('ui.k0688') }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getAiConfig, updateAiConfig } from '../api/ai'
import LinearIcon from './LinearIcon.vue'
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
const aiConfigNoticeIsError = ref(false)
const aiConfigured = ref(false)
const aiConfigLoading = ref(false)

onMounted(async () => {
  aiConfigNotice.value = ''
  aiConfigNoticeIsError.value = false
  try {
    const res = await getAiConfig(props.token)
    aiConfigured.value = Boolean(res.is_configured)
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
    aiConfigNoticeIsError.value = true
    aiConfigNotice.value = t('ui.k0319') + (e.detail || e.message || e)
  }
})

async function saveAiConfigAction() {
  aiConfigLoading.value = true
  aiConfigNotice.value = ''
  aiConfigNoticeIsError.value = false
  try {
    const updated = await updateAiConfig(props.token, aiConfigForm.value)
    aiConfigForm.value.ai_api_key = updated.ai_api_key ?? ''
    aiConfigForm.value.search_api_key = updated.search_api_key ?? ''
    aiConfigured.value = Boolean(updated.is_configured)
    aiConfigNotice.value = t('ui.k0320')
  } catch (e) {
    aiConfigNoticeIsError.value = true
    aiConfigNotice.value = t('ui.k0321') + (e.detail || e.message || e)
  } finally {
    aiConfigLoading.value = false
  }
}
</script>

<style scoped>
.ai-config-dialog { width: min(100%, 500px); gap: 0; }
.ai-config-form { display: flex; flex-direction: column; gap: 12px; }
.ai-config-status { margin: 2px 0 10px; font-size: 11.5px; color: var(--ink-3); }
.ai-config-status.is-ready { color: var(--ok); }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ai-config-dialog .dialog-actions { margin-top: 4px; padding-top: 14px; border-top: 1px solid var(--line); }
@media (max-width: 480px) { .field-row { grid-template-columns: 1fr; } }
</style>
