/**
 * Practice domain helper functions for session state hydration,
 * option normalization, and navigation lifecycle resets.
 */

/**
 * Hydrates practice session state from backend session payload.
 * Safely restores the current question index (clamped to questions boundary)
 * and answers dictionary.
 *
 * @param {Object|null} session - Backend session object
 * @param {number} questionsLength - Total number of questions in session
 * @returns {{ currentIndex: number, sessionAnswers: Object }}
 */
export function hydrateSessionPractice(session, questionsLength = 0) {
  const maxIdx = Math.max(0, questionsLength - 1)
  let currentIndex = 0
  if (session && session.current_index !== undefined && session.current_index !== null) {
    currentIndex = Math.min(Math.max(0, Number(session.current_index) || 0), maxIdx)
  }

  const sessionAnswers = {}
  if (session && session.answers && typeof session.answers === 'object') {
    Object.assign(sessionAnswers, session.answers)
  }

  return {
    currentIndex,
    sessionAnswers
  }
}

/**
 * Normalizes question options to ensure standard { key, content } contract.
 * Resilient to legacy or foreign data schemas where text was named 'text'.
 *
 * @param {Array<Object>} options - Raw options array
 * @returns {Array<{ key: string, content: string }>}
 */
export function normalizeQuestionOptions(options) {
  if (!Array.isArray(options)) return []
  return options.map((opt, index) => {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    const key = opt.key || letters[index] || `Option${index + 1}`
    const content = opt.content !== undefined && opt.content !== null
      ? String(opt.content)
      : (opt.text !== undefined && opt.text !== null ? String(opt.text) : '')
    return { key, content }
  })
}

/**
 * Determines whether question editing / temporary form state must be reset
 * based on question navigation transitions.
 *
 * @param {Object|null} current - Current question object
 * @param {Object|null} previous - Previous question object
 * @returns {boolean} True if question pointer has changed and state must be reset
 */
export function shouldResetQuestionForm(current, previous) {
  if (!current) return true
  if (!previous) return true
  return current.id !== previous.id
}

/**
 * Stable per-account storage scope. Never falls back to a shared literal such
 * as "user": doing so would merge different accounts' offline queues.
 *
 * @param {Object|null} user
 * @returns {string} Empty string when no authenticated identity is available.
 */
export function resolvePracticeUserKey(user) {
  const id = user?.id ?? user?.username
  return id === undefined || id === null ? '' : String(id)
}

export const LEGACY_OFFLINE_EDIT_KEY = 'easyexam_offline_question_edits'

export function offlineEditQueueKey(userKey) {
  return userKey ? `easyexam_offline_question_edits_${userKey}` : ''
}

export function offlineAttemptQueueKey(userKey) {
  return userKey ? `easyexam_offline_attempts_${userKey}` : ''
}

export function localPracticeDraftKey(userKey, sessionId) {
  return userKey && sessionId ? `easyexam_practice_draft_${userKey}_${sessionId}` : ''
}

export function practiceDraftConflictKey(userKey, sessionId) {
  return userKey && sessionId ? `easyexam_practice_draft_conflicts_${userKey}_${sessionId}` : ''
}

export function isNetworkError(err) {
  return err?.status === 0 || err?.code === 'NETWORK_ERROR'
}

let attemptIdSequence = 0

/**
 * Creates the stable idempotency key for one user submission.
 *
 * The key is generated once when the user acts and is reused verbatim by every
 * retry and by the offline queue, so the server can collapse a replay instead
 * of inserting a second attempt. A genuinely new user action must call this
 * again to obtain a fresh key.
 *
 * @param {string} prefix - Short operation label, useful when debugging queues.
 * @returns {string} Non-empty key of at most 200 characters.
 */
export function createClientAttemptId(prefix = 'attempt') {
  const cryptoObj = typeof globalThis !== 'undefined' ? globalThis.crypto : null
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    return `${prefix}-${cryptoObj.randomUUID()}`
  }
  attemptIdSequence += 1
  const random = Math.random().toString(36).slice(2, 10)
  return `${prefix}-${Date.now().toString(36)}-${attemptIdSequence}-${random}`
}

export function clientAttemptIdOf(entry) {
  const value = entry?.clientAttemptId ?? entry?.client_attempt_id
  return typeof value === 'string' && value.trim() ? value : ''
}

/**
 * Queue identity. Entries created before client keys existed fall back to the
 * session+question pair, which keeps the old upsert behaviour for them.
 */
export function pendingAttemptKey(entry) {
  return `${entry?.sessionId}::${entry?.questionId}::${clientAttemptIdOf(entry)}`
}

function mergePendingAttempt(existing, incoming) {
  const merged = { ...existing, ...incoming }
  if (incoming?.user_answer === undefined) merged.user_answer = existing.user_answer
  if (incoming?.fsrs_rating === undefined) merged.fsrs_rating = existing?.fsrs_rating ?? null
  return merged
}

export function isEmptyAnswer(value) {
  if (value === undefined || value === null) return true
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'string') return value.trim().length === 0
  return false
}

/**
 * Extracts a plain answer value from either a draft-state entry
 * ({ answer, textAnswer }) or an attempt record ({ answer, user_answer }).
 */
export function rawDraftAnswer(saved) {
  if (saved === undefined || saved === null) return ''
  if (Array.isArray(saved)) return saved
  if (typeof saved !== 'object') return saved
  if (typeof saved.textAnswer === 'string' && saved.textAnswer.trim()) return saved.textAnswer
  if (saved.answer !== undefined && saved.answer !== null) return saved.answer
  if (saved.user_answer !== undefined && saved.user_answer !== null) return saved.user_answer
  if (saved.textAnswer !== undefined && saved.textAnswer !== null) return saved.textAnswer
  return ''
}

/**
 * Builds the optimistic-concurrency draft sync payload.
 *
 * A value is sent when the user has content locally, or when the local state is
 * empty while the last observed server value was not (an explicit clear).
 * `baseAnswers` is the snapshot of server values this client last observed; the
 * server uses it to distinguish a normal local edit from a cross-device write.
 */
export function buildDraftAnswerPayload(sessionAnswers, baseAnswers) {
  const payload = {}
  const answers = sessionAnswers || {}
  for (const qid of Object.keys(answers)) {
    const raw = rawDraftAnswer(answers[qid])
    const base = rawDraftAnswer((baseAnswers || {})[qid])
    if (!isEmptyAnswer(raw)) payload[qid] = raw
    else if (!isEmptyAnswer(base)) payload[qid] = ''
  }
  return payload
}

export function buildDraftBasePayload(payload, baseAnswers) {
  const base = {}
  for (const qid of Object.keys(payload || {})) {
    // A question missing from the observed map was observed as unanswered, not
    // as "unknown", so send an explicit empty base for it.
    base[qid] = rawDraftAnswer((baseAnswers || {})[qid])
  }
  return base
}

export function answersToBaseMap(serverAnswers) {
  const base = {}
  for (const [qid, value] of Object.entries(serverAnswers || {})) {
    base[qid] = rawDraftAnswer(value)
  }
  return base
}

/**
 * Parses a server timestamp into epoch milliseconds.
 *
 * SQLite `CURRENT_TIMESTAMP` produces `YYYY-MM-DD HH:MM:SS` with no timezone
 * marker. `Date.parse` reads such a string as *local* time, shifting it by the
 * client's UTC offset (8 hours in UTC+8) and letting an older local draft look
 * newer than the server write it must not clobber. Zoneless values are pinned
 * to UTC here, matching how they were written.
 *
 * @param {string|number|null|undefined} value
 * @returns {number} Epoch milliseconds, or NaN when the value is not a timestamp.
 */
export function parseServerTimestamp(value) {
  if (value === undefined || value === null || value === '') return Number.NaN
  if (typeof value === 'number') return Number.isFinite(value) ? value : Number.NaN
  const text = String(value).trim()
  if (!text) return Number.NaN
  const zoneless = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/
  const normalized = zoneless.test(text) ? `${text.replace(' ', 'T')}Z` : text
  return Date.parse(normalized)
}

/**
 * Writes a local backup of unsubmitted answers so a weak/offline network does
 * not lose the draft on exit or reload.
 */
export function snapshotLocalDraft(sessionAnswers, updatedAt = Date.now(), clientAttemptIds = null) {
  const entries = {}
  for (const [qid, saved] of Object.entries(sessionAnswers || {})) {
    if (!isEmptyAnswer(rawDraftAnswer(saved))) {
      entries[qid] = {
        answer: saved?.answer !== undefined ? saved.answer : rawDraftAnswer(saved),
        textAnswer: saved?.textAnswer || '',
      }
    }
  }
  const snapshot = { answers: entries, updatedAt }
  const ids = {}
  for (const [qid, id] of Object.entries(clientAttemptIds || {})) {
    if (typeof id === 'string' && id.trim()) ids[qid] = id
  }
  if (Object.keys(ids).length) snapshot.clientAttemptIds = ids
  return snapshot
}

/** Reads the per-question attempt keys kept alongside a local draft backup. */
export function clientAttemptIdsFromDraft(localDraft) {
  const ids = {}
  const source = localDraft?.clientAttemptIds
  if (!source || typeof source !== 'object') return ids
  for (const [qid, id] of Object.entries(source)) {
    if (typeof id === 'string' && id.trim()) ids[qid] = id
  }
  return ids
}

/**
 * Merges a local draft backup into server-hydrated state.
 *
 * The local backup wins only when it is newer than the server's `updated_at`,
 * and never overrides an answer that already has a scored result.
 */
export function mergeLocalDraftEntries(sessionAnswers, localDraft, serverUpdatedAt) {
  const merged = { ...(sessionAnswers || {}) }
  if (!localDraft || !localDraft.answers) return merged
  const localAt = typeof localDraft.updatedAt === 'number'
    ? localDraft.updatedAt
    : Date.parse(localDraft.updatedAt || 0)
  const serverAt = parseServerTimestamp(serverUpdatedAt)
  if (!Number.isFinite(localAt) || (Number.isFinite(serverAt) && localAt <= serverAt)) {
    return merged
  }
  for (const [qid, entry] of Object.entries(localDraft.answers)) {
    if (!entry) continue
    const existing = merged[qid]
    if (existing && (existing.result || existing.correctness)) continue
    merged[qid] = {
      ...(existing || {}),
      answer: entry.answer,
      textAnswer: entry.textAnswer || '',
    }
  }
  return merged
}

/**
 * Splits a legacy unscoped edit queue without dropping another account's items.
 */
export function partitionLegacyEditQueue(queue, userKey) {
  const mine = []
  const others = []
  for (const item of Array.isArray(queue) ? queue : []) {
    if (!item || !item.userId || String(item.userId) === String(userKey)) mine.push(item)
    else others.push(item)
  }
  return { mine, others }
}

export function mergeEditQueues(primary, secondary) {
  const seen = new Set()
  const merged = []
  for (const item of [...(primary || []), ...(secondary || [])]) {
    if (!item || !item.questionId) continue
    const key = `${item.questionId}::${JSON.stringify(item.payload || {})}`
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(item)
  }
  return merged
}

/**
 * Upserts one queued submission.
 *
 * Identity includes the client attempt key: an answer and the rating for that
 * same answer share one queue entry (so neither overwrites the other), while a
 * genuinely new operation with a new key stays a separate entry.
 */
export function upsertPendingAttempt(queue, item) {
  const key = pendingAttemptKey(item)
  const next = []
  let existing = null
  for (const entry of Array.isArray(queue) ? queue : []) {
    if (!entry) continue
    if (pendingAttemptKey(entry) !== key) {
      next.push(entry)
      continue
    }
    existing = existing ? mergePendingAttempt(existing, entry) : entry
  }
  next.push(existing ? mergePendingAttempt(existing, item) : item)
  return next
}

/**
 * Removes a queued submission.
 *
 * With a client key only that exact operation is dropped; without one (legacy
 * entries) every submission for the question is dropped, as before.
 */
export function removePendingAttempt(queue, sessionId, questionId, clientAttemptId) {
  return (Array.isArray(queue) ? queue : []).filter(entry => {
    if (entry?.sessionId !== sessionId || entry?.questionId !== questionId) return true
    if (clientAttemptId === undefined || clientAttemptId === null) return false
    return clientAttemptIdOf(entry) !== clientAttemptId
  })
}

/**
 * Merges newly reported draft conflicts into the still-unresolved set.
 * A question already awaiting resolution is replaced by the freshest report so
 * the banner always describes the latest server value.
 */
export function mergeDraftConflicts(existing, incoming) {
  const merged = new Map()
  for (const conflict of [...(existing || []), ...(incoming || [])]) {
    if (!conflict || !conflict.question_id) continue
    merged.set(conflict.question_id, conflict)
  }
  return [...merged.values()]
}

export function draftConflictQuestionIds(conflicts) {
  const ids = new Set()
  for (const conflict of Array.isArray(conflicts) ? conflicts : []) {
    if (conflict?.question_id) ids.add(conflict.question_id)
  }
  return ids
}

export function dropDraftConflicts(conflicts, questionIds) {
  const dropped = new Set(questionIds || [])
  return (Array.isArray(conflicts) ? conflicts : []).filter(
    conflict => !dropped.has(conflict?.question_id),
  )
}

/**
 * Removes answers that are still locked behind an unresolved conflict. Sending
 * them again would look like a normal local edit once the base snapshot has
 * advanced to the server value, silently overwriting the other device's answer.
 */
export function withoutProtectedAnswers(payload, protectedQuestionIds) {
  const protectedIds = protectedQuestionIds instanceof Set
    ? protectedQuestionIds
    : new Set(protectedQuestionIds || [])
  const filtered = {}
  for (const [qid, value] of Object.entries(payload || {})) {
    if (protectedIds.has(qid)) continue
    filtered[qid] = value
  }
  return filtered
}

export function isEditorRole(role) {
  return role === 'ADMIN' || role === 'EDITOR'
}
