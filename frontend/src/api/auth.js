import { authHeaders, request } from './client'

export const register = (username, password) => request('/auth/register', {
  method: 'POST',
  body: JSON.stringify({ username, password }),
})

export const login = (username, password) => request('/auth/login', {
  method: 'POST',
  body: JSON.stringify({ username, password }),
})

export const currentUser = token => request('/auth/me', { headers: authHeaders(token) })

export const logout = token => request('/auth/logout', {
  method: 'POST',
  headers: authHeaders(token),
})

export const changePassword = (token, old_password, new_password) => request('/auth/change-password', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ old_password, new_password }),
})

