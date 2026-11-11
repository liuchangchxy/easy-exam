<template>
  <main class="auth-layout">
    <section class="auth-brand-pane">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">易</span>
        <span class="brand-text">
          <span class="brand-name">{{ t('ep.brand.name') }}</span>
          <span class="brand-sub">{{ t('ep.brand.sub') }}</span>
        </span>
      </div>
      <div class="auth-brand-copy">
        <h1 class="auth-headline">{{ t('ep.auth.headline') }}</h1>
        <p class="auth-lede">{{ t('ep.auth.lede') }}</p>
        <div class="auth-points">
          <div class="auth-point">
            <span class="auth-point-n">01</span>
            <div><div class="auth-point-title">{{ t('ep.auth.point_private') }}</div><div class="auth-point-desc">{{ t('ep.auth.point_private_desc') }}</div></div>
          </div>
          <div class="auth-point">
            <span class="auth-point-n">02</span>
            <div><div class="auth-point-title">{{ t('ep.auth.point_shared') }}</div><div class="auth-point-desc">{{ t('ep.auth.point_shared_desc') }}</div></div>
          </div>
          <div class="auth-point">
            <span class="auth-point-n">03</span>
            <div><div class="auth-point-title">{{ t('ep.auth.point_local') }}</div><div class="auth-point-desc">{{ t('ep.auth.point_local_desc') }}</div></div>
          </div>
        </div>
      </div>
      <div class="auth-colophon"><span>{{ t('ep.brand.name') }}</span> 1.0 · {{ t('ep.brand.sub') }}</div>
    </section>

    <section class="auth-form-pane">
      <div class="auth-mobile-brand">
        <span class="brand-mark" aria-hidden="true">易</span>
        <span class="brand-name">{{ t('ep.brand.name') }}</span>
      </div>

      <div class="auth-toggles">
        <button type="button" class="icon-btn" :title="t('ep.action.language')" :aria-label="t('ep.action.language')" @click="toggleLocale">
          <LinearIcon name="globe" :size="16" />
        </button>
        <button type="button" class="icon-btn" :title="t('ep.action.theme')" :aria-label="t('ep.action.theme')" @click="toggleTheme">
          <LinearIcon :name="theme === 'dark' ? 'sun' : 'moon'" :size="16" />
        </button>
      </div>

      <div class="auth-form-wrap">
        <div class="page-eyebrow">{{ registering ? t('ep.auth.register_title') : t('ep.auth.signin_title') }}</div>
        <h2 class="auth-form-title">{{ registering ? t('ep.auth.register_title') : t('ep.auth.signin_title') }}</h2>

        <form class="auth-form" @submit.prevent="submit">
          <div class="field">
            <label class="label" for="login-username">{{ t('ep.auth.username') }}</label>
            <input
              id="login-username"
              v-model.trim="username"
              class="input"
              autocomplete="username"
              autocapitalize="off"
              autocorrect="off"
              :placeholder="t('ep.auth.username')"
              required
            />
          </div>

          <div class="field">
            <label class="label" for="login-password">{{ t('ep.auth.password') }}</label>
            <div class="auth-input-row">
              <input
                id="login-password"
                v-model="password"
                class="input"
                :type="showPassword ? 'text' : 'password'"
                :autocomplete="registering ? 'new-password' : 'current-password'"
                :placeholder="t('ep.auth.password')"
                required
                minlength="8"
              />
              <button type="button" class="link-btn auth-eye" tabindex="-1" @click="showPassword = !showPassword">
                {{ showPassword ? t('ep.auth.hide_password') : t('ep.auth.show_password') }}
              </button>
            </div>
          </div>

          <div v-if="registering" class="field">
            <label class="label" for="login-confirm">{{ t('ep.auth.confirm_password') }}</label>
            <div class="auth-input-row">
              <input
                id="login-confirm"
                v-model="confirmPassword"
                class="input"
                :type="showConfirmPassword ? 'text' : 'password'"
                autocomplete="new-password"
                :placeholder="t('ep.auth.confirm_password')"
                required
                minlength="8"
              />
              <button type="button" class="link-btn auth-eye" tabindex="-1" @click="showConfirmPassword = !showConfirmPassword">
                {{ showConfirmPassword ? t('ep.auth.hide_password') : t('ep.auth.show_password') }}
              </button>
            </div>
          </div>

          <label class="check">
            <input v-model="rememberMe" type="checkbox" />
            <span>{{ t('ep.auth.remember') }}</span>
          </label>

          <div v-if="error" class="notice bad" role="alert">
            <LinearIcon name="alert" :size="15" />
            <span>{{ errorText }}</span>
          </div>

          <button type="submit" class="btn btn-primary auth-submit" :disabled="busy">
            {{ busy ? t('ep.auth.logging_in') : (registering ? t('ep.auth.register_action') : t('ep.auth.login')) }}
          </button>
        </form>

        <div class="auth-switch">
          <span class="small dim">{{ registering ? t('ep.auth.have_account') : t('ep.auth.no_account') }}</span>
          <button type="button" class="link-btn" @click="registering = !registering">
            {{ registering ? t('ep.auth.login') : t('ep.auth.register_action') }}
          </button>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import { useTheme } from '../composables/useTheme.js'
import * as authApi from '../api/auth'

const { t, toggleLocale } = useLocale()
const { theme, toggleTheme } = useTheme()

const emit = defineEmits(['authenticated'])
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const registering = ref(false)
const busy = ref(false)
const error = ref(null)
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const rememberMe = ref(true)

const errorText = computed(() => {
  if (error.value?.translationKey) return t(error.value.translationKey)
  if (error.value instanceof Error) return error.value.message
  return error.value || ''
})

async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''

  if (registering.value) {
    if (!confirmPassword.value) {
      error.value = { translationKey: 'ep.auth.confirm_required' }
      busy.value = false
      return
    }
    if (confirmPassword.value !== password.value) {
      error.value = { translationKey: 'ep.auth.password_mismatch' }
      busy.value = false
      return
    }
  }
  if (password.value.length < 8) {
    error.value = { translationKey: 'ep.auth.password_too_short' }
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
    error.value = err instanceof Error ? err : new Error(t('ep.auth.error_required'))
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.auth-form-wrap {
  width: min(100%, 360px);
}

.auth-form-title {
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 600;
  letter-spacing: .01em;
  margin: 8px 0 26px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.auth-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.auth-eye {
  flex: none;
  font-size: 11.5px;
  color: var(--ink-3);
}

.auth-submit {
  width: 100%;
  min-height: 40px;
  margin-top: 6px;
}

.auth-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.auth-toggles {
  position: absolute;
  top: 18px;
  right: 22px;
  display: flex;
  gap: 2px;
}

.auth-brand-copy { max-width: 520px; }
.auth-points { margin-top: 40px; display: flex; flex-direction: column; }
.auth-point {
  display: flex;
  gap: 16px;
  padding: 16px 0;
  border-top: 1px solid color-mix(in srgb, var(--brand-contrast) 18%, transparent);
}
.auth-point-n {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: color-mix(in srgb, var(--brand-contrast) 62%, transparent);
  padding-top: 2px;
}
.auth-point-title { font-size: 13.5px; font-weight: 600; }
.auth-point-desc { font-size: 12.5px; line-height: 1.6; opacity: .72; margin-top: 2px; }
.auth-colophon {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: .06em;
  opacity: .55;
}
</style>
