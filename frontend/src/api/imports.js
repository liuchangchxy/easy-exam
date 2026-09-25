import { authHeaders, request } from './client'

export const previewImport = (token, bankId, payload) => request(`/imports/banks/${bankId}/preview`, {
  method: 'POST', headers: authHeaders(token), body: JSON.stringify(payload),
})

export async function previewFileImport(token, bankId, file, columnMapping = null) {
  const form = new FormData()
  form.append('file', file)
  if (columnMapping) {
    form.append('column_mapping', JSON.stringify(columnMapping))
  }
  const response = await fetch(`/api/v1/imports/banks/${bankId}/preview-file`, {
    method: 'POST', headers: authHeaders(token), body: form,
  })
  if (!response.ok) {
    const body = await response.json()
    const error = new Error(typeof body.detail === 'string' ? body.detail : body.detail?.reason || response.statusText)
    error.status = response.status
    error.detail = body.detail
    throw error
  }
  return response.json()
}

export async function uploadImport(token, bankId, file, duplicateStrategy = 'prompt', columnMapping = null) {
  const form = new FormData()
  form.append('file', file)
  if (columnMapping) {
    form.append('column_mapping', JSON.stringify(columnMapping))
  }
  const query = new URLSearchParams({ duplicate_strategy: duplicateStrategy }).toString()
  const response = await fetch(`/api/v1/imports/banks/${bankId}/file?${query}`, {
    method: 'POST', headers: authHeaders(token), body: form,
  })
  if (!response.ok) {
    const body = await response.json()
    const error = new Error(typeof body.detail === 'string' ? body.detail : body.detail?.reason || response.statusText)
    error.status = response.status
    error.detail = body.detail
    throw error
  }
  return response.json()
}
