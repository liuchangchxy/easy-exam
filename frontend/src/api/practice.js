import { authHeaders, request } from './client'

export const startSession = (token, payload) => request('/practice/sessions', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const submitAttempt = (token, sessionId, payload) => request(`/practice/sessions/${sessionId}/attempts`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const getSession = (token, sessionId) => request(`/practice/sessions/${sessionId}`, {
  headers: authHeaders(token),
})

export const getSessionQuestions = (token, sessionId) => request(`/practice/sessions/${sessionId}/questions`, {
  headers: authHeaders(token),
})

export const completeSession = (token, sessionId) => request(`/practice/sessions/${sessionId}/complete`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const syncDraft = (token, sessionId, payload) => request(`/practice/sessions/${sessionId}/sync`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const toggleFlag = (token, sessionId, questionId) => request(`/practice/sessions/${sessionId}/toggle-flag`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ question_id: questionId }),
})

export const listActiveSessions = (token, mode = null) => {
  const query = mode ? `?mode=${encodeURIComponent(mode)}` : ''
  return request(`/practice/sessions/active${query}`, {
    headers: authHeaders(token),
  })
}

export const abandonSession = (token, sessionId) => request(`/practice/sessions/${sessionId}/abandon`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const abandonAllSessions = (token) => request('/practice/sessions/abandon-all', {
  method: 'POST',
  headers: authHeaders(token),
})
