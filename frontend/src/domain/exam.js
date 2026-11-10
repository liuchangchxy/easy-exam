import { t } from '../composables/useLocale.js'
export function normalizeExamAnswer(type, value) {
  if (type === 'MULTI') {
    const selected = Array.isArray(value) ? value : typeof value === 'string' ? [...value] : []
    const uniqueSorted = Array.from(new Set(selected.map(String).map(s => s.trim().toUpperCase()))).filter(Boolean).sort()
    return uniqueSorted.join('')
  }
  if (type === 'FILL' || type === 'SHORT_ANSWER' || type === 'ESSAY' || type === 'SUBJECTIVE') {
    return typeof value === 'string' ? value.trim() : ''
  }
  return value ?? ''
}

export function examAnswerState(questionId, answers, flags) {
  const value = answers?.[questionId]
  const answer = value && typeof value === 'object' && !Array.isArray(value)
    ? value.user_answer ?? value.answer
    : value
  const answered = Array.isArray(answer) ? answer.length > 0 : String(answer ?? '').trim().length > 0
  return { answered, flagged: (flags || []).includes(questionId) }
}

export function formatRemainingTime(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  const pad = value => String(value).padStart(2, '0')
  return hours > 0 ? `${pad(hours)}:${pad(minutes)}:${pad(remainder)}` : `${pad(minutes)}:${pad(remainder)}`
}

export function formatQuestionTypeName(type) {
  const map = {
    SINGLE: t('ui.k0050'),
    MULTI: t('ui.k0051'),
    JUDGE: t('ui.k0052'),
    FILL: t('ui.k0053'),
    SHORT_ANSWER: t('ui.k0054'),
    ESSAY: t('ui.k0054'),
    SUBJECTIVE: t('ui.k0054'),
  }
  return map[String(type || '').toUpperCase()] || String(type || '')
}

export function calculateAccuracy(correct, attempted) {
  const att = Number(attempted) || 0
  const corr = Number(correct) || 0
  if (att <= 0) return '0.0%'
  return `${(Math.round((corr / att) * 1000) / 10).toFixed(1)}%`
}

export function isExamReviewItem(questionId, answers) {
  // The report's "wrong and blank" section covers every question that was not
  // answered fully correctly, including questions with no scored attempt.
  const entry = answers?.[questionId]
  return !entry || entry.correctness !== 'CORRECT'
}

export function normalizeDraftConflicts(conflicts, questions) {  // Draft sync merges per question and reports the values that lost the merge.
  // Keep only conflicts that still belong to the loaded paper, deduplicated by
  // question and ordered like the answer sheet so the notice is actionable.
  const order = new Map((questions || []).map((question, index) => [question?.id, index]))
  const byQuestion = new Map()
  for (const conflict of Array.isArray(conflicts) ? conflicts : []) {
    const questionId = conflict?.question_id
    if (!questionId || !order.has(questionId)) continue
    byQuestion.set(questionId, {
      question_id: questionId,
      question_number: order.get(questionId) + 1,
      existing_answer: conflict.existing_answer,
      incoming_answer: conflict.incoming_answer,
    })
  }
  return [...byQuestion.values()].sort((a, b) => a.question_number - b.question_number)
}

function rawDraftAnswer(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value.user_answer ?? value.answer ?? ''
  }
  return value ?? ''
}

function hasDraftAnswer(value) {
  if (Array.isArray(value)) return value.length > 0
  return String(value ?? '').trim().length > 0
}

/**
 * The server draft contract is optimistic: the client sends the values it last
 * observed as `base_answers`, so a cross-device write can be reported instead
 * of silently overwritten. Local answers are sent; a saved answer that was
 * cleared locally is sent as an explicit empty value.
 */
export function buildExamDraftPayload(answers, baseAnswers) {
  const payload = {}
  for (const qid of Object.keys(answers || {})) {
    const raw = rawDraftAnswer(answers[qid])
    const base = rawDraftAnswer(baseAnswers?.[qid])
    if (hasDraftAnswer(raw)) payload[qid] = raw
    else if (hasDraftAnswer(base)) payload[qid] = ''
  }
  return payload
}

export function buildExamDraftBase(payload, baseAnswers) {
  const base = {}
  for (const qid of Object.keys(payload || {})) {
    if (baseAnswers && Object.prototype.hasOwnProperty.call(baseAnswers, qid)) {
      base[qid] = rawDraftAnswer(baseAnswers[qid])
    }
  }
  return base
}

export function examAnswersToBase(answers) {
  const base = {}
  for (const [qid, value] of Object.entries(answers || {})) {
    base[qid] = rawDraftAnswer(value)
  }
  return base
}

export const EXAM_LOCAL_DRAFT_PREFIX = 'easyexam_exam_draft'

/**
 * Stable per-account scope for the exam device backup. Never falls back to a
 * shared literal: two accounts must not share an offline exam draft.
 */
export function resolveExamUserKey(user) {
  const id = user?.id ?? user?.username
  return id === undefined || id === null ? '' : String(id)
}

/**
 * Local draft backup key. A session id already belongs to exactly one user and
 * one exam paper, so this cannot merge another account's device backup into
 * this runner; the user key makes that isolation explicit in storage.
 */
export function examLocalDraftKey(sessionId, userKey) {
  if (!sessionId) return ''
  return userKey
    ? `${EXAM_LOCAL_DRAFT_PREFIX}_${userKey}_${sessionId}`
    : `${EXAM_LOCAL_DRAFT_PREFIX}_${sessionId}`
}

/** Network failures (offline, DNS, aborted fetch) are retryable; 4xx are not. */
export function isExamNetworkError(err) {
  return err?.status === 0 || err?.code === 'NETWORK_ERROR'
}

/**
 * Recognises the server's terminal exam-deadline rejection.
 *
 * The API may expose it as a stable error code, a structured detail object, or
 * only the marker embedded in the detail text (the route currently wraps the
 * service error). All three forms must stop the client's retry loop.
 */
export function isExamTimeExpiredError(err) {
  const code = err?.code ?? err?.error_code
  if (code === 'EXAM_TIME_EXPIRED') return true
  const structured = err?.structuredDetail
  if (structured && (structured.code === 'EXAM_TIME_EXPIRED' || structured.error_code === 'EXAM_TIME_EXPIRED')) {
    return true
  }
  const detail = err?.rawDetail ?? err?.detail ?? err?.message
  return typeof detail === 'string' && detail.includes('EXAM_TIME_EXPIRED')
}

/**
 * Local answers that never reached the server.
 *
 * The baseline is the last server snapshot this device observed, so anything
 * differing from it (and still non-empty) is a local answer the server does not
 * hold. Explicit local clears are not "answers" and are excluded.
 */
export function unsubmittedExamAnswers(answers, baseAnswers) {
  const result = []
  for (const [questionId, value] of Object.entries(answers || {})) {
    const raw = rawDraftAnswer(value)
    if (!hasDraftAnswer(raw)) continue
    const base = rawDraftAnswer(baseAnswers?.[questionId])
    if (JSON.stringify(raw) === JSON.stringify(base)) continue
    result.push({ question_id: questionId, answer: raw })
  }
  return result
}

/**
 * Serialises the runner's device-local state. Answers are stored as raw values
 * (never the server's `{ user_answer }` envelope) so they can be fed straight
 * back into the runner after a reload. Explicit empty values are kept: a clear
 * made offline is a real edit and must survive the reload. `base` is the server
 * snapshot this device last observed, which is what lets recovery distinguish
 * "my unsynced edit" from "another device wrote this while I was away".
 */
export function buildExamLocalDraft(state = {}, updatedAt = Date.now()) {
  const { answers, baseAnswers, flags, currentIndex, timeSpent, pendingSubmit } = state || {}
  const snapshot = {}
  for (const [qid, value] of Object.entries(answers || {})) {
    snapshot[qid] = rawDraftAnswer(value)
  }
  return {
    version: 1,
    answers: snapshot,
    base: examAnswersToBase(baseAnswers),
    flags: [...(flags || [])],
    currentIndex: Math.max(0, Math.floor(Number(currentIndex) || 0)),
    timeSpent: Math.max(0, Math.floor(Number(timeSpent) || 0)),
    pendingSubmit: Boolean(pendingSubmit),
    updatedAt,
  }
}

/**
 * Splits the local backup (this device's word) from the server's copy.
 *
 * Only values that differ from the baseline this device last observed are
 * unsynced local edits and win; values that merely match the old baseline are
 * stale and must lose to the freshly fetched server state. The winning local
 * values are then sent with the *old* baseline, so the server still reports a
 * cross-device conflict instead of silently overwriting the other device.
 */
export function mergeExamLocalDraft(serverAnswers, localDraft) {
  const merged = { ...(serverAnswers || {}) }
  if (!localDraft || typeof localDraft !== 'object' || !localDraft.answers) return merged
  const localBase = localDraft.base && typeof localDraft.base === 'object' ? localDraft.base : null
  for (const [qid, value] of Object.entries(localDraft.answers)) {
    if (localBase && JSON.stringify(rawDraftAnswer(value)) === JSON.stringify(rawDraftAnswer(localBase[qid]))) continue
    merged[qid] = value
  }
  return merged
}

/**
 * Baseline to send while replaying a restored local draft.
 *
 * Freshly fetched server values become the baseline for everything, except for
 * questions this device edited offline: those keep the baseline the device
 * actually observed, so the server can tell whether another device has written
 * in the meantime. Without this, replaying an edit with a freshly fetched
 * server value as `base` would silently overwrite the other device's change.
 */
export function examRecoveryBase(serverAnswers, localDraft) {
  const base = examAnswersToBase(serverAnswers)
  if (!localDraft || typeof localDraft !== 'object' || !localDraft.answers) return base
  const localBase = localDraft.base && typeof localDraft.base === 'object' ? localDraft.base : null
  if (!localBase) return base
  for (const [qid, value] of Object.entries(localDraft.answers)) {
    if (JSON.stringify(rawDraftAnswer(value)) !== JSON.stringify(rawDraftAnswer(localBase[qid]))) {
      base[qid] = rawDraftAnswer(localBase[qid])
    }
  }
  return base
}

/** True when the local backup holds an unsynced edit against its baseline. */
export function examLocalDraftDiffers(localDraft, observedAnswers) {
  if (!localDraft || typeof localDraft !== 'object' || !localDraft.answers) return false
  const base = localDraft.base && typeof localDraft.base === 'object'
    ? localDraft.base
    : examAnswersToBase(observedAnswers)
  for (const [qid, value] of Object.entries(localDraft.answers)) {
    if (JSON.stringify(rawDraftAnswer(value)) !== JSON.stringify(rawDraftAnswer(base[qid]))) return true
  }
  return false
}

export function findFirstUnansweredIndex(questions, answers) {
  if (!Array.isArray(questions)) return -1
  return questions.findIndex(q => {
    const state = examAnswerState(q.id, answers, [])
    return !state.answered
  })
}

export function findNextUnansweredIndex(questions, answers, currentIndex = 0) {
  if (!Array.isArray(questions) || !questions.length) return -1
  const len = questions.length
  // Search from currentIndex + 1 to end
  for (let i = currentIndex + 1; i < len; i++) {
    const state = examAnswerState(questions[i]?.id, answers, [])
    if (!state.answered) return i
  }
  // Wrap around from 0 to currentIndex
  for (let i = 0; i <= currentIndex; i++) {
    const state = examAnswerState(questions[i]?.id, answers, [])
    if (!state.answered) return i
  }
  return -1
}

export function formatVerdictTitle(questionType, correctness, isObjective) {
  const type = String(questionType || 'SINGLE').toUpperCase()
  if (!isObjective || type === 'ESSAY' || type === 'SHORT_ANSWER' || type === 'SUBJECTIVE') {
    return t('ui.k0055')
  }
  if (correctness === 'CORRECT') {
    return type === 'MULTI' ? t('ui.k0056') : t('ui.k0057')
  }
  if (correctness === 'PARTIAL' && type === 'MULTI') {
    return t('ui.k0058')
  }
  return t('ui.k0059')
}

export function isSwipeGestureValid(startX, startY, endX, endY, minDistance = 50) {
  // Prevent edge gesture collision with iOS / browser back navigation (first 25px)
  if (startX <= 25) return null
  const deltaX = endX - startX
  const deltaY = endY - startY
  const absX = Math.abs(deltaX)
  const absY = Math.abs(deltaY)

  if (absX < minDistance) return null
  // Must be primarily horizontal (|deltaX| > |deltaY| * 1.5)
  if (absX <= absY * 1.5) return null

  return deltaX < 0 ? 'next' : 'prev'
}

