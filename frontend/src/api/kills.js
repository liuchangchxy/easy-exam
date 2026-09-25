import { authHeaders, request } from './client'

export const listKills = token => request('/kills', {
  headers: authHeaders(token),
})

export const killQuestion = (token, questionId) => request(`/kills/${encodeURIComponent(questionId)}`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const unkillQuestion = (token, questionId) => request(`/kills/${encodeURIComponent(questionId)}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})
