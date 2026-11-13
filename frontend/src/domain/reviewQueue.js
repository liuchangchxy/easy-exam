// Phase P3 "one queue": the review page used to be four independent lists, so
// the same question could appear under 到期 and 错题 without any row saying so.
// These helpers merge the sources into one deduplicated list keyed by
// bank + question, keeping every applicable reason on the row. They are pure
// so the merge rules can be tested without mounting the view.

export const REVIEW_REASONS = ['due', 'mistakes', 'weak', 'killed']

const REASON_LABEL_KEYS = {
  all: 'ep.review.reason_all',
  due: 'ep.review.tab_due',
  mistakes: 'ep.review.tab_mistakes',
  weak: 'ep.review.weak',
  killed: 'ep.review.reason_killed',
}

function reasonRank(reason) {
  const index = REVIEW_REASONS.indexOf(reason)
  return index === -1 ? REVIEW_REASONS.length : index
}

function rowKey(bankId, questionId) {
  return `${bankId || ''}::${questionId}`
}

// A due row, a mistake row and a weak flag all describe the same question.
// Fold them into one row and remember each source that mentioned it.
function foldRow(map, item, reason) {
  const questionId = item?.question_id
  if (!questionId) return
  const bankId = item.bank_id || ''
  const key = rowKey(bankId, questionId)
  let row = map.get(key)
  if (!row) {
    row = {
      key,
      bank_id: bankId,
      question_id: questionId,
      stem: '',
      type: '',
      reasons: [],
    }
    map.set(key, row)
  }
  if (!row.stem && item.stem) row.stem = item.stem
  if (!row.type && item.type) row.type = item.type
  if (item.due_at && !row.due_at) row.due_at = item.due_at
  if (item.killed_at && !row.killed_at) row.killed_at = item.killed_at
  if (Number.isFinite(item.mistake_count)) {
    row.mistake_count = Math.max(row.mistake_count || 0, item.mistake_count)
  }
  if (!row.reasons.includes(reason)) row.reasons.push(reason)
  if (reason === 'weak') row.weak = true
}

function compareDates(a, b, direction) {
  const left = Date.parse(a)
  const right = Date.parse(b)
  const leftValid = Number.isFinite(left)
  const rightValid = Number.isFinite(right)
  if (!leftValid && !rightValid) return 0
  // Rows without the timestamp sink to the end of the group.
  if (!leftValid) return 1
  if (!rightValid) return -1
  if (left === right) return 0
  return direction === 'desc' ? right - left : left - right
}

// Buckets: due (even when it is also a mistake), mistakes by count, weak,
// killed. The bucket decides the order of the merged queue; the key breaks
// ties so the output is deterministic for equal timestamps and counts.
function bucketOf(row) {
  if (row.reasons.includes('due')) return 0
  if (row.reasons.includes('mistakes')) return 1
  if (row.reasons.includes('weak')) return 2
  return 3
}

function compareRows(a, b) {
  const bucketA = bucketOf(a)
  const bucketB = bucketOf(b)
  if (bucketA !== bucketB) return bucketA - bucketB
  if (bucketA === 0) {
    const byDue = compareDates(a.due_at, b.due_at, 'asc')
    if (byDue) return byDue
  } else if (bucketA === 1) {
    const byCount = (b.mistake_count || 0) - (a.mistake_count || 0)
    if (byCount) return byCount
  } else if (bucketA === 3) {
    const byKilled = compareDates(a.killed_at, b.killed_at, 'desc')
    if (byKilled) return byKilled
  }
  if (a.key === b.key) return 0
  return a.key < b.key ? -1 : 1
}

export function mergeReviewQueue({ due = [], mistakes = [], weak = [], killed = [] } = {}) {
  const map = new Map()
  const sources = [
    [due, 'due'],
    [mistakes, 'mistakes'],
    [weak, 'weak'],
    [killed, 'killed'],
  ]
  for (const [items, reason] of sources) {
    for (const item of Array.isArray(items) ? items : []) foldRow(map, item, reason)
  }
  const rows = [...map.values()]
  for (const row of rows) row.reasons.sort((a, b) => reasonRank(a) - reasonRank(b))
  return rows.sort(compareRows)
}

export function filterReviewRows(rows, reason) {
  const list = Array.isArray(rows) ? rows : []
  if (!reason || reason === 'all') return list.slice()
  return list.filter(row => Array.isArray(row.reasons) && row.reasons.includes(reason))
}

export function reviewReasonLabelKey(reason) {
  return REASON_LABEL_KEYS[reason] || REASON_LABEL_KEYS.all
}
