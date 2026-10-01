import assert from 'node:assert/strict'
import test from 'node:test'
import {
  hydrateSessionPractice,
  normalizeQuestionOptions,
  shouldResetQuestionForm,
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
