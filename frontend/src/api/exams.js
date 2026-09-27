import { authHeaders, request } from './client'

export const startExam = (token, payload) => request('/exams/sessions', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const listProfiles = token => request('/exams/profiles', {
  headers: authHeaders(token),
})

export const createProfile = (token, payload) => request('/exams/profiles', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify(payload),
})

export const saveBlueprint = (token, profileId, blueprint) => request(`/exams/profiles/${profileId}/blueprint`, {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ blueprint }),
})

export const getBlueprint = (token, profileId) => request(`/exams/profiles/${profileId}/blueprint`, {
  headers: authHeaders(token),
})
