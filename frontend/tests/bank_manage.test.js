import assert from 'node:assert/strict'
import test from 'node:test'
import {
  createEmptyBankFilters,
  isFilterActive,
  canEditBankContent,
  canEditQuestionInBank,
  filterBankQuestions,
  validateQuestionEdit,
  sanitizeAnswerOnOptionRemove,
} from '../src/domain/bankManage.js'

const sampleQuestions = [
  {
    id: 'q1',
    stem: 'What is the speed of light in a vacuum?',
    type: 'SINGLE',
    difficulty: 2,
    tags: ['physics', 'optics'],
    chapter_id: 'chap-1',
    version_number: 1,
  },
  {
    id: 'q2',
    stem: 'Select all prime numbers below 10.',
    type: 'MULTI',
    difficulty: 3,
    tags: ['math', 'numbers'],
    chapter_id: 'chap-2',
    version_number: 2,
  },
  {
    id: 'q3',
    stem: 'Water boils at 100 degrees Celsius at 1 atm.',
    type: 'JUDGE',
    difficulty: 1,
    tags: ['chemistry', 'physics'],
    chapter_id: 'chap-1',
    version_number: 1,
  },
  {
    id: 'q4',
    stem: 'Explain the theory of general relativity.',
    type: 'ESSAY',
    difficulty: 5,
    tags: ['physics', 'advanced'],
    chapter_id: null,
    version_number: 3,
  },
]

test('createEmptyBankFilters creates default blank filter state', () => {
  const filters = createEmptyBankFilters()
  assert.deepEqual(filters, {
    keyword: '',
    type: '',
    difficulty: '',
    tag: '',
    chapterId: '',
  })
  assert.equal(isFilterActive(filters), false)
})

test('isFilterActive detects any active filter criteria', () => {
  assert.equal(isFilterActive({ keyword: 'light', type: '', difficulty: '', tag: '', chapterId: '' }), true)
  assert.equal(isFilterActive({ keyword: '', type: 'SINGLE', difficulty: '', tag: '', chapterId: '' }), true)
  assert.equal(isFilterActive({ keyword: '', type: '', difficulty: 3, tag: '', chapterId: '' }), true)
  assert.equal(isFilterActive({ keyword: '', type: '', difficulty: '', tag: 'math', chapterId: '' }), true)
  assert.equal(isFilterActive({ keyword: '', type: '', difficulty: '', tag: '', chapterId: 'chap-1' }), true)
  assert.equal(isFilterActive({ keyword: '   ', type: '', difficulty: '', tag: '', chapterId: '' }), false)
})

test('canEditBankContent allows ADMIN and EDITOR, disallows MEMBER and null', () => {
  assert.equal(canEditBankContent('ADMIN'), true)
  assert.equal(canEditBankContent('admin'), true)
  assert.equal(canEditBankContent('EDITOR'), true)
  assert.equal(canEditBankContent('editor'), true)
  assert.equal(canEditBankContent('MEMBER'), false)
  assert.equal(canEditBankContent('member'), false)
  assert.equal(canEditBankContent(''), false)
  assert.equal(canEditBankContent(null), false)
  assert.equal(canEditBankContent(undefined), false)
})

test('canEditQuestionInBank checks active exam safety condition', () => {
  assert.equal(canEditQuestionInBank({ role: 'ADMIN', hasActiveExam: false }), true)
  assert.equal(canEditQuestionInBank({ role: 'EDITOR', hasActiveExam: false }), true)
  // Active exam blocks editing even for admin
  assert.equal(canEditQuestionInBank({ role: 'ADMIN', hasActiveExam: true }), false)
  assert.equal(canEditQuestionInBank({ role: 'EDITOR', hasActiveExam: true }), false)
  // Member is always blocked
  assert.equal(canEditQuestionInBank({ role: 'MEMBER', hasActiveExam: false }), false)
})

test('filterBankQuestions filters by keyword matching stem', () => {
  const res = filterBankQuestions(sampleQuestions, { keyword: 'vacuum' })
  assert.equal(res.length, 1)
  assert.equal(res[0].id, 'q1')
})

test('filterBankQuestions filters by keyword matching tags', () => {
  const res = filterBankQuestions(sampleQuestions, { keyword: 'optics' })
  assert.equal(res.length, 1)
  assert.equal(res[0].id, 'q1')
})

test('filterBankQuestions filters by question type', () => {
  const res = filterBankQuestions(sampleQuestions, { type: 'MULTI' })
  assert.equal(res.length, 1)
  assert.equal(res[0].id, 'q2')
})

test('filterBankQuestions filters by difficulty', () => {
  const res = filterBankQuestions(sampleQuestions, { difficulty: 1 })
  assert.equal(res.length, 1)
  assert.equal(res[0].id, 'q3')
})

test('filterBankQuestions filters by tag', () => {
  const res = filterBankQuestions(sampleQuestions, { tag: 'physics' })
  assert.equal(res.length, 3)
  const ids = res.map(q => q.id)
  assert.deepEqual(ids, ['q1', 'q3', 'q4'])
})

test('filterBankQuestions filters by chapterId', () => {
  const res = filterBankQuestions(sampleQuestions, { chapterId: 'chap-1' })
  assert.equal(res.length, 2)
  const ids = res.map(q => q.id)
  assert.deepEqual(ids, ['q1', 'q3'])
})

test('filterBankQuestions combines multi-criteria filters with AND logic', () => {
  const res = filterBankQuestions(sampleQuestions, {
    keyword: 'light',
    type: 'SINGLE',
    difficulty: 2,
    tag: 'physics',
    chapterId: 'chap-1',
  })
  assert.equal(res.length, 1)
  assert.equal(res[0].id, 'q1')

  const noMatch = filterBankQuestions(sampleQuestions, {
    keyword: 'light',
    type: 'MULTI',
  })
  assert.equal(noMatch.length, 0)
})

test('filterBankQuestions returns full array when filters are empty or null', () => {
  const res = filterBankQuestions(sampleQuestions, createEmptyBankFilters())
  assert.equal(res.length, 4)
  const emptyRes = filterBankQuestions(null, {})
  assert.deepEqual(emptyRes, [])
})

test('validateQuestionEdit validates SINGLE choice answers strictly', () => {
  const opts = [{ key: 'A', content: '1' }, { key: 'B', content: '2' }]
  assert.equal(validateQuestionEdit('SINGLE', opts, 'A').valid, true)
  assert.equal(validateQuestionEdit('SINGLE', opts, 'B').valid, true)
  assert.equal(validateQuestionEdit('SINGLE', opts, 'C').valid, false)
  assert.equal(validateQuestionEdit('SINGLE', opts, '').valid, false)
  assert.equal(validateQuestionEdit('SINGLE', opts, null).valid, false)
})

test('validateQuestionEdit validates MULTI choice answers strictly', () => {
  const opts = [{ key: 'A', content: '1' }, { key: 'B', content: '2' }, { key: 'C', content: '3' }]
  assert.equal(validateQuestionEdit('MULTI', opts, 'A,B').valid, true)
  assert.equal(validateQuestionEdit('MULTI', opts, 'A, C').valid, true)
  assert.equal(validateQuestionEdit('MULTI', opts, 'A,D').valid, false)
  assert.equal(validateQuestionEdit('MULTI', opts, '').valid, false)
  assert.equal(validateQuestionEdit('MULTI', opts, '   ').valid, false)
})

test('validateQuestionEdit validates JUDGE answers strictly', () => {
  const opts = [{ key: 'T', content: 'True' }, { key: 'F', content: 'False' }]
  assert.equal(validateQuestionEdit('JUDGE', opts, 'T').valid, true)
  assert.equal(validateQuestionEdit('JUDGE', opts, 'f').valid, true)
  assert.equal(validateQuestionEdit('JUDGE', opts, 'X').valid, false)
  assert.equal(validateQuestionEdit('JUDGE', opts, '').valid, false)
})

test('sanitizeAnswerOnOptionRemove cleans up deleted options in answers', () => {
  // SINGLE: if answer was deleted key, clears it
  assert.equal(sanitizeAnswerOnOptionRemove('SINGLE', 'B', 'B'), '')
  assert.equal(sanitizeAnswerOnOptionRemove('SINGLE', 'A', 'B'), 'A')

  // MULTI: removes deleted key from comma-separated list
  assert.equal(sanitizeAnswerOnOptionRemove('MULTI', 'A,B,C', 'B'), 'A,C')
  assert.equal(sanitizeAnswerOnOptionRemove('MULTI', 'B', 'B'), '')
  assert.equal(sanitizeAnswerOnOptionRemove('MULTI', 'A,C', 'B'), 'A,C')
})
