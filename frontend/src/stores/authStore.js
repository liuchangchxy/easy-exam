import { computed, ref } from 'vue'
import * as authApi from '../api/auth'

const token = ref(localStorage.getItem('easyexam_token') || '')
const user = ref(null)

export function useAuthStore() {
  const isAuthenticated = computed(() => Boolean(token.value))

  async function login(username, password) {
    const result = await authApi.login(username, password)
    token.value = result.token
    user.value = result.user
    localStorage.setItem('easyexam_token', token.value)
    return result.user
  }

  async function loadCurrentUser() {
    if (!token.value) return null
    try {
      user.value = await authApi.currentUser(token.value)
      return user.value
    } catch (_) {
      logout()
      return null
    }
  }

  function logout() {
    if (token.value) authApi.logout(token.value).catch(() => {})
    token.value = ''
    user.value = null
    localStorage.removeItem('easyexam_token')
  }

  return { token, user, isAuthenticated, login, loadCurrentUser, logout }
}
