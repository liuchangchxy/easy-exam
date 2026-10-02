<template>
  <main class="auth-page">
    <div class="auth-theme-switch" style="display: flex; gap: 0.5rem;"><ThemeToggle compact /><LocaleToggle compact /></div>
    <div class="auth-background-decoration"></div>
    <section class="auth-card">
      <div class="auth-brand">
        <div class="brand-logo">
          <LinearIcon name="zap" size="24" />
        </div>
        <h1>{{ t('app.name') }}</h1>
        <p class="brand-sub">{{ t('app.subtitle') }}</p>
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <div class="form-group">
          <label class="field-label">{{ t('ui.k0463') }}</label>
          <div class="input-wrapper">
            <input
              v-model.trim="username"
              autocomplete="username"
              autocapitalize="off"
              autocorrect="off"
              :placeholder="t('ui.k0463')"
              required
            />
          </div>
        </div>

        <div class="form-group">
          <label class="field-label">{{ t('ui.k0464') }}</label>
          <div class="input-wrapper has-trailing-action">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              :autocomplete="registering ? 'new-password' : 'current-password'"
              :placeholder="t('ui.k0465')"
              required
              minlength="8"
            />
            <button
              type="button"
              class="btn-toggle-eye"
              tabindex="-1"
              :title="showPassword ? t('ui.k0466') : t('ui.k0467')"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? t('ui.k0710') : t('ui.k0711') }}
            </button>
          </div>
        </div>

        <div v-if="registering" class="form-group">
          <label class="field-label">{{ t('ui.k0468') }}</label>
          <div class="input-wrapper has-trailing-action">
            <input
              v-model="confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              autocomplete="new-password"
              :placeholder="t('ui.k0469')"
            />
            <button
              type="button"
              class="btn-toggle-eye"
              tabindex="-1"
              :title="showConfirmPassword ? t('ui.k0466') : t('ui.k0467')"
              @click="showConfirmPassword = !showConfirmPassword"
            >
              {{ showConfirmPassword ? t('ui.k0710') : t('ui.k0711') }}
            </button>
          </div>
        </div>

        <div class="auth-options-row">
          <label class="remember-label">
            <input type="checkbox" v-model="rememberMe" />
            <span>{{ t('ui.k0470') }}</span>
          </label>
        </div>

        <div v-if="error" class="error-banner">
          <span class="error-icon">⚠️</span>
          <span class="error-text">{{ errorText }}</span>
        </div>

        <button type="submit" class="primary-btn submit-btn" :disabled="busy">
          {{ busy ? t('ui.k0712') : (registering ? t('ui.k0713') : t('ui.k0714')) }}
        </button>
      </form>

      <div class="auth-footer-toggle">
        <button class="link-button" type="button" @click="registering = !registering">
          {{ registering ? t('ui.k0715') : t('ui.k0716') }}
        </button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import LocaleToggle from '../components/LocaleToggle.vue'
import { useLocale } from '../composables/useLocale.js'
import * as authApi from '../api/auth'

const { t } = useLocale()

const emit = defineEmits(['authenticated'])
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const registering = ref(false)
const busy = ref(false)
const error = ref(null)
const errorText = computed(() => {
  if (error.value?.translationKey) return t(error.value.translationKey)
  if (error.value instanceof Error) return error.value.message
  return error.value || ''
})
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const rememberMe = ref(true)

function switchToLogin() {
  registering.value = false
  error.value = ''
}

function switchToRegister() {
  registering.value = true
  error.value = ''
}

async function submit() {
  busy.value = true
  error.value = ''

  if (registering.value && confirmPassword.value && confirmPassword.value !== password.value) {
    error.value = { translationKey: 'ui.k0471' }
    busy.value = false
    return
  }

  try {
    if (registering.value) {
      await authApi.register(username.value, password.value)
    }
    const result = await authApi.login(username.value, password.value)
    const targetStorage = rememberMe.value ? localStorage : sessionStorage
    targetStorage.setItem('easyexam_token', result.token)
    try {
      targetStorage.setItem('easyexam_user', JSON.stringify(result.user))
    } catch (_) {}

    if (!rememberMe.value && typeof localStorage !== 'undefined') {
      localStorage.removeItem('easyexam_token')
      localStorage.removeItem('easyexam_user')
    }

    emit('authenticated', result)
  } catch (err) {
    error.value = err instanceof Error ? err : new Error(t('ui.k0472'))
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
  padding: 1.5rem;
  position: relative;
  overflow: hidden;
}

.auth-theme-switch {
  position: absolute;
  top: 1rem;
  right: 1rem;
  z-index: 2;
}

.auth-card {
  width: 100%;
  max-width: 25rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 1rem;
  box-shadow: var(--shadow-lg);
  padding: 2.25rem 2rem;
  position: relative;
  z-index: 1;
}

.auth-brand {
  text-align: center;
  margin-bottom: 1.5rem;
}

.brand-logo {
  font-size: 2.5rem;
  line-height: 1;
  margin-bottom: 0.5rem;
}

.auth-brand h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-main);
  margin: 0 0 0.25rem 0;
  letter-spacing: -0.02em;
}

.brand-sub {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin: 0;
}

.auth-tab-switch {
  display: flex;
  background: var(--bg-subtle);
  border-radius: 0.5rem;
  padding: 0.25rem;
  margin-bottom: 1.5rem;
  gap: 0.25rem;
}

.tab-btn {
  flex: 1;
  border: none;
  background: transparent;
  padding: 0.5rem 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-muted);
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn.active {
  background: var(--bg-card);
  color: var(--primary);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-label {
  font-size: 0.825rem;
  font-weight: 600;
  color: var(--text-main);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-wrapper input {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-strong);
  border-radius: 0.5rem;
  font-size: 0.95rem;
  color: var(--text-main);
  background: var(--bg-page);
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.input-wrapper input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 20%, transparent);
}

.input-wrapper.has-trailing-action input {
  padding-right: 2.5rem;
}

.btn-toggle-eye {
  position: absolute;
  right: 0.5rem;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.35rem;
  font-size: 1.1rem;
  line-height: 1;
  border-radius: 0.25rem;
  opacity: 0.7;
  transition: opacity 0.15s;
}

.btn-toggle-eye:hover {
  opacity: 1;
}

.auth-options-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: -0.25rem;
}

.remember-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.825rem;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
}

.remember-label input[type="checkbox"] {
  cursor: pointer;
  accent-color: var(--primary);
  width: 1rem;
  height: 1rem;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: 0.5rem;
  color: var(--danger);
  font-size: 0.825rem;
}

.submit-btn {
  width: 100%;
  padding: 0.75rem;
  background: var(--primary);
  color: var(--on-primary);
  border: none;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.1s ease;
  margin-top: 0.25rem;
}

.submit-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}

.submit-btn:active:not(:disabled) {
  transform: scale(0.99);
}

.submit-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.auth-footer-toggle {
  text-align: center;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
}

.link-button {
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
}

.link-button:hover {
  text-decoration: underline;
}
</style>
