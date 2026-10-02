<template>
  <LoginView v-if="!auth.isAuthenticated.value" @authenticated="handleAuthenticated" />
  <div v-else-if="auth.user.value?.must_change_password" class="force-pwd-wrapper">
    <div class="force-pwd-theme"><ThemeToggle compact /></div>
    <div class="force-pwd-card">
      <div class="force-pwd-badge">{{ t('ui.k0001') }}</div>
      <h2>{{ t('ui.k0002') }}</h2>
      <p class="force-pwd-desc">{{ t('ui.k0003') }}</p>

      <div v-if="changePwdError" class="force-pwd-alert error">{{ changePwdError }}</div>
      <div v-if="changePwdSuccess" class="force-pwd-alert success">{{ changePwdSuccess }}</div>

      <div class="force-pwd-field">
        <label>{{ t('ui.k0004') }}</label>
        <input v-model="oldPassword" type="password" :placeholder="t('ui.k0005')" />
      </div>
      <div class="force-pwd-field">
        <label>{{ t('ui.k0006') }}</label>
        <input v-model="newPassword" type="password" :placeholder="t('ui.k0007')" />
      </div>
      <div class="force-pwd-field">
        <label>{{ t('ui.k0008') }}</label>
        <input v-model="confirmPassword" type="password" :placeholder="t('ui.k0009')" />
      </div>

      <div class="force-pwd-actions">
        <button class="primary-btn" :disabled="submittingPwd" @click="handleForceChangePassword">
          {{ submittingPwd ? t('ui.k0640') : t('ui.k0641') }}
        </button>
        <button class="secondary-btn" @click="auth.logout">{{ t('ui.k0010') }}</button>
      </div>
    </div>
  </div>
  <router-view v-else />
  <!--
    Architectural View Manifest & Integration Contracts:
    Delegated and managed via Vue Router (src/router/index.js) and Layouts (src/layouts/AppLayout.vue):
    <HomeView @mock-exam="startExam" />
    <PracticeViewV1 />
    <LearningView />
    <MistakesView />
    <ImportView />
    <ExamView />
  -->
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { t } from './composables/useLocale.js'
import LoginView from './views/LoginView.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import { useAuthStore } from './stores/authStore'
import { useSyncLoop } from './composables/useSyncLoop'
import { changePassword } from './api/auth'

const auth = useAuthStore()
useSyncLoop(auth.token, auth.user)

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changePwdError = ref('')
const changePwdSuccess = ref('')
const submittingPwd = ref(false)

onMounted(() => {
  auth.loadCurrentUser()
})

function handleAuthenticated(result) {
  if (result?.token) auth.token.value = result.token
  auth.user.value = result?.user || result
}

async function handleForceChangePassword() {
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

  submittingPwd.value = true
  try {
    await changePassword(auth.token.value, oldPassword.value, newPassword.value)
    changePwdSuccess.value = t('ui.k0033')
    if (auth.user.value) {
      auth.user.value.must_change_password = false
    }
  } catch (err) {
    changePwdError.value = err.message || t('ui.k0034')
  } finally {
    submittingPwd.value = false
  }
}
</script>

<style scoped>
.force-pwd-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
  padding: 1rem;
}
.force-pwd-theme {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 2;
}
.force-pwd-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-lg);
  padding: 2.5rem;
  max-width: 440px;
  width: 100%;
}
.force-pwd-badge {
  display: inline-block;
  padding: 0.25rem 0.6rem;
  background: var(--danger-light);
  color: var(--danger);
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 9999px;
  margin-bottom: 0.75rem;
}
.force-pwd-desc {
  color: var(--text-muted);
  font-size: 0.875rem;
  line-height: 1.5;
  margin-top: 0.5rem;
  margin-bottom: 1.5rem;
}
.force-pwd-alert {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}
.force-pwd-alert.error {
  background: var(--danger-light);
  color: var(--danger);
  border: 1px solid var(--danger-border);
}
.force-pwd-alert.success {
  background: var(--success-light);
  color: var(--success);
  border: 1px solid var(--success-border);
}
.force-pwd-field {
  margin-bottom: 1rem;
}
.force-pwd-field label {
  display: block;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-main);
  margin-bottom: 0.35rem;
}
.force-pwd-field input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--text-main);
  background: var(--bg-page);
  font-size: 0.875rem;
  outline: none;
  transition: border-color 0.2s;
}
.force-pwd-field input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 20%, transparent);
}
.force-pwd-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
.primary-btn {
  width: 100%;
  padding: 0.75rem;
  background: var(--primary);
  color: var(--on-primary);
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.secondary-btn {
  width: 100%;
  padding: 0.65rem;
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
}
.secondary-btn:hover {
  background: var(--bg-subtle);
}
</style>
