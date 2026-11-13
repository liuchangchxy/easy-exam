import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { adminGuard, FORBIDDEN_ROUTE } from '../../src/router/guards.js'

function makeAuth({ user = null, token = '', loadCurrentUser = null } = {}) {
  return { user: ref(user), token: ref(token), loadCurrentUser }
}

describe('adminGuard', () => {
  it('lets every page through when it is not an admin-only route', async () => {
    const auth = makeAuth({ user: { is_admin: false } })
    expect(await adminGuard({ meta: {} }, auth)).toBe(true)
    expect(await adminGuard({}, auth)).toBe(true)
  })

  it('lets an instance admin through', async () => {
    const auth = makeAuth({ user: { is_admin: true }, token: 't' })
    expect(await adminGuard({ meta: { requiresAdmin: true }, fullPath: '/admin' }, auth)).toBe(true)
  })

  it('sends a signed-in non-admin to the 403 page and keeps the target', async () => {
    const auth = makeAuth({ user: { is_admin: false }, token: 't' })
    const result = await adminGuard({ meta: { requiresAdmin: true }, fullPath: '/admin/users' }, auth)

    expect(result).toEqual({ name: FORBIDDEN_ROUTE.name, query: { kind: 'forbidden', from: '/admin/users' } })
  })

  it('refreshes a stale or missing cached user before deciding', async () => {
    const loadCurrentUser = vi.fn().mockResolvedValue({ is_admin: true })
    const auth = makeAuth({ user: null, token: 't', loadCurrentUser })

    expect(await adminGuard({ meta: { requiresAdmin: true }, fullPath: '/admin' }, auth)).toBe(true)
    expect(loadCurrentUser).toHaveBeenCalledTimes(1)
  })

  it('refreshes a cached user that predates the is_admin flag', async () => {
    const loadCurrentUser = vi.fn().mockResolvedValue({ is_admin: true })
    const auth = makeAuth({ user: { username: 'legacy' }, token: 't', loadCurrentUser })

    expect(await adminGuard({ meta: { requiresAdmin: true }, fullPath: '/instance' }, auth)).toBe(true)
    expect(loadCurrentUser).toHaveBeenCalledTimes(1)
  })

  it('does not call the API when there is no token', async () => {
    const loadCurrentUser = vi.fn()
    const auth = makeAuth({ user: null, token: '', loadCurrentUser })

    await adminGuard({ meta: { requiresAdmin: true }, fullPath: '/admin' }, auth)
    expect(loadCurrentUser).not.toHaveBeenCalled()
  })
})
