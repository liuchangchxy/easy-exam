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
  adaptAnswerOnTypeChange,
  isQuestionLocked,
  canEditQuestion,
  createSelection,
  toggleSelection,
  toggleVisibleSelection,
  isAllVisibleSelected,
  buildBatchRequest,
  normalizeAnswer,
  shouldOfferRegrade,
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

test('per-question lock only blocks the questions included in an active exam', () => {
  const lockedQuestion = { id: 'q1', locked_by_active_exam: true }
  const freeQuestion = { id: 'q2', locked_by_active_exam: false }
  assert.equal(isQuestionLocked(lockedQuestion), true)
  assert.equal(isQuestionLocked(freeQuestion), false)
  assert.equal(canEditQuestion({ role: 'ADMIN', question: lockedQuestion }), false)
  assert.equal(canEditQuestion({ role: 'ADMIN', question: freeQuestion }), true)
  assert.equal(canEditQuestion({ role: 'MEMBER', question: freeQuestion }), false)
})

test('selection helpers toggle single rows and the visible page without duplicates', () => {
  const selected = createSelection()
  const one = toggleSelection(selected, 'q1')
  assert.deepEqual([...one], ['q1'])
  assert.deepEqual([...toggleSelection(one, 'q1')], [])
  // Blank ids never enter the selection
  assert.deepEqual([...toggleSelection(one, '  ')], ['q1'])

  const visible = ['q1', 'q2', 'q3']
  const all = toggleVisibleSelection(one, visible, true)
  assert.deepEqual([...all], ['q1', 'q2', 'q3'])
  assert.equal(isAllVisibleSelected(all, visible), true)
  assert.equal(isAllVisibleSelected(all, ['q1', 'q4']), false)

  const cleared = toggleVisibleSelection(all, ['q1', 'q2'], false)
  assert.deepEqual([...cleared], ['q3'])
  assert.equal(isAllVisibleSelected(cleared, ['q1', 'q2']), false)
})

test('buildBatchRequest validates each batch operation and deduplicates ids', () => {
  assert.deepEqual(buildBatchRequest('archive', []), { error: 'no_questions' })
  assert.deepEqual(buildBatchRequest('explode', ['q1']), { error: 'invalid_operation' })

  const archive = buildBatchRequest('archive', ['q1', 'q1', ' q2 '])
  assert.deepEqual(archive.payload, { question_ids: ['q1', 'q2'], operation: 'archive' })

  assert.deepEqual(buildBatchRequest('chapter', ['q1']), { error: 'chapter_required' })
  assert.deepEqual(buildBatchRequest('chapter', ['q1'], { chapterId: '' }).payload, {
    question_ids: ['q1'],
    operation: 'chapter',
    chapter_id: null,
  })

  assert.deepEqual(buildBatchRequest('add_tags', ['q1']), { error: 'tags_required' })
  assert.deepEqual(buildBatchRequest('add_tags', ['q1'], { tags: [' math ', ''] }).payload, {
    question_ids: ['q1'],
    operation: 'add_tags',
    tags: ['math'],
  })

  assert.deepEqual(buildBatchRequest('copy', ['q1']), { error: 'target_required' })
  assert.deepEqual(buildBatchRequest('copy', ['q1'], { targetBankId: 'b2' }).payload, {
    question_ids: ['q1'],
    operation: 'copy',
    target_bank_id: 'b2',
  })
})

test('normalizeAnswer ignores separator and case noise for choice questions', () => {
  assert.equal(normalizeAnswer('MULTI', 'B, A'), 'A,B')
  assert.equal(normalizeAnswer('MULTI', 'a b'), 'A,B')
  assert.equal(normalizeAnswer('SINGLE', ' a '), 'A')
  assert.equal(normalizeAnswer('ESSAY', ' Depends on context '), 'Depends on context')
})

test('shouldOfferRegrade only asks when the scoring answer actually changes', () => {
  const original = { type: 'SINGLE', answer: 'A' }
  assert.equal(shouldOfferRegrade(original, { type: 'SINGLE', answer: 'A' }), false)
  assert.equal(shouldOfferRegrade(original, { type: 'SINGLE', answer: ' a ' }), false)
  assert.equal(shouldOfferRegrade(original, { type: 'SINGLE', answer: 'B' }), true)
  assert.equal(shouldOfferRegrade(original, { type: 'MULTI', answer: 'A,B' }), true)
  // Do not offer destructive re-grading when the draft answer is empty.
  assert.equal(shouldOfferRegrade(original, { type: 'SINGLE', answer: '' }), false)
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

test('validateQuestionEdit accepts contiguous MULTI keys the same way the backend does', () => {
  const opts = [{ key: 'A', content: '1' }, { key: 'B', content: '2' }, { key: 'C', content: '3' }]
  // Clicking option keys in the create form joins them without separators ("AB");
  // the backend expands that token, so the client-side gate must not reject it.
  assert.equal(validateQuestionEdit('MULTI', opts, 'AB').valid, true)
  assert.equal(validateQuestionEdit('MULTI', opts, 'ABC').valid, true)
  assert.equal(validateQuestionEdit('MULTI', opts, 'AB,D').valid, false)
  assert.equal(validateQuestionEdit('MULTI', opts, 'A').valid, false)
  assert.equal(sanitizeAnswerOnOptionRemove('MULTI', 'AB', 'B'), 'A')
  assert.equal(adaptAnswerOnTypeChange('MULTI', 'AB', opts), 'A,B')
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

test('adaptAnswerOnTypeChange resets incompatible answers to empty string and never auto-picks default option', () => {
  const choiceOpts = [{ key: 'A', content: '1' }, { key: 'B', content: '2' }, { key: 'C', content: '3' }]
  const judgeOpts = [{ key: 'T', content: 'True' }, { key: 'F', content: 'False' }]

  // Switching to JUDGE:
  // Valid judge answer is preserved
  assert.equal(adaptAnswerOnTypeChange('JUDGE', 'T', judgeOpts), 'T')
  assert.equal(adaptAnswerOnTypeChange('JUDGE', 'f', judgeOpts), 'F')
  // Incompatible answer (e.g. from SINGLE/MULTI) is cleared, NOT defaulted to 'T'
  assert.equal(adaptAnswerOnTypeChange('JUDGE', 'A', judgeOpts), '')
  assert.equal(adaptAnswerOnTypeChange('JUDGE', 'B', judgeOpts), '')
  assert.equal(adaptAnswerOnTypeChange('JUDGE', 'A,B', judgeOpts), '')

  // Switching to SINGLE:
  // Valid option key is preserved
  assert.equal(adaptAnswerOnTypeChange('SINGLE', 'B', choiceOpts), 'B')
  // Incompatible answer (e.g. from JUDGE 'T' or MULTI 'A,B') is cleared, NOT defaulted to 'A'
  assert.equal(adaptAnswerOnTypeChange('SINGLE', 'T', choiceOpts), '')
  assert.equal(adaptAnswerOnTypeChange('SINGLE', 'F', choiceOpts), '')
  assert.equal(adaptAnswerOnTypeChange('SINGLE', 'X', choiceOpts), '')
  assert.equal(adaptAnswerOnTypeChange('SINGLE', 'A,B', choiceOpts), '')

  // Switching to MULTI:
  // Overlapping option keys are preserved
  assert.equal(adaptAnswerOnTypeChange('MULTI', 'A,B', choiceOpts), 'A,B')
  assert.equal(adaptAnswerOnTypeChange('MULTI', 'B', choiceOpts), 'B')
  // Incompatible answer (e.g. from JUDGE 'T') is cleared, NOT defaulted to 'A'
  assert.equal(adaptAnswerOnTypeChange('MULTI', 'T', choiceOpts), '')
  assert.equal(adaptAnswerOnTypeChange('MULTI', 'Z', choiceOpts), '')

  // Switching to ESSAY:
  assert.equal(adaptAnswerOnTypeChange('ESSAY', 'A', choiceOpts), '')
  assert.equal(adaptAnswerOnTypeChange('ESSAY', '', choiceOpts), '')
})

test('question keyword search matches id and short code', async () => {
  const { questionCode } = await import('../src/domain/bankManage.js')
  const filters = { ...createEmptyBankFilters(), keyword: questionCode('q-1234abcd') }
  const filtered = filterBankQuestions(sampleQuestions, filters)
  assert.equal(filtered.length, 0, 'a code from another question must not match')

  const byCode = filterBankQuestions(sampleQuestions, { ...createEmptyBankFilters(), keyword: 'q1' })
  assert.deepEqual(byCode.map(q => q.id), ['q1'])
  const byId = filterBankQuestions(sampleQuestions, { ...createEmptyBankFilters(), keyword: 'Q2' })
  assert.deepEqual(byId.map(q => q.id), ['q2'])
})

test('FILL questions require an answer and ignore options', () => {
  assert.deepEqual(validateQuestionEdit('FILL', [], '  '), { valid: false, error: 'invalid_answer' })
  assert.deepEqual(validateQuestionEdit('FILL', [], '北京'), { valid: true })
  assert.deepEqual(validateQuestionEdit('FILL', [{ key: 'A', content: 'x' }], '北京'), { valid: true })
})

test('bank batch requests validate ids and category payloads', async () => {
  const { buildBankBatchRequest } = await import('../src/domain/bankManage.js')
  assert.deepEqual(buildBankBatchRequest([], 'archive'), { error: 'no_banks' })
  assert.deepEqual(buildBankBatchRequest(['b1'], 'nope'), { error: 'invalid_operation' })
  assert.deepEqual(buildBankBatchRequest(['b1'], 'set_category', {}), { error: 'category_required' })
  assert.deepEqual(buildBankBatchRequest(['b1', 'b1', ' '], 'archive'), {
    payload: { bank_ids: ['b1'], operation: 'archive' },
  })
  assert.deepEqual(buildBankBatchRequest(['b1'], 'set_category', { category: ' Alpha ' }), {
    payload: { bank_ids: ['b1'], operation: 'set_category', category: 'Alpha' },
  })
})

test('bank list filtering and sorting are stable', async () => {
  const { filterBankList, sortBankList } = await import('../src/domain/bankManage.js')
  const banks = [
    { id: 'b1', name: 'Beta', category: 'Two', question_count: 3, created_at: '2026-01-01' },
    { id: 'b2', name: 'Alpha', category: 'One', question_count: 9, created_at: '2026-02-01' },
  ]
  assert.deepEqual(sortBankList(banks, 'name').map(b => b.id), ['b2', 'b1'])
  assert.deepEqual(sortBankList(banks, 'count').map(b => b.id), ['b2', 'b1'])
  assert.deepEqual(sortBankList(banks, 'recent').map(b => b.id), ['b2', 'b1'])
  assert.deepEqual(filterBankList(banks, { query: 'alp' }).map(b => b.id), ['b2'])
  assert.deepEqual(filterBankList(banks, { category: 'Two' }).map(b => b.id), ['b1'])
})

test('recent bank sorting prefers updated_at over created_at', async () => {
  const { sortBankList } = await import('../src/domain/bankManage.js')
  const banks = [
    // Created first but edited most recently.
    { id: 'old-created', name: 'A', created_at: '2026-01-01', updated_at: '2026-05-01' },
    { id: 'new-created', name: 'B', created_at: '2026-03-01', updated_at: '2026-03-02' },
    // No updated_at falls back to created_at.
    { id: 'no-updated', name: 'C', created_at: '2026-02-01' },
  ]
  assert.deepEqual(sortBankList(banks, 'recent').map(b => b.id), ['old-created', 'new-created', 'no-updated'])
})


test('chapter tree flattens depth-first and reorder moves siblings only', async () => {
  const { flattenChapterTree, buildChapterReorderPayload } = await import('../src/domain/bankManage.js')
  const chapters = [
    { id: 'c1', name: 'Root A', parent_id: null, sort_order: 0 },
    { id: 'c2', name: 'Root B', parent_id: null, sort_order: 1 },
    { id: 'c3', name: 'Child A1', parent_id: 'c1', sort_order: 0 },
  ]
  const tree = flattenChapterTree(chapters)
  assert.deepEqual(tree.map(c => [c.id, c.depth]), [['c1', 0], ['c3', 1], ['c2', 0]])

  const first = buildChapterReorderPayload(chapters, 'c2', 'up')
  assert.deepEqual(first.items, [
    { id: 'c1', parent_id: null, sort_order: 1 },
    { id: 'c3', parent_id: 'c1', sort_order: 0 },
    { id: 'c2', parent_id: null, sort_order: 0 },
  ])
  assert.deepEqual(buildChapterReorderPayload(chapters, 'c1', 'up'), { error: 'no_sibling' })
  assert.deepEqual(buildChapterReorderPayload(chapters, 'missing', 'up'), { error: 'chapter_not_found' })
})

test('pagination clamps pages and slices deterministically', async () => {
  const { paginateList } = await import('../src/domain/bankManage.js')
  const rows = Array.from({ length: 45 }, (_, i) => i + 1)
  const first = paginateList(rows, 1, 20)
  assert.equal(first.pages, 3)
  assert.equal(first.items.length, 20)
  assert.equal(first.items[0], 1)
  const last = paginateList(rows, 9, 20)
  assert.equal(last.page, 3)
  assert.deepEqual(last.items, [41, 42, 43, 44, 45])
  assert.equal(paginateList([], 1, 20).pages, 1)
})
