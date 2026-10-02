import { authHeaders, request, requestForm } from './client'

export const previewImport = (token, bankId, payload) => request(`/imports/banks/${bankId}/preview`, {
  method: 'POST', headers: authHeaders(token), body: JSON.stringify(payload),
})

export async function previewFileImport(token, bankId, file, columnMapping = null) {
  const form = new FormData()
  form.append('file', file)
  if (columnMapping) {
    form.append('column_mapping', JSON.stringify(columnMapping))
  }
  return requestForm(`/imports/banks/${bankId}/preview-file`, form, { headers: authHeaders(token) })
}

export async function uploadImport(token, bankId, file, duplicateStrategy = 'prompt', columnMapping = null) {
  const form = new FormData()
  form.append('file', file)
  if (columnMapping) {
    form.append('column_mapping', JSON.stringify(columnMapping))
  }
  const query = new URLSearchParams({ duplicate_strategy: duplicateStrategy }).toString()
  return requestForm(`/imports/banks/${bankId}/file?${query}`, form, { headers: authHeaders(token) })
}

export async function previewPdfImport(token, bankId, file) {
  const form = new FormData()
  form.append('file', file)
  return requestForm(`/imports/banks/${bankId}/pdf-preview`, form, { headers: authHeaders(token) })
}

export const confirmPdfImport = (token, bankId, payload) => request(`/imports/banks/${bankId}/pdf-confirm`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})
