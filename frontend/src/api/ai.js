import { authHeaders, request } from './client'

export const listAnswerVersions = (token, questionId) => request(`/ai/questions/${questionId}/answers`, {
  headers: authHeaders(token),
})

export const saveCandidate = (token, questionId, payload) => request(`/ai/questions/${questionId}/answers`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const adoptAnswer = (token, answerId) => request(`/ai/answers/${answerId}/adopt`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const generateAnswer = (token, questionId, payload = {}) => request(`/ai/questions/${questionId}/generate`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const verifyWeb = (token, questionId, payload = {}) => request(`/ai/questions/${questionId}/verify-web`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const listQuestionConversations = (token, questionId) => request(`/ai/questions/${questionId}/conversations`, {
  headers: authHeaders(token),
})

export const sendChatMessage = (token, questionId, payload) => request(`/ai/questions/${questionId}/messages`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const listConversationMessages = (token, conversationId) => request(`/ai/conversations/${conversationId}/messages`, {
  headers: authHeaders(token),
})

export const getMessageThread = (token, messageId) => request(`/ai/messages/${messageId}/thread`, {
  headers: authHeaders(token),
})

