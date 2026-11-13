import { authHeaders, request } from './client'

// Instance administration. These calls are authorised by `users.is_admin` on
// the server; the route guard is only the front-end half of that contract.
export const listAdminUsers = token => request('/admin/users', {
  headers: authHeaders(token),
})

export const updateAdminUser = (token, userId, payload) => request(`/admin/users/${userId}`, {
  method: 'PATCH',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const resetUserPassword = (token, userId) => request(`/admin/users/${userId}/reset-password`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const getAdminSettings = token => request('/admin/settings', {
  headers: authHeaders(token),
})

export const updateAdminSettings = (token, payload) => request('/admin/settings', {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const listSessions = token => request('/auth/sessions', {
  headers: authHeaders(token),
})

export const revokeOtherSessions = token => request('/auth/sessions', {
  method: 'DELETE',
  headers: authHeaders(token),
})
