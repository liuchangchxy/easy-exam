// Route guards only answer questions the URL can answer on its own: is the user
// signed in, and may they open an instance-admin page. Whether somebody is a
// member of a particular bank is data, so it stays with the backend and the
// page's own 403 state (see AccessDeniedState).
export const FORBIDDEN_ROUTE = { name: 'forbidden' }

export async function adminGuard(to, auth) {
  if (!to?.meta?.requiresAdmin) return true
  if (!auth) return true

  // A hard refresh straight onto an admin URL may only have the cached user;
  // refresh it once rather than judging from stale storage. A cache written by
  // a build that predates `is_admin` also has to be refreshed, otherwise an
  // existing admin would be locked out of the new page.
  let refreshed = null
  const cached = auth.user?.value
  const needsRefresh = !cached || typeof cached.is_admin !== 'boolean'
  if (needsRefresh && auth.token?.value && typeof auth.loadCurrentUser === 'function') {
    refreshed = await auth.loadCurrentUser()
  }

  if (refreshed?.is_admin || auth.user?.value?.is_admin) return true

  return { ...FORBIDDEN_ROUTE, query: { kind: 'forbidden', from: to.fullPath } }
}
