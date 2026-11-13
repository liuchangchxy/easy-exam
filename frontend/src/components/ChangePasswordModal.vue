<template>
  <AppDialog
    :open="true"
    :title="t('ui.k0002')"
    panel-class="exam-setup-dialog change-pwd-dialog"
    style="--app-dialog-width: 430px"
    initial-focus="#change-pwd-old"
    @close="$emit('close')"
  >
    <template #head>
      <div class="change-pwd-head">
        <div class="rule-label">{{ t('ui.k0001') }}</div>
        <h2 id="change-pwd-title">{{ t('ui.k0002') }}</h2>
        <p class="change-pwd-desc">{{ t('ui.k0003') }}</p>
      </div>
    </template>

    <div v-if="changePwdError" class="notice bad" role="alert">{{ changePwdError }}</div>
    <div v-if="changePwdSuccess" class="notice ok">{{ changePwdSuccess }}</div>

    <form class="change-pwd-form" @submit.prevent="handleSubmit">
      <label class="field">
        <span class="label">{{ t('ui.k0004') }}</span>
        <input id="change-pwd-old" v-model="oldPassword" class="input" type="password" :placeholder="t('ui.k0005')" required autocomplete="current-password" />
      </label>
      <label class="field">
        <span class="label">{{ t('ui.k0006') }}</span>
        <input id="change-pwd-new" v-model="newPassword" class="input" type="password" :placeholder="t('ui.k0007')" required minlength="8" autocomplete="new-password" />
      </label>
      <label class="field">
        <span class="label">{{ t('ui.k0008') }}</span>
        <input id="change-pwd-confirm" v-model="confirmPassword" class="input" type="password" :placeholder="t('ui.k0009')" required minlength="8" autocomplete="new-password" />
      </label>

      <div class="dialog-actions-row">
        <button type="button" class="btn" @click="$emit('close')">{{ t('common.cancel') }}</button>
        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? t('ui.k0640') : t('ui.k0641') }}
        </button>
      </div>
    </form>
  </AppDialog>
</template>

<script setup>
import { ref } from 'vue'
import AppDialog from './AppDialog.vue'
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
.change-pwd-head h2 {
  margin: 3px 0 6px;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 600;
}
.change-pwd-desc { margin: 0; color: var(--ink-3); font-size: 12.5px; line-height: 1.65; }
.change-pwd-form { display: flex; flex-direction: column; gap: 12px; margin-top: 18px; }
.dialog-actions-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
/* AppDialog owns the modal behaviour; keep the legacy box metrics and the
   border-only panel the password form has always used. */
:global(.app-dialog-panel.change-pwd-dialog) {
  width: min(100%, 430px);
  padding: 0;
  gap: 0;
  overflow: hidden;
}
:global(.app-dialog-panel.change-pwd-dialog .app-dialog-head) {
  padding: 22px 24px 0;
  border-bottom: 0;
}
:global(.app-dialog-panel.change-pwd-dialog .app-dialog-body) {
  padding: 0 24px 20px;
}
</style>
