import { authHeaders, localizedHeaders, request } from './client'

export const listBanks = (token, options = {}) => {
  const query = options.deleted ? '?deleted=1' : ''
  return request(`/banks${query}`, { headers: authHeaders(token) })
}

export const updateBank = (token, bankId, payload) => request(`/banks/${bankId}`, {
  method: 'PATCH',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const deleteBank = (token, bankId) => request(`/banks/${bankId}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})

export const restoreBank = (token, bankId) => request(`/banks/${bankId}/restore`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const batchBanks = (token, payload) => request('/banks/batch', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const listBankCategories = token => request('/banks/categories', {
  headers: authHeaders(token),
})

export const renameBankCategory = (token, oldName, newName) => request('/banks/categories/rename', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ old_name: oldName, new_name: newName }),
})

export const deleteBankCategory = (token, name) => request('/banks/categories/delete', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ name }),
})

export const listBankAudit = (token, bankId) => request(`/banks/${bankId}/audit`, {
  headers: authHeaders(token),
})

export const listBankImports = (token, bankId) => request(`/banks/${bankId}/imports`, {
  headers: authHeaders(token),
})

export const updateBankMemberRole = (token, bankId, memberUserId, role) => request(`/banks/${bankId}/members/${memberUserId}`, {
  method: 'PATCH',
  headers: authHeaders(token),
  body: JSON.stringify({ role }),
})

export const leaveBank = (token, bankId) => request(`/banks/${bankId}/leave`, {
  method: 'POST',
  headers: authHeaders(token),
})

export const transferBankOwnership = (token, bankId, username) => request(`/banks/${bankId}/transfer`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ username }),
})

export const reorderChapters = (token, bankId, items) => request(`/banks/${bankId}/chapters/reorder`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ items }),
})

export const exportBank = async (token, bankId, format = 'json', includeArchived = false) => {
  const params = new URLSearchParams({ format })
  if (includeArchived) params.set('include_archived', '1')
  const response = await fetch(`/api/v1/banks/${bankId}/export?${params.toString()}`, {
    headers: localizedHeaders(authHeaders(token)),
  })
  if (!response.ok) throw new Error(`export failed (${response.status})`)
  return response.blob()
}

export async function downloadBankExport(token, bankId, format = 'json', includeArchived = false) {
  const blob = await exportBank(token, bankId, format, includeArchived)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `bank_${bankId}.${format === 'json' ? 'json' : format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

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

export const getBank = (token, bankId) => request(`/banks/${bankId}`, {
  headers: authHeaders(token),
})

export const listBankQuestionsContent = (token, bankId, options = {}) => {
  const query = options.includeArchived ? '?include_archived=true' : ''
  return request(`/banks/${bankId}/content/questions${query}`, {
    headers: authHeaders(token),
  })
}

export const batchBankQuestions = (token, bankId, payload) => request(`/banks/${bankId}/questions/batch`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const listChapters = (token, bankId) => request(`/banks/${bankId}/chapters`, {
  headers: authHeaders(token),
})

export const createChapter = (token, bankId, payload) => request(`/banks/${bankId}/chapters`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const updateChapter = (token, bankId, chapterId, payload) => request(`/banks/${bankId}/chapters/${chapterId}`, {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const deleteChapter = (token, bankId, chapterId) => request(`/banks/${bankId}/chapters/${chapterId}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})

export const listTags = (token, bankId) => request(`/banks/${bankId}/tags`, {
  headers: authHeaders(token),
})

export const createTag = (token, bankId, name) => request(`/banks/${bankId}/tags`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ name }),
})

export const updateTag = (token, bankId, tagId, name) => request(`/banks/${bankId}/tags/${tagId}`, {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify({ name }),
})

export const deleteTag = (token, bankId, tagId) => request(`/banks/${bankId}/tags/${tagId}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})
