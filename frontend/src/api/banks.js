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

export const addBankMember = (token, bankId, username, role = 'MEMBER') => request(`/banks/${bankId}/members`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ username, role }),
})

export const listBankMembers = (token, bankId) => request(`/banks/${bankId}/members`, {
  headers: authHeaders(token),
})

export const removeBankMember = (token, bankId, memberUserId) => request(`/banks/${bankId}/members/${memberUserId}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})

export const copyQuestionToBank = (token, sourceBankId, questionId, targetBankId) => request(`/banks/${targetBankId}/questions/${questionId}/copy`, {
  method: 'POST',
  headers: authHeaders(token),
})
