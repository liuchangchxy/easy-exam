import { authHeaders, request } from './client'

export const getQuestion = (token, questionId) => request(`/questions/${questionId}`, {
  headers: authHeaders(token),
})

export const listQuestionVersions = (token, questionId) => request(`/questions/${questionId}/versions`, {
  headers: authHeaders(token),
})

export const updateQuestion = (token, questionId, payload) => request(`/questions/${questionId}`, {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const getQuestionConflict = (token, questionId) => request(`/questions/${questionId}/conflict`, {
  headers: authHeaders(token),
})

export const resolveQuestionConflict = (token, questionId, adoptVersionNumber) => request(`/questions/${questionId}/resolve-conflict`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ adopt_version_number: adoptVersionNumber }),
})
