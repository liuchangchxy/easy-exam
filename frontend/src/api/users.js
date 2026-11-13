import { authHeaders, request } from './client'

// Prefix search over registered accounts. Returns at most 10 candidates and
// never includes the caller; the member picker must work with usernames the
// bank owner cannot already see in the member list.
export const searchUsers = (token, q) => {
  const query = String(q || '').trim()
  return request(`/users/search?q=${encodeURIComponent(query)}`, {
    headers: authHeaders(token),
  })
}
