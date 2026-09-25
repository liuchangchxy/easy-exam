import { authHeaders, request } from './client'

export const listMistakes = (token, bankId = '') => request(`/mistakes${bankId ? `?bank_id=${encodeURIComponent(bankId)}` : ''}`, { headers: authHeaders(token) })
export const listDueMistakes = (token, bankId = '') => request(`/mistakes/due${bankId ? `?bank_id=${encodeURIComponent(bankId)}` : ''}`, { headers: authHeaders(token) })
export const updateMistakeCause = (token, questionId, mistakeCause) => request(`/mistakes/${questionId}/cause`, {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify({ mistake_cause: mistakeCause }),
})
