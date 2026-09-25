import { authHeaders, request } from './client'

export const startExam = (token, payload) => request('/exams/sessions', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})
