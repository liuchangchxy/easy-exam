import { authHeaders, request } from './client'

export const listBanks = token => request('/banks', { headers: authHeaders(token) })

export const createBank = (token, payload) => request('/banks', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const createQuestion = (token, bankId, payload) => request(`/banks/${bankId}/questions`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})
