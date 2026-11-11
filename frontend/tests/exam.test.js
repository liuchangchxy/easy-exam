import assert from 'node:assert/strict'
import test from 'node:test'
import { buildExamDraftBase, buildExamDraftPayload, buildExamLocalDraft, calculateAccuracy, examAnswerState, examAnswersToBase, examLocalDraftDiffers, examLocalDraftKey, examRecoveryBase, findFirstUnansweredIndex, findNextUnansweredIndex, formatQuestionTypeName, formatRemainingTime, formatVerdictTitle, isExamNetworkError, isExamTimeExpiredError, isExamReviewItem, isSwipeGestureValid, mergeExamLocalDraft, normalizeDraftConflicts, normalizeExamAnswer, resolveExamUserKey, unsubmittedExamAnswers } from '../src/domain/exam.js'
import { setLocale } from '../src/composables/useLocale.js'

setLocale('zh-CN')

test('multi-select answers are normalized deterministically for submission', () => {
  assert.equal(normalizeExamAnswer('MULTI', ['C', 'A', 'B']), 'ABC')
  assert.equal(normalizeExamAnswer('MULTI', ['b', 'A', 'b', 'c']), 'ABC')
  assert.equal(normalizeExamAnswer('MULTI', 'bdca'), 'ABCD')
  assert.equal(normalizeExamAnswer('MULTI', []), '')
  assert.equal(normalizeExamAnswer('MULTI', null), '')
  assert.equal(normalizeExamAnswer('SINGLE', 'D'), 'D')
  assert.equal(normalizeExamAnswer('FILL', '  hello world  '), 'hello world')
})


test('exam answer sheet distinguishes unanswered, answered, and flagged questions', () => {
  assert.deepEqual(examAnswerState('q1', {}, []), { answered: false, flagged: false })
  assert.deepEqual(examAnswerState('q1', { q1: ['A'] }, []), { answered: true, flagged: false })
  assert.deepEqual(examAnswerState('q1', {}, ['q1']), { answered: false, flagged: true })
  assert.deepEqual(examAnswerState('q1', { q1: 'text' }, ['q1']), { answered: true, flagged: true })
})

test('countdown formatting is stable below and above one hour', () => {
  assert.equal(formatRemainingTime(59), '00:59')
  assert.equal(formatRemainingTime(3600), '01:00:00')
})

test('formatQuestionTypeName maps domain codes to friendly Chinese labels', () => {
  assert.equal(formatQuestionTypeName('SINGLE'), '单选题')
  assert.equal(formatQuestionTypeName('MULTI'), '多选题')
  assert.equal(formatQuestionTypeName('JUDGE'), '判断题')
  assert.equal(formatQuestionTypeName('ESSAY'), '主观题')
  assert.equal(formatQuestionTypeName('UNKNOWN'), 'UNKNOWN')
})

test('calculateAccuracy calculates percentage safely without division by zero', () => {
  assert.equal(calculateAccuracy(3, 4), '75.0%')
  assert.equal(calculateAccuracy(0, 0), '0.0%')
})

test('findFirstUnansweredIndex locates first unanswered question accurately', () => {
  const questions = [{ id: 'q1' }, { id: 'q2' }, { id: 'q3' }]
  const answers = { q1: 'A' }
  assert.equal(findFirstUnansweredIndex(questions, answers), 1)

  const allAnswered = { q1: 'A', q2: 'B', q3: 'C' }
  assert.equal(findFirstUnansweredIndex(questions, allAnswered), -1)

  const noneAnswered = {}
  assert.equal(findFirstUnansweredIndex(questions, noneAnswered), 0)

  assert.equal(findFirstUnansweredIndex([], {}), -1)
  assert.equal(findFirstUnansweredIndex(null, {}), -1)
})

test('formatVerdictTitle accurately differentiates single choice wrong from multi choice partial', () => {
  // Single choice
  assert.equal(formatVerdictTitle('SINGLE', 'CORRECT', true), '回答正确！')
  assert.equal(formatVerdictTitle('SINGLE', 'INCORRECT', true), '回答错误')

  // Judge question
  assert.equal(formatVerdictTitle('JUDGE', 'CORRECT', true), '回答正确！')
  assert.equal(formatVerdictTitle('JUDGE', 'INCORRECT', true), '回答错误')

  // Multi choice
  assert.equal(formatVerdictTitle('MULTI', 'CORRECT', true), '回答完全正确！')
  assert.equal(formatVerdictTitle('MULTI', 'PARTIAL', true), '部分得分（漏选）')
  assert.equal(formatVerdictTitle('MULTI', 'INCORRECT', true), '回答错误')

  // Subjective
  assert.equal(formatVerdictTitle('ESSAY', 'UNANSWERED', false), '作答已保存（主观题）')
})

test('findNextUnansweredIndex finds next unanswered from current position with wrap-around', () => {
  const questions = [{ id: 'q1' }, { id: 'q2' }, { id: 'q3' }, { id: 'q4' }]
  // q1 and q3 answered. Current is at index 0 (q1). Next unanswered should be index 1 (q2).
  const answers = { q1: 'A', q3: 'B' }
  assert.equal(findNextUnansweredIndex(questions, answers, 0), 1)

  // Current is at index 1 (q2). Next unanswered should be index 3 (q4).
  assert.equal(findNextUnansweredIndex(questions, answers, 1), 3)

  // Current is at index 3 (q4). Next unanswered wraps around to index 1 (q2).
  assert.equal(findNextUnansweredIndex(questions, answers, 3), 1)

  // All answered returns -1
  assert.equal(findNextUnansweredIndex(questions, { q1: 'A', q2: 'B', q3: 'C', q4: 'D' }, 0), -1)
})

test('isSwipeGestureValid recognizes horizontal swipes and guards against edge/diagonal gestures', () => {  // Valid left swipe (Next): moved from 200, 200 to 120, 205 (deltaX = -80, deltaY = 5)
  assert.equal(isSwipeGestureValid(200, 200, 120, 205), 'next')

  // Valid right swipe (Prev): moved from 200, 200 to 280, 205 (deltaX = +80, deltaY = 5)
  assert.equal(isSwipeGestureValid(200, 200, 280, 205), 'prev')

  // Distance too short (< 50px)
  assert.equal(isSwipeGestureValid(200, 200, 230, 205), null)

  // Vertical scroll / diagonal movement (|deltaY| is large)
  assert.equal(isSwipeGestureValid(200, 200, 280, 300), null)

  // Left-edge protection for iOS Safari back swipe (startX <= 25)
  assert.equal(isSwipeGestureValid(15, 200, 100, 200), null)
})

test('isExamReviewItem includes wrong, partial and blank questions but not correct ones', () => {
  const answers = {
    q1: { correctness: 'CORRECT' },
    q2: { correctness: 'PARTIAL' },
    q3: { correctness: 'INCORRECT' },
    q4: { correctness: 'UNANSWERED' },
  }
  assert.equal(isExamReviewItem('q1', answers), false)
  assert.equal(isExamReviewItem('q2', answers), true)
  assert.equal(isExamReviewItem('q3', answers), true)
  assert.equal(isExamReviewItem('q4', answers), true)
  assert.equal(isExamReviewItem('missing', answers), true)
  assert.equal(isExamReviewItem('q1', undefined), true)
})

test('normalizeDraftConflicts keeps loaded questions, numbers them and deduplicates', () => {
  const questions = [{ id: 'q1' }, { id: 'q2' }, { id: 'q3' }]
  const conflicts = [
    { question_id: 'q3', existing_answer: 'C', incoming_answer: 'A' },
    { question_id: 'q1', existing_answer: 'B', incoming_answer: 'D' },
    { question_id: 'q3', existing_answer: 'C', incoming_answer: 'A' },
    { question_id: 'gone', existing_answer: 'A', incoming_answer: 'B' },
  ]
  assert.deepEqual(normalizeDraftConflicts(conflicts, questions), [
    { question_id: 'q1', question_number: 1, existing_answer: 'B', incoming_answer: 'D' },
    { question_id: 'q3', question_number: 3, existing_answer: 'C', incoming_answer: 'A' },
  ])
  assert.deepEqual(normalizeDraftConflicts(null, questions), [])
  assert.deepEqual(normalizeDraftConflicts(conflicts, []), [])
})

test('exam draft payload sends only local changes with the observed server baseline', () => {
  const base = { q1: 'A', q2: 'B' }
  const answers = {
    q1: 'A',
    q2: { user_answer: 'C' },
    q3: 'D',
    q4: [],
    q5: '',
  }
  const payload = buildExamDraftPayload(answers, base)
  assert.deepEqual(payload, { q1: 'A', q2: 'C', q3: 'D' })

  // Clearing a saved answer is an explicit change and must be sent.
  assert.deepEqual(buildExamDraftPayload({ q1: '' }, { q1: 'A' }), { q1: '' })
  assert.deepEqual(buildExamDraftBase(payload, { ...base, q3: '' }), { q1: 'A', q2: 'B', q3: '' })
  assert.deepEqual(examAnswersToBase({ q1: { answer: 'A' }, q2: ['B', 'C'], q3: null }), { q1: 'A', q2: ['B', 'C'], q3: '' })
})

test('local exam draft key is scoped to the exam session only', () => {
  assert.equal(examLocalDraftKey('s1'), 'easyexam_exam_draft_s1')
  assert.equal(examLocalDraftKey(''), '')
  assert.equal(examLocalDraftKey(null), '')
})

test('local exam draft snapshot flattens envelopes and keeps explicit clears', () => {
  const snapshot = buildExamLocalDraft({
    answers: { q1: { user_answer: 'A' }, q2: ['B', 'C'], q3: '', q4: null },
    baseAnswers: { q1: 'C', q4: 'B' },
    flags: ['q2', 'q2'],
    currentIndex: 3,
    timeSpent: 47.9,
    pendingSubmit: true,
  }, 1234)
  assert.deepEqual(snapshot, {
    version: 1,
    answers: { q1: 'A', q2: ['B', 'C'], q3: '', q4: '' },
    base: { q1: 'C', q4: 'B' },
    flags: ['q2', 'q2'],
    currentIndex: 3,
    timeSpent: 47,
    pendingSubmit: true,
    updatedAt: 1234,
  })
  assert.deepEqual(buildExamLocalDraft(null, 1).answers, {})
  assert.deepEqual(buildExamLocalDraft(null, 1).base, {})
  assert.equal(buildExamLocalDraft({ currentIndex: -2, timeSpent: -5 }).currentIndex, 0)
})

test('restoring a local exam draft keeps unsynced device edits and defers to fresher server values', () => {
  const server = { q1: { user_answer: 'B' }, q2: { user_answer: 'C' }, q3: { user_answer: 'D' } }
  // q1 was edited offline, q2 was not; q3 exists only on the server.
  const local = { answers: { q1: 'A', q2: 'C' }, base: { q1: 'B', q2: 'C' } }
  assert.deepEqual(mergeExamLocalDraft(server, local), {
    q1: 'A',
    q2: { user_answer: 'C' },
    q3: { user_answer: 'D' },
  })
  // No backup or a malformed backup must not change the server view.
  assert.deepEqual(mergeExamLocalDraft(server, null), server)
  assert.deepEqual(mergeExamLocalDraft(server, { answers: null }), server)

  // A legacy backup without a baseline behaves like the whole local map.
  assert.deepEqual(mergeExamLocalDraft(server, { answers: { q1: 'E' } }), { ...server, q1: 'E' })
})

test('recovery baseline keeps the old observed value only for unsynced local edits', () => {
  // The server moved q2 on after this device's last sync; q1 is an offline edit.
  const server = { q1: { user_answer: 'B' }, q2: { user_answer: 'D' } }
  const local = { answers: { q1: 'A', q2: 'C' }, base: { q1: 'B', q2: 'C' } }
  // q1 keeps its old baseline (B) so a cross-device write is reportable; q2 was
  // not edited locally, so the fresh server value D is the correct baseline.
  assert.deepEqual(examRecoveryBase(server, local), { q1: 'B', q2: 'D' })
  // Untouched questions use the freshly fetched server value as baseline so
  // they are not re-sent as a false local change.
  assert.deepEqual(examRecoveryBase(server, null), { q1: 'B', q2: 'D' })
  assert.deepEqual(examRecoveryBase(server, { answers: { q1: 'A' } }), { q1: 'B', q2: 'D' })
})

test('local exam draft divergence only reports unsynced edits against the observed baseline', () => {
  const server = { q1: { user_answer: 'A' }, q2: { user_answer: '' } }
  assert.equal(examLocalDraftDiffers({ answers: { q1: 'A', q2: '' }, base: { q1: 'A', q2: '' } }, server), false)
  assert.equal(examLocalDraftDiffers({ answers: { q1: 'B' }, base: { q1: 'A' } }, server), true)
  // A locally cleared answer is a real difference from a saved server value.
  assert.equal(examLocalDraftDiffers({ answers: { q1: '' }, base: { q1: 'A' } }, server), true)
  // A server-only entry does not count as a local divergence.
  assert.equal(examLocalDraftDiffers({ answers: {} }, server), false)
  assert.equal(examLocalDraftDiffers(null, server), false)
  // A legacy backup without a baseline compares against the fetched server.
  assert.equal(examLocalDraftDiffers({ answers: { q1: 'A' } }, server), false)
  assert.equal(examLocalDraftDiffers({ answers: { q1: 'C' } }, server), true)
})

test('network failures are the only draft errors treated as retryable offline state', () => {
  assert.equal(isExamNetworkError({ status: 0, code: 'NETWORK_ERROR' }), true)
  assert.equal(isExamNetworkError({ code: 'NETWORK_ERROR' }), true)
  assert.equal(isExamNetworkError({ status: 409, code: 'HTTP_409' }), false)
  assert.equal(isExamNetworkError(new Error('boom')), false)
  assert.equal(isExamNetworkError(null), false)
})

test('EXAM_TIME_EXPIRED is recognised from code, structured detail, or detail text', () => {
  assert.equal(isExamTimeExpiredError({ code: 'EXAM_TIME_EXPIRED' }), true)
  assert.equal(isExamTimeExpiredError({ error_code: 'EXAM_TIME_EXPIRED' }), true)
  assert.equal(isExamTimeExpiredError({ structuredDetail: { code: 'EXAM_TIME_EXPIRED' } }), true)
  assert.equal(isExamTimeExpiredError({ rawDetail: '模考时间已到，已超时，请交卷 [EXAM_TIME_EXPIRED]' }), true)
  assert.equal(isExamTimeExpiredError({ detail: 'boom [EXAM_TIME_EXPIRED]' }), true)
  assert.equal(isExamTimeExpiredError({ message: 'x EXAM_TIME_EXPIRED y' }), true)
  // Ordinary 409s and network failures must keep their existing handling.
  assert.equal(isExamTimeExpiredError({ status: 409, code: 'HTTP_409', detail: 'session already completed' }), false)
  assert.equal(isExamTimeExpiredError({ status: 0, code: 'NETWORK_ERROR' }), false)
  assert.equal(isExamTimeExpiredError(null), false)
})

test('unsubmitted exam answers are exactly the non-empty local changes', () => {
  const base = { q1: 'A', q2: 'B', q3: '' }
  const answers = {
    q1: 'A',              // unchanged
    q2: { user_answer: 'C' }, // changed locally
    q3: '',               // explicit clear, not an answer
    q4: ['D', 'E'],       // new local answer
    q5: '',               // empty, nothing to submit
  }
  assert.deepEqual(unsubmittedExamAnswers(answers, base), [
    { question_id: 'q2', answer: 'C' },
    { question_id: 'q4', answer: ['D', 'E'] },
  ])
  assert.deepEqual(unsubmittedExamAnswers({}, base), [])
})

test('exam device drafts are scoped per account as well as per session', () => {
  assert.equal(resolveExamUserKey({ id: 'u1' }), 'u1')
  assert.equal(resolveExamUserKey({ username: 'alice' }), 'alice')
  assert.equal(resolveExamUserKey(null), '')

  const first = examLocalDraftKey('s1', 'u1')
  const second = examLocalDraftKey('s1', 'u2')
  assert.equal(first, 'easyexam_exam_draft_u1_s1')
  assert.notEqual(first, second, 'two accounts must not share a device draft')
  // Legacy session-only keys remain readable for migration.
  assert.equal(examLocalDraftKey('s1'), 'easyexam_exam_draft_s1')
  assert.equal(examLocalDraftKey('s1', ''), 'easyexam_exam_draft_s1')
})
