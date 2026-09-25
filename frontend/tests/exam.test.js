import assert from 'node:assert/strict'
import test from 'node:test'

import { calculateAccuracy, examAnswerState, formatQuestionTypeName, formatRemainingTime, normalizeExamAnswer } from '../src/domain/exam.js'

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

