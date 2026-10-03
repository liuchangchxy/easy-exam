import assert from 'node:assert/strict'
import test from 'node:test'
import { calculateAccuracy, examAnswerState, findFirstUnansweredIndex, findNextUnansweredIndex, formatQuestionTypeName, formatRemainingTime, formatVerdictTitle, isSwipeGestureValid, normalizeExamAnswer } from '../src/domain/exam.js'
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

test('isSwipeGestureValid recognizes horizontal swipes and guards against edge/diagonal gestures', () => {
  // Valid left swipe (Next): moved from 200, 200 to 120, 205 (deltaX = -80, deltaY = 5)
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
