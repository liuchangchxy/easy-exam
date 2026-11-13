import { ref } from 'vue'
import { abandonAllSessions, abandonSession, listActiveSessions, startSession } from '../api/practice'

function resolveToken(tokenRef) {
  if (typeof tokenRef === 'function') return tokenRef()
  if (tokenRef && typeof tokenRef === 'object' && 'value' in tokenRef) return tokenRef.value
  return tokenRef
}

function errorMessage(err) {
  return err?.detail || err?.message || ''
}

/**
 * `listActiveSessions(token, mode)` is mode-filtered, so its result can only
 * ever describe one mode. A list that spans several modes came from the
 * unfiltered query and is the complete set the server's abandon-all covers.
 */
function coversEveryMode(sessions) {
  const modes = new Set(sessions.map(item => item?.mode).filter(Boolean))
  return modes.size > 1
}

/**
 * One start entry for every "start studying" button.
 *
 * Starting a session must never silently stack a second one on top of work the
 * user forgot about. The caller renders the decision panel when `blocked` is
 * returned, then delegates back here through `continueSession` or
 * `endAndStart`; it alone decides where a session navigates to.
 */
export function useStartStudy(tokenRef) {
  const pending = ref(false)
  const error = ref('')

  function clearError() {
    error.value = ''
  }

  async function start(payload, { navigate } = {}) {
    error.value = ''
    pending.value = true
    try {
      const token = resolveToken(tokenRef)
      const sessions = await listActiveSessions(token, payload?.mode ?? null)
      const blocked = Array.isArray(sessions) ? sessions : []
      if (blocked.length) return { blocked }
      const session = await startSession(token, payload)
      if (typeof navigate === 'function') navigate(session)
      return { session }
    } catch (err) {
      error.value = errorMessage(err)
      return { error: err }
    } finally {
      pending.value = false
    }
  }

  function continueSession(session, navigate) {
    if (!session || typeof navigate !== 'function') return false
    navigate(session)
    return true
  }

  async function endAndStart(sessions, payload, navigate, options = {}) {
    const list = Array.isArray(sessions) ? sessions.filter(Boolean) : []
    error.value = ''
    pending.value = true
    try {
      const token = resolveToken(tokenRef)
      const allModes = options.coversEveryMode ?? coversEveryMode(list)
      if (list.length) {
        if (allModes) {
          await abandonAllSessions(token)
        } else {
          for (const item of list) {
            if (item?.id) await abandonSession(token, item.id)
          }
        }
      }
      const session = await startSession(token, payload)
      if (typeof navigate === 'function') navigate(session)
      return { session }
    } catch (err) {
      error.value = errorMessage(err)
      return { error: err }
    } finally {
      pending.value = false
    }
  }

  return { start, continueSession, endAndStart, pending, error, clearError }
}
