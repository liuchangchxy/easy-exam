<template>
  <div class="exam-setup-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <div class="exam-setup-dialog change-pwd-dialog" role="dialog" aria-modal="true" style="width: min(100%, 30rem);">
      <div class="change-pwd-header">
        <div class="change-pwd-badge">
          <LinearIcon name="key" size="14" />
          <span>{{ t('ui.k0001') }}</span>
        </div>
        <h2>{{ t('ui.k0002') }}</h2>
        <p class="change-pwd-desc">{{ t('ui.k0003') }}</p>
      </div>

      <div v-if="changePwdError" class="alert-box error">{{ changePwdError }}</div>
      <div v-if="changePwdSuccess" class="alert-box success">{{ changePwdSuccess }}</div>

      <form @submit.prevent="handleSubmit">
        <div class="form-field">
          <label>{{ t('ui.k0004') }}</label>
          <input v-model="oldPassword" type="password" :placeholder="t('ui.k0005')" required autocomplete="current-password" />
        </div>
        <div class="form-field">
          <label>{{ t('ui.k0006') }}</label>
          <input v-model="newPassword" type="password" :placeholder="t('ui.k0007')" required minlength="8" autocomplete="new-password" />
        </div>
        <div class="form-field">
          <label>{{ t('ui.k0008') }}</label>
          <input v-model="confirmPassword" type="password" :placeholder="t('ui.k0009')" required minlength="8" autocomplete="new-password" />
        </div>

        <div class="dialog-actions">
          <button type="button" class="secondary-btn" @click="$emit('close')">{{ t('common.cancel') }}</button>
          <button type="submit" class="primary-btn" :disabled="submitting">
            {{ submitting ? t('ui.k0640') : t('ui.k0641') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { changePassword } from '../api/auth'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({
  token: { type: String, required: true }
})

const emit = defineEmits(['close', 'success'])

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changePwdError = ref('')
const changePwdSuccess = ref('')
const submitting = ref(false)

async function handleSubmit() {
  changePwdError.value = ''
  changePwdSuccess.value = ''
  if (!oldPassword.value) {
    changePwdError.value = t('ui.k0030')
    return
  }
  if (!newPassword.value || newPassword.value.length < 8) {
    changePwdError.value = t('ui.k0031')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    changePwdError.value = t('ui.k0032')
    return
  }

  submitting.value = true
  try {
    await changePassword(props.token, oldPassword.value, newPassword.value)
    changePwdSuccess.value = t('ui.k0033')
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    emit('success')
    setTimeout(() => {
      emit('close')
    }, 1200)
  } catch (err) {
    changePwdError.value = err.message || t('ui.k0034')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.change-pwd-header {
  margin-bottom: 1.25rem;
}

.change-pwd-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.change-pwd-header h2 {
  margin: 0 0 0.35rem;
  font-size: 1.25rem;
  color: var(--text-main);
}

.change-pwd-desc {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.form-field label {
  font-size: 0.825rem;
  font-weight: 500;
  color: var(--text-main);
}

.form-field input {
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--bg-card);
  color: var(--text-main);
  font-size: 0.9rem;
}

.form-field input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-light);
}

.alert-box {
  padding: 0.65rem 0.85rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

.alert-box.error {
  background: var(--danger-light);
  color: var(--danger);
  border: 1px solid var(--danger-border);
}

.alert-box.success {
  background: var(--success-light);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.28);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
  border-top: 1px solid var(--border);
  padding-top: 1rem;
}

.primary-btn {
  padding: 0.5rem 1.2rem;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 120ms ease;
}

.primary-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary-btn {
  padding: 0.5rem 1rem;
  background: transparent;
  color: var(--text-main);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  cursor: pointer;
}
</style>
