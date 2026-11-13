<template>
  <LoginView v-if="!auth.isAuthenticated.value" @authenticated="handleAuthenticated" />
  <div v-else-if="auth.user.value?.must_change_password" class="force-pwd-wrapper">
    <div class="force-pwd-theme">
      <ThemeToggle compact />
    </div>
    <div class="force-pwd-card">
      <div class="brand" style="margin-bottom: 28px">
        <span class="brand-mark" aria-hidden="true">易</span>
        <span class="brand-text">
          <span class="brand-name">{{ t('ep.brand.name') }}</span>
          <span class="brand-sub">{{ t('ep.brand.sub') }}</span>
        </span>
      </div>
      <div class="page-eyebrow">{{ t('ep.auth.force_title') }}</div>
      <h2 class="force-pwd-title">{{ t('ep.auth.force_title') }}</h2>
      <p class="force-pwd-desc">{{ t('ep.auth.force_lede') }}</p>

      <div v-if="changePwdError" class="notice bad" role="alert">{{ changePwdError }}</div>

      <div class="field">
        <label class="label" for="force-old">{{ t('ep.auth.old_password') }}</label>
        <input id="force-old" v-model="oldPassword" class="input" type="password" :placeholder="t('ep.auth.old_password')" />
      </div>
      <div class="field">
        <label class="label" for="force-new">{{ t('ep.auth.new_password') }}</label>
        <input id="force-new" v-model="newPassword" class="input" type="password" :placeholder="t('ep.auth.new_password')" />
        <div class="hint">{{ t('ep.auth.password_rule') }}</div>
      </div>
      <div class="field">
        <label class="label" for="force-confirm">{{ t('ep.auth.confirm_password') }}</label>
        <input id="force-confirm" v-model="confirmPassword" class="input" type="password" :placeholder="t('ep.auth.confirm_password')" />
      </div>

      <div class="force-pwd-actions">
        <button type="button" class="btn btn-primary" :disabled="submittingPwd" @click="handleForceChangePassword">
          {{ submittingPwd ? t('ep.auth.changing_password') : t('ep.auth.change_password') }}
        </button>
        <button type="button" class="btn btn-quiet" @click="auth.logout">{{ t('ep.account.logout') }}</button>
      </div>
    </div>
  </div>
  <router-view v-else />

  <!-- The two app-wide control surfaces, mounted once. ConfirmHost registers
       the dialog presenter; ToastHost owns the single transient channel. -->
  <ConfirmHost ref="confirmHostRef" />
  <ToastHost />
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { t } from './composables/useLocale.js'
import LoginView from './views/LoginView.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import ConfirmHost from './components/ConfirmHost.vue'
import ToastHost from './components/ToastHost.vue'
import { useAuthStore } from './stores/authStore'
import { useSyncLoop } from './composables/useSyncLoop'
import { changePassword } from './api/auth'
import { useToast } from './composables/useToast'
import { setConfirmPresenter, setNoticePresenter } from './composables/useConfirm'

const auth = useAuthStore()
useSyncLoop(auth.token, auth.user)
const toast = useToast()
const confirmHostRef = ref(null)

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changePwdError = ref('')
const submittingPwd = ref(false)

onMounted(() => {
  auth.loadCurrentUser()
  // From here on, confirmations render as the editorial dialog and blocking
  // notices as error toasts. Without this registration the composable falls
  // back to the native dialogs (as it does in single-view component tests).
  setConfirmPresenter(options => confirmHostRef.value?.present(options) ?? false)
  setNoticePresenter(options => toast.error(options.title))
})

function handleAuthenticated(result) {
  if (result?.token) auth.token.value = result.token
  auth.user.value = result?.user || result
}

async function handleForceChangePassword() {
  changePwdError.value = ''
  if (!oldPassword.value) {
    changePwdError.value = t('ep.auth.error_required')
    return
  }
  if (!newPassword.value || newPassword.value.length < 8) {
    changePwdError.value = t('ep.auth.password_rule')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    changePwdError.value = t('ep.auth.password_mismatch')
    return
  }

  submittingPwd.value = true
  try {
    await changePassword(auth.token.value, oldPassword.value, newPassword.value)
    toast.success(t('ui.k0033'))
    if (auth.user.value) auth.user.value.must_change_password = false
  } catch (err) {
    changePwdError.value = err.message || t('common.error')
  } finally {
    submittingPwd.value = false
  }
}
</script>

<style scoped>
.force-pwd-wrapper {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: var(--paper);
  padding: 24px;
}

.force-pwd-theme {
  position: fixed;
  top: 18px;
  right: 22px;
  z-index: 2;
}

.force-pwd-card {
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-2);
  padding: 32px;
  max-width: 420px;
  width: 100%;
}

.force-pwd-title {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 600;
  margin: 4px 0 8px;
}

.force-pwd-desc {
  color: var(--ink-3);
  font-size: 13px;
  line-height: 1.7;
  margin: 0 0 20px;
}

.force-pwd-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 22px;
}

.force-pwd-actions .btn { height: 38px; }
</style>
