import { authHeaders, request } from './client'
import { getQuestion } from './questions'

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

/**
 * Normalize legacy practice-view payloads to the variant API contract.
 * The API requires `original_question_id` and `target_bank_id`; older callers
 * sent `question_id` and `prompt`, which produced spurious 422 responses.
 */
export function buildVariantRequestBody(payload = {}, question = null) {
  const originalQuestionId = String(payload.original_question_id || payload.question_id || '').trim()
  if (!originalQuestionId) {
    throw new Error('original_question_id is required')
  }
  const targetBankId = String(payload.target_bank_id || question?.bank_id || '').trim()
  if (!targetBankId) {
    throw new Error('target_bank_id is required')
  }
  return {
    original_question_id: originalQuestionId,
    target_bank_id: targetBankId,
    prompt_hint: String(payload.prompt_hint || payload.prompt || '').trim(),
  }
}

export const generateVariant = async (token, payload = {}) => {
  let question = null
  if (!payload.target_bank_id) {
    const questionId = payload.original_question_id || payload.question_id
    if (questionId) question = await getQuestion(token, questionId)
  }
  return request('/ai/variants', {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(buildVariantRequestBody(payload, question)),
  })
}

export const listDrafts = (token, status = 'DRAFT', bankId = '') => {
  const params = new URLSearchParams({ status })
  if (bankId) params.set('bank_id', bankId)
  return request(`/ai/drafts?${params.toString()}`, {
    headers: authHeaders(token),
  })
}

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


