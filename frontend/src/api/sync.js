import { authHeaders, request } from './client.js'

export const appendEvents = (token, events) => request('/sync/events', {
  method: 'POST',
  headers: authHeaders(token),
  body: JSON.stringify({ events }),
})

export const listEvents = (token, after = '') => request(`/sync/events${after ? `?after=${encodeURIComponent(after)}` : ''}`, {
  headers: authHeaders(token),
})

export function triggerSyncEvent(eventType, aggregateType, aggregateId, payload = {}) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('easyexam:emit-sync-event', {
      detail: { eventType, aggregateType, aggregateId, payload },
    }))
  }
}
