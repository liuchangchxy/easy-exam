import { describe, expect, it } from 'vitest'
import {
  filterReviewRows,
  mergeReviewQueue,
  reviewReasonLabelKey,
} from '../../src/domain/reviewQueue.js'

const question = (questionId, bankId = 'b1', extra = {}) => ({
  question_id: questionId,
  bank_id: bankId,
  stem: `Stem ${questionId}`,
  type: 'SINGLE',
  ...extra,
})

describe('mergeReviewQueue', () => {
  it('folds a question that is due, a mistake and weak into one row with every reason', () => {
    const rows = mergeReviewQueue({
      due: [question('q1', 'b1', { due_at: '2026-11-13T08:00:00Z', mistake_count: 2 })],
      mistakes: [question('q1', 'b1', { mistake_count: 4 })],
      weak: [question('q1', 'b1')],
      killed: [],
    })

    expect(rows).toHaveLength(1)
    expect(rows[0].key).toBe('b1::q1')
    expect(rows[0].bank_id).toBe('b1')
    expect(rows[0].question_id).toBe('q1')
    expect(rows[0].stem).toBe('Stem q1')
    expect(rows[0].type).toBe('SINGLE')
    expect(rows[0].reasons).toEqual(['due', 'mistakes', 'weak'])
    expect(rows[0].mistake_count).toBe(4)
    expect(rows[0].due_at).toBe('2026-11-13T08:00:00Z')
    expect(rows[0].weak).toBe(true)
  })

  it('keeps the same question id in different banks as separate rows', () => {
    const rows = mergeReviewQueue({
      due: [question('q1', 'b1'), question('q1', 'b2')],
    })

    expect(rows.map(row => row.key)).toEqual(['b1::q1', 'b2::q1'])
  })

  it('orders due first, then mistakes by count, then weak, then killed', () => {
    const rows = mergeReviewQueue({
      due: [
        question('q-late', 'b1', { due_at: '2026-11-13T10:00:00Z' }),
        question('q-early', 'b1', { due_at: '2026-11-13T08:00:00Z' }),
      ],
      mistakes: [
        question('m-low', 'b1', { mistake_count: 2 }),
        question('m-high', 'b1', { mistake_count: 5 }),
      ],
      weak: [question('w1', 'b1')],
      killed: [
        question('k-old', 'b1', { killed_at: '2026-11-10T08:00:00Z' }),
        question('k-new', 'b1', { killed_at: '2026-11-12T08:00:00Z' }),
      ],
    })

    expect(rows.map(row => row.question_id)).toEqual([
      'q-early',
      'q-late',
      'm-high',
      'm-low',
      'w1',
      'k-new',
      'k-old',
    ])
  })

  it('stays deterministic when due dates and mistake counts tie', () => {
    const build = () => ({
      due: [
        question('q-b', 'b2', { due_at: '2026-11-13T08:00:00Z' }),
        question('q-a', 'b1', { due_at: '2026-11-13T08:00:00Z' }),
      ],
      mistakes: [
        question('m-b', 'b1', { mistake_count: 3 }),
        question('m-a', 'b1', { mistake_count: 3 }),
      ],
    })

    const first = mergeReviewQueue(build()).map(row => row.key)
    const second = mergeReviewQueue(build()).map(row => row.key)
    expect(first).toEqual(['b1::q-a', 'b2::q-b', 'b1::m-a', 'b1::m-b'])
    expect(second).toEqual(first)
  })

  it('tolerates missing sources and drops entries without a question id', () => {
    expect(mergeReviewQueue()).toEqual([])
    expect(mergeReviewQueue({})).toEqual([])
    expect(mergeReviewQueue({ due: [{ bank_id: 'b1', stem: 'no id' }] })).toEqual([])
  })
})

describe('filterReviewRows', () => {
  const rows = mergeReviewQueue({
    due: [question('q1', 'b1', { due_at: '2026-11-13T08:00:00Z' })],
    mistakes: [question('q1', 'b1', { mistake_count: 3 }), question('q2', 'b1', { mistake_count: 1 })],
    weak: [question('q1', 'b1')],
    killed: [question('q3', 'b1', { killed_at: '2026-11-12T08:00:00Z' })],
  })

  it('returns every row for all or an empty reason', () => {
    expect(filterReviewRows(rows, 'all')).toHaveLength(3)
    expect(filterReviewRows(rows, '')).toHaveLength(3)
    expect(filterReviewRows(rows)).toHaveLength(3)
  })

  it('keeps rows that qualify for the requested reason, even with several reasons', () => {
    expect(filterReviewRows(rows, 'due').map(row => row.question_id)).toEqual(['q1'])
    expect(filterReviewRows(rows, 'mistakes').map(row => row.question_id)).toEqual(['q1', 'q2'])
    expect(filterReviewRows(rows, 'weak').map(row => row.question_id)).toEqual(['q1'])
    expect(filterReviewRows(rows, 'killed').map(row => row.question_id)).toEqual(['q3'])
  })

  it('returns nothing for an unknown reason', () => {
    expect(filterReviewRows(rows, 'bogus')).toEqual([])
  })
})

describe('reviewReasonLabelKey', () => {
  it('maps every reason to an ep.review locale key', () => {
    expect(reviewReasonLabelKey('due')).toBe('ep.review.tab_due')
    expect(reviewReasonLabelKey('mistakes')).toBe('ep.review.tab_mistakes')
    expect(reviewReasonLabelKey('weak')).toBe('ep.review.weak')
    expect(reviewReasonLabelKey('killed')).toBe('ep.review.reason_killed')
    expect(reviewReasonLabelKey('all')).toBe('ep.review.reason_all')
  })
})
