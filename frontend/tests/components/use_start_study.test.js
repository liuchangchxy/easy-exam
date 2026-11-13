import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { useStartStudy } from '../../src/composables/useStartStudy'
import {
  abandonAllSessions,
  abandonSession,
  listActiveSessions,
  startSession,
} from '../../src/api/practice'

vi.mock('../../src/api/practice', () => ({
  listActiveSessions: vi.fn(),
  startSession: vi.fn(),
  abandonSession: vi.fn(),
  abandonAllSessions: vi.fn(),
}))

const token = ref('t1')
const payload = { bank_id: 'b1', mode: 'PRACTICE' }

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

describe('useStartStudy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listActiveSessions.mockResolvedValue([])
    startSession.mockResolvedValue({ id: 's-new', mode: 'PRACTICE' })
    abandonSession.mockResolvedValue({})
    abandonAllSessions.mockResolvedValue({})
  })

  it('starts the session and navigates when nothing is unfinished', async () => {
    const navigate = vi.fn()
    const { start, pending, error } = useStartStudy(token)

    const result = await start(payload, { navigate })

    expect(listActiveSessions).toHaveBeenCalledWith('t1', 'PRACTICE')
    expect(startSession).toHaveBeenCalledWith('t1', payload)
    expect(navigate).toHaveBeenCalledWith({ id: 's-new', mode: 'PRACTICE' })
    expect(result.blocked).toBeUndefined()
    expect(result.session).toEqual({ id: 's-new', mode: 'PRACTICE' })
    expect(pending.value).toBe(false)
    expect(error.value).toBe('')
  })

  it('blocks instead of posting when an active session exists', async () => {
    const active = [{ id: 's-open', mode: 'PRACTICE', bank_name: 'Bank One' }]
    listActiveSessions.mockResolvedValue(active)
    const navigate = vi.fn()
    const { start, pending } = useStartStudy(token)

    const result = await start(payload, { navigate })

    expect(result).toEqual({ blocked: active })
    expect(startSession).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
    expect(pending.value).toBe(false)
  })

  it('abandons the returned session by id when the list is a single mode', async () => {
    const sessions = [
      { id: 's1', mode: 'PRACTICE' },
      { id: 's2', mode: 'PRACTICE' },
    ]
    const navigate = vi.fn()
    const { endAndStart } = useStartStudy(token)

    const result = await endAndStart(sessions, payload, navigate)

    expect(abandonSession.mock.calls).toEqual([['t1', 's1'], ['t1', 's2']])
    expect(abandonAllSessions).not.toHaveBeenCalled()
    expect(startSession).toHaveBeenCalledWith('t1', payload)
    expect(navigate).toHaveBeenCalledWith({ id: 's-new', mode: 'PRACTICE' })
    expect(result.session).toEqual({ id: 's-new', mode: 'PRACTICE' })
  })

  it('uses abandon-all only when the returned list spans every active mode', async () => {
    const sessions = [
      { id: 's1', mode: 'PRACTICE' },
      { id: 's2', mode: 'EXAM' },
    ]
    const { endAndStart } = useStartStudy(token)

    await endAndStart(sessions, payload, vi.fn())

    expect(abandonAllSessions).toHaveBeenCalledWith('t1')
    expect(abandonSession).not.toHaveBeenCalled()
    expect(startSession).toHaveBeenCalledWith('t1', payload)
  })

  it('continues an existing session through the caller-supplied navigation', () => {
    const navigate = vi.fn()
    const { continueSession } = useStartStudy(token)

    const opened = continueSession({ id: 's1' }, navigate)

    expect(opened).toBe(true)
    expect(navigate).toHaveBeenCalledWith({ id: 's1' })
  })

  it('surfaces a failed lookup without starting or navigating', async () => {
    listActiveSessions.mockRejectedValue({ detail: 'lookup failed' })
    const navigate = vi.fn()
    const { start, error, pending, clearError } = useStartStudy(token)

    const result = await start(payload, { navigate })

    expect(error.value).toBe('lookup failed')
    expect(result.error).toBeTruthy()
    expect(startSession).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
    expect(pending.value).toBe(false)

    clearError()
    expect(error.value).toBe('')
  })

  it('surfaces a failed start after abandoning and keeps pending false', async () => {
    startSession.mockRejectedValue({ message: 'start failed' })
    const navigate = vi.fn()
    const { endAndStart, error, pending } = useStartStudy(token)

    const result = await endAndStart([{ id: 's1', mode: 'PRACTICE' }], payload, navigate)

    expect(abandonSession).toHaveBeenCalledWith('t1', 's1')
    expect(error.value).toBe('start failed')
    expect(result.error).toBeTruthy()
    expect(navigate).not.toHaveBeenCalled()
    expect(pending.value).toBe(false)
  })

  it('marks pending true while the lookup is in flight', async () => {
    const lookup = deferred()
    listActiveSessions.mockReturnValue(lookup.promise)
    const { start, pending } = useStartStudy(token)

    const run = start(payload, { navigate: vi.fn() })
    expect(pending.value).toBe(true)

    lookup.resolve([])
    await run
    expect(pending.value).toBe(false)
  })
})
