import { authHeaders, request } from './client'

export const appendEvents = (token, events) => request('/sync/events', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ events }),
})

export const listEvents = (token, after = '') => request(`/sync/events${after ? `?after=${encodeURIComponent(after)}` : ''}`, {
  headers: authHeaders(token),
})
