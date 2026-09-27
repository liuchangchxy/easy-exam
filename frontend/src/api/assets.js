import { authHeaders, request } from './client'

export const listAssets = (token, questionId = '') => request(`/assets${questionId ? `?question_id=${questionId}` : ''}`, {
  headers: authHeaders(token),
})

export const createAsset = (token, payload) => request('/assets', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const uploadAssetFile = (token, file, assetType = 'NOTE', questionId = '', knowledgeTagId = '') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('asset_type', assetType)
  if (questionId) formData.append('question_id', questionId)
  if (knowledgeTagId) formData.append('knowledge_tag_id', knowledgeTagId)

  return fetch('/api/v1/assets/upload', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw err
    }
    return res.json()
  })
}

export const deleteAsset = (token, assetId) => request(`/assets/${assetId}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})
