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

// --- Resumable wizard drafts -------------------------------------------------
// A draft is the server-side identity of one unfinished import. The wizard
// saves its whole in-page state there, so a reload, a back/forward trip or a
// walk to the bank workspace and back can restore the exact step.

export const createImportDraft = (token, bankId, payload) => request(`/imports/banks/${bankId}/drafts`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export function listImportDrafts(token, bankId, status = 'OPEN') {
  const query = status ? `?${new URLSearchParams({ status }).toString()}` : ''
  return request(`/imports/banks/${bankId}/drafts${query}`, { headers: authHeaders(token) })
}

export const getImportDraft = (token, draftId) => request(`/imports/drafts/${draftId}`, {
  headers: authHeaders(token),
})

export const updateImportDraft = (token, draftId, payload) => request(`/imports/drafts/${draftId}`, {
  method: 'PUT',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const deleteImportDraft = (token, draftId) => request(`/imports/drafts/${draftId}`, {
  method: 'DELETE',
  headers: authHeaders(token),
})

// --- Import jobs ------------------------------------------------------------
// The import itself is a background job: start it, then poll its snapshot.
// A file import is multipart (the parser needs the original bytes); a text
// import sends the already-read format/content pair as JSON.

export async function startImportJob(token, bankId, payload = {}) {
  if (payload.file) {
    const form = new FormData()
    form.append('file', payload.file)
    if (payload.column_mapping) {
      form.append('column_mapping', JSON.stringify(payload.column_mapping))
    }
    if (payload.duplicate_strategy) {
      form.append('duplicate_strategy', payload.duplicate_strategy)
    }
    return requestForm(`/imports/banks/${bankId}/jobs`, form, { headers: authHeaders(token) })
  }
  return request(`/imports/banks/${bankId}/jobs`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({
      format: payload.format || 'text',
      content: payload.content || '',
      duplicate_strategy: payload.duplicate_strategy || 'prompt',
    }),
  })
}

export const getImportJob = (token, jobId) => request(`/imports/jobs/${jobId}`, {
  headers: authHeaders(token),
})

export const cancelImportJob = (token, jobId) => request(`/imports/jobs/${jobId}/cancel`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({}),
})
