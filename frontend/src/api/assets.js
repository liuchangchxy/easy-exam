import { ApiError, authHeaders, parseApiResponse, request, requestForm } from './client'

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

  return requestForm('/assets/upload', formData, { headers: authHeaders(token) })
}

export const updateAsset = (token, assetId, payload) => request(`/assets/${assetId}`, {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const deleteAsset = (token, assetId) => request(`/assets/${assetId}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})

/**
 * Fetch a stored reference file as a blob so the browser can preview or
 * download it while still sending the Authorization header.
 */
export async function fetchAssetBlob(token, assetId, { download = false } = {}) {
  const query = download ? '?download=1' : ''
  let response
  try {
    response = await fetch(`/api/v1/assets/${assetId}/file${query}`, {
      headers: authHeaders(token),
    })
  } catch (_) {
    throw new ApiError(0, 'NETWORK_ERROR')
  }
  if (!response.ok) {
    await parseApiResponse(response)
    throw new ApiError(response.status, 'REQUEST_FAILED')
  }
  return {
    blob: await response.blob(),
    mimeType: response.headers.get('Content-Type') || '',
  }
}
