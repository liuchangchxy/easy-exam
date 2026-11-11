import assert from 'node:assert/strict'
import test from 'node:test'
import {
  answersToBaseMap,
  buildDraftAnswerPayload,
  buildDraftBasePayload,
  clientAttemptIdOf,
  clientAttemptIdsFromDraft,
  createClientAttemptId,
  draftConflictQuestionIds,
  dropDraftConflicts,
  hydrateSessionPractice,
  isEmptyAnswer,
  isEditorRole,
  isNetworkError,
  localPracticeDraftKey,
  mergeDraftConflicts,
  mergeEditQueues,
  mergeLocalDraftEntries,
  normalizeQuestionOptions,
  offlineAttemptQueueKey,
  offlineEditQueueKey,
  parseServerTimestamp,
  partitionLegacyEditQueue,
  practiceDraftConflictKey,
  rawDraftAnswer,
  removePendingAttempt,
  resolvePracticeUserKey,
  shouldResetQuestionForm,
  snapshotLocalDraft,
  upsertPendingAttempt,
  withoutProtectedAnswers,
} from '../src/domain/practice.js'

test('hydrateSessionPractice restores index within boundary and extracts answers', () => {
  const session = {
    current_index: 3,
    answers: {
      q1: { answer: 'A', result: { correctness: 'CORRECT' } },
      q2: { answer: 'B', result: { correctness: 'INCORRECT' } }
    }
  }

  const hydrated = hydrateSessionPractice(session, 10)
  assert.equal(hydrated.currentIndex, 3)
  assert.equal(Object.keys(hydrated.sessionAnswers).length, 2)
  assert.equal(hydrated.sessionAnswers.q1.answer, 'A')

  // Clamps out of bound indices
  const clamped = hydrateSessionPractice({ current_index: 99 }, 5)
  assert.equal(clamped.currentIndex, 4)

  // Handles null / empty session gracefully
  const empty = hydrateSessionPractice(null, 5)
  assert.equal(empty.currentIndex, 0)
  assert.deepEqual(empty.sessionAnswers, {})
})

test('normalizeQuestionOptions ensures { key, content } contract and handles fallback', () => {
  const rawStandard = [{ key: 'A', content: '选项一' }, { key: 'B', content: '选项二' }]
  assert.deepEqual(normalizeQuestionOptions(rawStandard), [
    { key: 'A', content: '选项一' },
    { key: 'B', content: '选项二' }
  ])

  // Handles legacy { text } schema seamlessly
  const rawLegacy = [{ key: 'A', text: '旧版选项一' }, { text: '旧版选项二无Key' }]
  const normalized = normalizeQuestionOptions(rawLegacy)
  assert.equal(normalized[0].content, '旧版选项一')
  assert.equal(normalized[1].key, 'B')
  assert.equal(normalized[1].content, '旧版选项二无Key')

  // Handles non-array gracefully
  assert.deepEqual(normalizeQuestionOptions(null), [])
  assert.deepEqual(normalizeQuestionOptions(undefined), [])
})

test('shouldResetQuestionForm detects question ID changes for editing scope isolation', () => {
  assert.equal(shouldResetQuestionForm({ id: 'q1' }, null), true)
  assert.equal(shouldResetQuestionForm(null, { id: 'q1' }), true)
  assert.equal(shouldResetQuestionForm({ id: 'q2' }, { id: 'q1' }), true)
  assert.equal(shouldResetQuestionForm({ id: 'q1' }, { id: 'q1' }), false)
})

test('resolvePracticeUserKey never falls back to a shared literal', () => {
  assert.equal(resolvePracticeUserKey({ id: 'user-1' }), 'user-1')
  assert.equal(resolvePracticeUserKey({ username: 'alice' }), 'alice')
  assert.equal(resolvePracticeUserKey(null), '')
  assert.equal(resolvePracticeUserKey({}), '')
})

test('offline and draft storage keys are scoped per account', () => {
  assert.equal(offlineEditQueueKey('u1'), 'easyexam_offline_question_edits_u1')
  assert.equal(offlineAttemptQueueKey('u1'), 'easyexam_offline_attempts_u1')
  assert.equal(localPracticeDraftKey('u1', 's1'), 'easyexam_practice_draft_u1_s1')
  assert.equal(offlineEditQueueKey(''), '')
  assert.equal(offlineAttemptQueueKey('u2').includes('u1'), false)
})

test('partitionLegacyEditQueue keeps other accounts items in the legacy queue', () => {
  const queue = [
    { userId: 'u1', questionId: 'q1' },
    { userId: 'u2', questionId: 'q2' },
    { userId: 'u1', questionId: 'q3' },
  ]
  const { mine, others } = partitionLegacyEditQueue(queue, 'u1')
  assert.deepEqual(mine.map(item => item.questionId), ['q1', 'q3'])
  assert.deepEqual(others.map(item => item.questionId), ['q2'])
})

test('buildDraftAnswerPayload sends typed answers and explicit clears only', () => {
  const answers = {
    q1: { answer: 'A', textAnswer: '' },
    q2: { answer: '', textAnswer: 'typed answer' },
    q3: { answer: '' },
    q4: { answer: '' },
    q5: { answer: 'B', result: { correctness: 'CORRECT' } },
  }
  const base = { q1: '', q2: '', q3: 'C', q5: '' }
  assert.deepEqual(buildDraftAnswerPayload(answers, base), {
    q1: 'A',
    q2: 'typed answer',
    q3: '',
    q5: 'B',
  })
  assert.equal(rawDraftAnswer({ user_answer: ['A', 'B'] }).length, 2)
  assert.deepEqual(answersToBaseMap({ q1: { answer: 'A' } }), { q1: 'A' })
  assert.deepEqual(buildDraftBasePayload({ q1: 'A', q3: '' }, { q1: 'C' }), { q1: 'C', q3: '' })
  assert.equal(isEmptyAnswer('   '), true)
  assert.equal(isEmptyAnswer(['A']), false)
})

test('mergeLocalDraftEntries honours numeric timestamps and never rewrites scored answers', () => {
  const serverAt = '2026-11-11 10:00:00'
  const serverMs = parseServerTimestamp(serverAt)
  const localDraft = snapshotLocalDraft(
    { q1: { answer: 'C' }, q2: { answer: 'D' } },
    serverMs + 60_000,
  )
  const merged = mergeLocalDraftEntries(
    {
      q1: { answer: 'A' },
      q2: { answer: 'B', result: { correctness: 'CORRECT' } },
    },
    localDraft,
    serverAt,
  )
  assert.equal(merged.q1.answer, 'C', 'newer local draft should win')
  assert.equal(merged.q2.answer, 'B', 'scored answer must not be overwritten')
  assert.equal(merged.q2.result.correctness, 'CORRECT')

  const staleDraft = snapshotLocalDraft({ q1: { answer: 'Z' } }, serverMs - 60_000)
  const staleMerged = mergeLocalDraftEntries({ q1: { answer: 'A' } }, staleDraft, serverAt)
  assert.equal(staleMerged.q1.answer, 'A', 'older local draft must not clobber the server')
})

test('parseServerTimestamp reads zoneless SQLite timestamps as UTC, not local time', () => {
  // SQLite CURRENT_TIMESTAMP: no zone marker, value is UTC.
  assert.equal(parseServerTimestamp('2026-11-11 10:00:00'), Date.parse('2026-11-11T10:00:00Z'))
  assert.equal(parseServerTimestamp('2026-11-11T10:00:00'), Date.parse('2026-11-11T10:00:00Z'))
  // Explicit zones are preserved as written.
  assert.equal(parseServerTimestamp('2026-11-11T10:00:00Z'), Date.parse('2026-11-11T10:00:00Z'))
  assert.equal(parseServerTimestamp('2026-11-11T18:00:00+08:00'), Date.parse('2026-11-11T10:00:00Z'))
  assert.equal(parseServerTimestamp(1762855200000), 1762855200000)
  assert.ok(Number.isNaN(parseServerTimestamp('')))
  assert.ok(Number.isNaN(parseServerTimestamp(null)))
})

test('UTC+8 clients never let an older local draft outrank the server write', () => {
  // Server wrote at 10:00 UTC (18:00 in UTC+8). A local backup saved one minute
  // before that instant must lose; naive local parsing would shift the server
  // value back by eight hours and make the stale draft win.
  const serverAt = '2026-11-11 10:00:00'
  const staleDraft = snapshotLocalDraft(
    { q1: { answer: 'Z' } },
    Date.parse('2026-11-11T09:59:00Z'),
  )
  const merged = mergeLocalDraftEntries({ q1: { answer: 'A' } }, staleDraft, serverAt)
  assert.equal(merged.q1.answer, 'A', 'older local draft must not clobber the UTC server value')

  const fresherDraft = snapshotLocalDraft(
    { q1: { answer: 'Z' } },
    Date.parse('2026-11-11T10:01:00Z'),
  )
  const fresher = mergeLocalDraftEntries({ q1: { answer: 'A' } }, fresherDraft, serverAt)
  assert.equal(fresher.q1.answer, 'Z', 'a genuinely newer local draft still wins')
})

test('unresolved draft conflicts accumulate, persist per account, and lock their answers', () => {
  assert.equal(
    practiceDraftConflictKey('u1', 's1'),
    'easyexam_practice_draft_conflicts_u1_s1',
  )
  assert.equal(practiceDraftConflictKey('', 's1'), '')

  const first = { question_id: 'q1', existing_answer: 'B', incoming_answer: 'A' }
  const second = { question_id: 'q2', existing_answer: 'D', incoming_answer: 'C' }
  const fresher = { question_id: 'q1', existing_answer: 'E', incoming_answer: 'A' }
  const merged = mergeDraftConflicts([first], [fresher, second])
  assert.equal(merged.length, 2)
  assert.equal(merged.find(c => c.question_id === 'q1').existing_answer, 'E')

  // A response without new conflicts must not clear the unresolved set.
  assert.equal(mergeDraftConflicts(merged, []).length, 2)

  const ids = draftConflictQuestionIds(merged)
  assert.deepEqual([...ids].sort(), ['q1', 'q2'])
  assert.deepEqual([...draftConflictQuestionIds(null)], [])

  assert.deepEqual(dropDraftConflicts(merged, ['q1']).map(c => c.question_id), ['q2'])

  const payload = { q1: 'A', q2: 'C', q3: 'B' }
  assert.deepEqual(withoutProtectedAnswers(payload, ids), { q3: 'B' })
  assert.deepEqual(withoutProtectedAnswers(payload, ['q1']), { q2: 'C', q3: 'B' })
  assert.deepEqual(withoutProtectedAnswers(payload, []), payload)
})

test('pending attempt queue upserts per session+question and removes on success', () => {
  const first = { sessionId: 's1', questionId: 'q1', answer: 'A' }
  const replacement = { sessionId: 's1', questionId: 'q1', answer: 'B' }
  const other = { sessionId: 's1', questionId: 'q2', answer: 'C' }
  let queue = upsertPendingAttempt([], first)
  queue = upsertPendingAttempt(queue, replacement)
  queue = upsertPendingAttempt(queue, other)
  assert.equal(queue.length, 2)
  assert.equal(queue.find(item => item.questionId === 'q1').answer, 'B')

  queue = removePendingAttempt(queue, 's1', 'q1')
  assert.deepEqual(queue.map(item => item.questionId), ['q2'])
})

test('client attempt ids are stable per operation and unique across operations', () => {
  const first = createClientAttemptId('practice-answer')
  const second = createClientAttemptId('practice-answer')
  assert.match(first, /^practice-answer-/)
  assert.notEqual(first, second)
  assert.ok(first.length <= 200)
  assert.equal(clientAttemptIdOf({ clientAttemptId: first }), first)
  assert.equal(clientAttemptIdOf({ client_attempt_id: first }), first)
  assert.equal(clientAttemptIdOf({}), '')
  assert.equal(clientAttemptIdOf(null), '')
})

test('one queue entry carries both the answer and its rating without overwriting each other', () => {
  const attemptId = 'practice-answer-1'
  let queue = upsertPendingAttempt([], {
    sessionId: 's1', questionId: 'q1', user_answer: 'A', fsrs_rating: null, clientAttemptId: attemptId,
  })
  queue = upsertPendingAttempt(queue, {
    sessionId: 's1', questionId: 'q1', user_answer: 'A', fsrs_rating: 3, clientAttemptId: attemptId,
  })
  assert.equal(queue.length, 1)
  assert.equal(queue[0].user_answer, 'A', 'rating must not drop the answer')
  assert.equal(queue[0].fsrs_rating, 3, 'answer replay must not drop the rating')

  // A rating queued before the answer keeps the rating when the answer arrives.
  let reversed = upsertPendingAttempt([], {
    sessionId: 's1', questionId: 'q1', user_answer: 'A', fsrs_rating: 2, clientAttemptId: 'k1',
  })
  reversed = upsertPendingAttempt(reversed, {
    sessionId: 's1', questionId: 'q1', user_answer: 'A', clientAttemptId: 'k1',
  })
  assert.equal(reversed[0].fsrs_rating, 2)

  // A genuinely new operation has a new key and is not collapsed into the old one.
  const withNew = upsertPendingAttempt(queue, {
    sessionId: 's1', questionId: 'q1', user_answer: 'B', clientAttemptId: 'practice-answer-2',
  })
  assert.equal(withNew.length, 2)

  // Removing one operation by key leaves the other queued operation intact.
  const removed = removePendingAttempt(withNew, 's1', 'q1', 'practice-answer-1')
  assert.equal(removed.length, 1)
  assert.equal(removed[0].clientAttemptId, 'practice-answer-2')
})

test('local draft snapshots persist per-question client attempt ids', () => {
  const snapshot = snapshotLocalDraft(
    { q1: { answer: 'A' } },
    1234,
    { q1: 'practice-answer-1', q2: '  ' },
  )
  assert.deepEqual(snapshot.clientAttemptIds, { q1: 'practice-answer-1' })
  assert.deepEqual(clientAttemptIdsFromDraft(snapshot), { q1: 'practice-answer-1' })
  assert.deepEqual(clientAttemptIdsFromDraft(null), {})
  assert.deepEqual(clientAttemptIdsFromDraft({ answers: {} }), {})
  // Without keys the snapshot shape stays backwards compatible.
  assert.equal('clientAttemptIds' in snapshotLocalDraft({ q1: { answer: 'A' } }, 1), false)
})

test('mergeEditQueues deduplicates identical edits without dropping distinct ones', () => {
  const a = [{ questionId: 'q1', payload: { stem: 'x' } }]
  const b = [{ questionId: 'q1', payload: { stem: 'x' } }, { questionId: 'q2', payload: { stem: 'y' } }]
  assert.deepEqual(mergeEditQueues(a, b).map(item => item.questionId), ['q1', 'q2'])
})

test('isEditorRole and isNetworkError gate sensitive UI and offline retries', () => {
  assert.equal(isEditorRole('ADMIN'), true)
  assert.equal(isEditorRole('EDITOR'), true)
  assert.equal(isEditorRole('MEMBER'), false)
  assert.equal(isEditorRole(undefined), false)
  assert.equal(isNetworkError({ status: 0 }), true)
  assert.equal(isNetworkError({ code: 'NETWORK_ERROR' }), true)
  assert.equal(isNetworkError({ status: 409 }), false)
})
