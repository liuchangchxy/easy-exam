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

export const generateVariant = (token, payload) => request('/ai/variants', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const listDrafts = (token, status = 'DRAFT') => request(`/ai/drafts?status=${status}`, {
  headers: authHeaders(token),
})

export const getDraft = (token, draftId) => request(`/ai/drafts/${draftId}`, {
  headers: authHeaders(token),
})

export const acceptDraft = (token, draftId, modifications = null) => request(`/ai/drafts/${draftId}/accept`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ modifications }),
})

export const discardDraft = (token, draftId) => request(`/ai/drafts/${draftId}/discard`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const getAiConfig = (token) => request('/ai/config', {
  headers: authHeaders(token),
})

export const updateAiConfig = (token, payload) => request('/ai/config', {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const getAiBatchStatus = (token, bankId) => request(`/ai/banks/${bankId}/batch-status`, {
  headers: authHeaders(token),
})

export const startAiBatchGenerate = (token, bankId, overwrite = false) => request(`/ai/banks/${bankId}/generate-batch`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ overwrite }),
})

export const stopAiBatchGenerate = (token, bankId) => request(`/ai/banks/${bankId}/batch-stop`, {
  method: 'POST',
  headers: authHeaders(token),
})


