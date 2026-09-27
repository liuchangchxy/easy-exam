import { computed, ref } from 'vue'
import * as authApi from '../api/auth'

function getStoredItem(key) {
  try {
    if (typeof localStorage !== 'undefined') {
      const val = localStorage.getItem(key)
      if (val) return val
    }
    if (typeof sessionStorage !== 'undefined') {
      return sessionStorage.getItem(key)
    }
  } catch (_) {}
  return null
}

function safeGetStoredUser() {
  try {
    const raw = getStoredItem('easyexam_user')
    return raw ? JSON.parse(raw) : null
  } catch (_) {
    return null
  }
}

const token = ref(getStoredItem('easyexam_token') || '')
const user = ref(safeGetStoredUser())

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === 'easyexam_token') {
      token.value = e.newValue || ''
      if (!token.value) {
        user.value = null
      }
    } else if (e.key === 'easyexam_user') {
      user.value = safeGetStoredUser()
    }
  })
}

export function useAuthStore() {
  const isAuthenticated = computed(() => Boolean(token.value))

  async function login(username, password, rememberMe = true) {
    const result = await authApi.login(username, password)
    token.value = result.token
    user.value = result.user
    const targetStorage = rememberMe ? localStorage : sessionStorage
    try {
      targetStorage.setItem('easyexam_token', token.value)
      targetStorage.setItem('easyexam_user', JSON.stringify(result.user))
      if (!rememberMe && typeof localStorage !== 'undefined') {
        localStorage.removeItem('easyexam_token')
        localStorage.removeItem('easyexam_user')
      }
    } catch (_) {}
    return result.user
  }

  async function loadCurrentUser() {
    if (!token.value) return null
    try {
      user.value = await authApi.currentUser(token.value)
      try {
        const isSessionOnly = typeof sessionStorage !== 'undefined' && sessionStorage.getItem('easyexam_token')
        const targetStorage = isSessionOnly ? sessionStorage : localStorage
        targetStorage.setItem('easyexam_user', JSON.stringify(user.value))
      } catch (_) {}
      return user.value
    } catch (err) {
      // ONLY logout if server explicitly returned 401 Unauthorized
      const status = err?.status ?? err?.response?.status
      if (status === 401 || err?.message?.includes('401') || err?.detail?.includes('credentials')) {
        logout()
        return null
      }
      // On network failure / offline / 5xx, preserve cached token and user info
      console.warn('[authStore] Network error loading current user, retaining local session:', err?.message || err)
      return user.value
    }
  }

  function logout() {
    if (token.value) authApi.logout(token.value).catch(() => {})
    token.value = ''
    user.value = null
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('easyexam_token')
        localStorage.removeItem('easyexam_user')
      }
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.removeItem('easyexam_token')
        sessionStorage.removeItem('easyexam_user')
      }
    } catch (_) {}
  }

  return { token, user, isAuthenticated, login, loadCurrentUser, logout }
}
