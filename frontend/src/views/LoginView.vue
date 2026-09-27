<template>
  <main class="auth-page">
    <div class="auth-background-decoration"></div>
    <section class="auth-card">
      <div class="auth-brand">
        <div class="brand-logo">📚</div>
        <h1>易考宝</h1>
        <p class="brand-sub">私有云刷题与错题消灭系统</p>
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <div class="form-group">
          <label class="field-label">用户名</label>
          <div class="input-wrapper">
            <input
              v-model.trim="username"
              autocomplete="username"
              autocapitalize="off"
              autocorrect="off"
              placeholder="用户名"
              required
            />
          </div>
        </div>

        <div class="form-group">
          <label class="field-label">密码</label>
          <div class="input-wrapper has-trailing-action">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              :autocomplete="registering ? 'new-password' : 'current-password'"
              placeholder="密码（至少 8 位）"
              required
              minlength="8"
            />
            <button
              type="button"
              class="btn-toggle-eye"
              tabindex="-1"
              :title="showPassword ? '隐藏密码' : '显示明文密码'"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? '🙈' : '👁️' }}
            </button>
          </div>
        </div>

        <div v-if="registering" class="form-group">
          <label class="field-label">确认密码</label>
          <div class="input-wrapper has-trailing-action">
            <input
              v-model="confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              autocomplete="new-password"
              placeholder="请再次输入密码以确认"
            />
            <button
              type="button"
              class="btn-toggle-eye"
              tabindex="-1"
              :title="showConfirmPassword ? '隐藏密码' : '显示明文密码'"
              @click="showConfirmPassword = !showConfirmPassword"
            >
              {{ showConfirmPassword ? '🙈' : '👁️' }}
            </button>
          </div>
        </div>

        <div class="auth-options-row">
          <label class="remember-label">
            <input type="checkbox" v-model="rememberMe" />
            <span>保持登录状态（30天免登录）</span>
          </label>
        </div>

        <div v-if="error" class="error-banner">
          <span class="error-icon">⚠️</span>
          <span class="error-text">{{ error }}</span>
        </div>

        <button type="submit" class="primary-btn submit-btn" :disabled="busy">
          {{ busy ? '处理中…' : (registering ? '注册并登录' : '登录') }}
        </button>
      </form>

      <div class="auth-footer-toggle">
        <button class="link-button" type="button" @click="registering = !registering">
          {{ registering ? '已有账号？登录' : '首次使用？创建账号' }}
        </button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import * as authApi from '../api/auth'

const emit = defineEmits(['authenticated'])
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const registering = ref(false)
const busy = ref(false)
const error = ref('')
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
    error.value = '两次输入的密码不一致，请重新核对'
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
    error.value = err.detail || err.message || '操作失败，请检查账号密码'
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
  background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
  padding: 1.5rem;
  position: relative;
  overflow: hidden;
}

.auth-card {
  width: 100%;
  max-width: 25rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
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
  color: #0f172a;
  margin: 0 0 0.25rem 0;
  letter-spacing: -0.02em;
}

.brand-sub {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0;
}

.auth-tab-switch {
  display: flex;
  background: #f1f5f9;
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
  color: #64748b;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn.active {
  background: #ffffff;
  color: #2563eb;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
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
  color: #334155;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-wrapper input {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border: 1px solid #cbd5e1;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  color: #0f172a;
  background: #f8fafc;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.input-wrapper input:focus {
  outline: none;
  border-color: #3b82f6;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
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
  color: #475569;
  cursor: pointer;
  user-select: none;
}

.remember-label input[type="checkbox"] {
  cursor: pointer;
  accent-color: #2563eb;
  width: 1rem;
  height: 1rem;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 0.5rem;
  color: #dc2626;
  font-size: 0.825rem;
}

.submit-btn {
  width: 100%;
  padding: 0.75rem;
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.1s ease;
  margin-top: 0.25rem;
}

.submit-btn:hover:not(:disabled) {
  background: #1d4ed8;
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
  border-top: 1px solid #f1f5f9;
}

.link-button {
  border: none;
  background: transparent;
  color: #2563eb;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
}

.link-button:hover {
  text-decoration: underline;
}
</style>
