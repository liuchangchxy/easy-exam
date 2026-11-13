import { authHeaders, request } from './client'

export const listMistakes = (token, bankId = '') => request(`/mistakes${bankId ? `?bank_id=${encodeURIComponent(bankId)}` : ''}`, { headers: authHeaders(token) })
export const listDueMistakes = (token, bankId = '') => request(`/mistakes/due${bankId ? `?bank_id=${encodeURIComponent(bankId)}` : ''}`, { headers: authHeaders(token) })
// Weak flags have their own source: /mistakes/due only mentions flags that
// already have a due card, which would leave the review queue's 薄弱 reason empty.
export const listWeakMistakes = (token, bankId = '') => request(`/mistakes/weak${bankId ? `?bank_id=${encodeURIComponent(bankId)}` : ''}`, { headers: authHeaders(token) })
export const updateMistakeCause = (token, questionId, mistakeCause) => request(`/mistakes/${questionId}/cause`, {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify({ mistake_cause: mistakeCause }),
})
