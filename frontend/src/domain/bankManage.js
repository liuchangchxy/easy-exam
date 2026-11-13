/**
 * Question Bank Content Management domain utilities.
 * Pure business logic for question filtering, search, and role authorization.
 */

export function createEmptyBankFilters() {
  return {
    keyword: '',
    type: '',
    difficulty: '',
    tag: '',
    chapterId: '',
  }
}

export function isFilterActive(filters) {
  if (!filters) return false
  const kw = filters.keyword ? String(filters.keyword).trim() : ''
  const tp = filters.type ? String(filters.type).trim() : ''
  const diff = filters.difficulty !== '' && filters.difficulty !== null && filters.difficulty !== undefined
  const tg = filters.tag ? String(filters.tag).trim() : ''
  const chap = filters.chapterId ? String(filters.chapterId).trim() : ''
  return Boolean(kw || tp || diff || tg || chap)
}

export function canEditBankContent(role) {
  if (!role) return false
  const normalized = String(role).trim().toUpperCase()
  return normalized === 'ADMIN' || normalized === 'EDITOR'
}

export function canEditQuestionInBank({ role, hasActiveExam = false, isQuestionInExam = false } = {}) {
  if (!canEditBankContent(role)) return false
  if (hasActiveExam || isQuestionInExam) return false
  return true
}

/**
 * A question is locked only when an unfinished exam currently includes it.
 * Other questions in the same bank stay editable.
 */
export function isQuestionLocked(question) {
  return Boolean(question && (question.locked_by_active_exam || question.locked))
}

export function canEditQuestion({ role, question, hasActiveExam = false } = {}) {
  if (!canEditBankContent(role)) return false
  if (hasActiveExam || isQuestionLocked(question)) return false
  return true
}

export function createSelection() {
  return new Set()
}

export function toggleSelection(selection, questionId) {
  const next = new Set(selection || [])
  const id = String(questionId || '').trim()
  if (!id) return next
  if (next.has(id)) next.delete(id)
  else next.add(id)
  return next
}

export function toggleVisibleSelection(selection, visibleIds, checked) {
  const next = new Set(selection || [])
  for (const raw of visibleIds || []) {
    const id = String(raw || '').trim()
    if (!id) continue
    if (checked) next.add(id)
    else next.delete(id)
  }
  return next
}

export function isAllVisibleSelected(selection, visibleIds) {
  const ids = (visibleIds || []).map(id => String(id || '').trim()).filter(Boolean)
  if (!ids.length) return false
  return ids.every(id => selection?.has?.(id))
}

export function buildBatchRequest(operation, questionIds, extras = {}) {
  const ids = [...new Set((questionIds || []).map(id => String(id || '').trim()).filter(Boolean))]
  if (!ids.length) return { error: 'no_questions' }

  const op = String(operation || '').trim().toLowerCase()
  const allowed = ['chapter', 'add_tags', 'remove_tags', 'move', 'copy', 'archive', 'restore']
  if (!allowed.includes(op)) return { error: 'invalid_operation' }

  const payload = { question_ids: ids, operation: op }

  if (op === 'chapter') {
    if (extras.chapterId === undefined || extras.chapterId === null) return { error: 'chapter_required' }
    payload.chapter_id = extras.chapterId || null
  }

  if (op === 'add_tags' || op === 'remove_tags') {
    const tags = [...new Set((extras.tags || []).map(tag => String(tag || '').trim()).filter(Boolean))]
    if (!tags.length) return { error: 'tags_required' }
    payload.tags = tags
  }

  if (op === 'move' || op === 'copy') {
    const targetBankId = String(extras.targetBankId || '').trim()
    if (!targetBankId) return { error: 'target_required' }
    payload.target_bank_id = targetBankId
  }

  return { payload }
}

export function normalizeAnswer(type, answer) {
  const t = String(type || '').toUpperCase()
  const raw = String(answer ?? '').trim()
  if (t === 'MULTI') {
    return [...new Set(raw.split(/[,;\s]+/).map(key => key.trim().toUpperCase()).filter(Boolean))].sort().join(',')
  }
  if (t === 'SINGLE' || t === 'JUDGE') return raw.toUpperCase()
  return raw
}

/**
 * Ask before re-grading existing attempts: only when the scoring-relevant
 * content changed and the draft still carries a usable answer.
 */
export function shouldOfferRegrade(original = {}, draft = {}) {
  const newAnswer = String(draft?.answer ?? '').trim()
  if (!newAnswer) return false
  const originalType = String(original?.type || '').toUpperCase()
  const draftType = String(draft?.type || '').toUpperCase()
  if (originalType !== draftType) return true
  return normalizeAnswer(originalType, original?.answer) !== normalizeAnswer(draftType, newAnswer)
}

export function questionCode(id) {
  return String(id || '').replace(/^q/i, '').slice(0, 8).toUpperCase()
}

export function filterBankQuestions(questions, filters) {
  if (!Array.isArray(questions)) return []
  if (!filters || !isFilterActive(filters)) return questions.slice()

  const kw = filters.keyword ? String(filters.keyword).trim().toLowerCase() : ''
  const tp = filters.type ? String(filters.type).trim().toUpperCase() : ''
  const hasDiff = filters.difficulty !== '' && filters.difficulty !== null && filters.difficulty !== undefined
  const targetDiff = hasDiff ? Number(filters.difficulty) : null
  const tg = filters.tag ? String(filters.tag).trim().toLowerCase() : ''
  const chap = filters.chapterId ? String(filters.chapterId).trim() : ''

  return questions.filter(q => {
    if (!q) return false

    // 1. Keyword filter matches id/code, stem or tags
    if (kw) {
      const id = String(q.id || '').toLowerCase()
      const code = questionCode(q.id).toLowerCase()
      const idMatch = id === kw || id.startsWith(kw) || code === kw || code.startsWith(kw)
      const stemMatch = q.stem ? String(q.stem).toLowerCase().includes(kw) : false
      const tagsMatch = Array.isArray(q.tags)
        ? q.tags.some(t => t && String(t).toLowerCase().includes(kw))
        : false
      if (!idMatch && !stemMatch && !tagsMatch) return false
    }

    // 2. Type filter
    if (tp && String(q.type || '').toUpperCase() !== tp) {
      return false
    }

    // 3. Difficulty filter
    if (hasDiff && Number(q.difficulty) !== targetDiff) {
      return false
    }

    // 4. Tag filter
    if (tg) {
      const hasTag = Array.isArray(q.tags)
        ? q.tags.some(t => t && String(t).toLowerCase() === tg)
        : false
      if (!hasTag) return false
    }

    // 5. Chapter filter
    if (chap && String(q.chapter_id || '') !== chap) {
      return false
    }

    return true
  })
}

export function splitAnswerKeys(rawAnswer) {
  const clean = String(rawAnswer || '').trim()
  if (!clean) return []
  const tokens = clean.split(/[,;\s]+/).map(k => k.trim()).filter(Boolean)
  const keys = []
  for (const token of tokens) {
    // Mirror backend normalize_answer_keys: "AB" is the same answer as "A,B".
    if (token.length > 1 && /^[A-Z]+$/.test(token)) {
      keys.push(...token.split(''))
    } else {
      keys.push(token)
    }
  }
  return [...new Set(keys)]
}

export function sanitizeAnswerOnOptionRemove(type, currentAnswer, removedKey) {
  if (!currentAnswer || !removedKey) return currentAnswer || ''
  const t = String(type || '').toUpperCase()
  if (t === 'SINGLE') {
    return currentAnswer.trim() === removedKey.trim() ? '' : currentAnswer
  }
  if (t === 'MULTI') {
    return splitAnswerKeys(currentAnswer).filter(k => k !== removedKey.trim()).join(',')
  }
  return currentAnswer
}

export function validateQuestionEdit(type, options, answer) {
  const t = String(type || '').toUpperCase()
  const trimmedAns = answer ? String(answer).trim() : ''

  if (t === 'SINGLE') {
    const rawKeys = (Array.isArray(options) ? options.map(o => (o.key ? String(o.key).trim() : '')) : []).filter(Boolean)
    if (rawKeys.length < 2 || new Set(rawKeys).size !== rawKeys.length) {
      return { valid: false, error: 'invalid_options' }
    }
    if (!trimmedAns || !rawKeys.includes(trimmedAns)) {
      return { valid: false, error: 'invalid_answer' }
    }
    return { valid: true }
  }

  if (t === 'MULTI') {
    const rawKeys = (Array.isArray(options) ? options.map(o => (o.key ? String(o.key).trim() : '')) : []).filter(Boolean)
    if (rawKeys.length < 2 || new Set(rawKeys).size !== rawKeys.length) {
      return { valid: false, error: 'invalid_options' }
    }
    const validKeys = new Set(rawKeys)
    const parts = splitAnswerKeys(trimmedAns)
    if (parts.length < 2 || !parts.every(k => validKeys.has(k))) {
      return { valid: false, error: 'invalid_answer' }
    }
    return { valid: true }
  }

  if (t === 'JUDGE') {
    const upper = trimmedAns.toUpperCase()
    if (upper !== 'T' && upper !== 'F') {
      return { valid: false, error: 'invalid_answer' }
    }
    return { valid: true }
  }

  if (t === 'FILL') {
    return trimmedAns ? { valid: true } : { valid: false, error: 'invalid_answer' }
  }

  return { valid: true }
}

export function adaptAnswerOnTypeChange(newType, currentAnswer, options = []) {
  if (!currentAnswer || !String(currentAnswer).trim()) return ''
  const t = String(newType || '').toUpperCase()
  const trimmedAns = String(currentAnswer).trim()

  if (t === 'JUDGE') {
    const upper = trimmedAns.toUpperCase()
    if (upper === 'T' || upper === 'F') {
      return upper
    }
    return ''
  }

  if (t === 'SINGLE') {
    // T/F from JUDGE does not adapt to SINGLE with A/B/C/D
    const validKeys = Array.isArray(options) ? options.map(o => o.key?.trim()).filter(Boolean) : []
    if (validKeys.includes(trimmedAns) && !['T', 'F'].includes(trimmedAns.toUpperCase())) {
      return trimmedAns
    }
    return ''
  }

  if (t === 'MULTI') {
    const validKeys = new Set(Array.isArray(options) ? options.map(o => o.key?.trim()).filter(Boolean) : [])
    const parts = splitAnswerKeys(trimmedAns)
    const validParts = parts.filter(k => validKeys.has(k) && !['T', 'F'].includes(k.toUpperCase()))
    if (validParts.length > 0) {
      return validParts.join(',')
    }
    return ''
  }

  if (t === 'ESSAY') {
    return ''
  }

  return trimmedAns
}

export function adaptOptionsOnTypeChange(newType, currentOptions = [], tHelper = null) {
  const t = String(newType || '').toUpperCase()
  const trueLabel = tHelper ? tHelper('bank_manage.judge_true') : '正确'
  const falseLabel = tHelper ? tHelper('bank_manage.judge_false') : '错误'

  if (t === 'JUDGE') {
    return [
      { key: 'T', content: trueLabel },
      { key: 'F', content: falseLabel },
    ]
  }

  if (['SINGLE', 'MULTI'].includes(t)) {
    const isFromJudge = !currentOptions.length ||
      currentOptions.length < 2 ||
      currentOptions.some(o => ['T', 'F'].includes(String(o?.key || '').trim().toUpperCase()))
    if (isFromJudge) {
      return [
        { key: 'A', content: '' },
        { key: 'B', content: '' },
        { key: 'C', content: '' },
        { key: 'D', content: '' },
      ]
    }
    return currentOptions.map(opt => ({
      key: opt.key || '',
      content: opt.content !== undefined ? opt.content : (opt.text || ''),
    }))
  }

  if (t === 'ESSAY') {
    return []
  }

  return currentOptions
}

/**
 * Bank-list batch actions. Mirrors the backend contract: archive/restore/delete
 * are id-only, set_category needs a non-empty category name.
 */
export function buildBankBatchRequest(bankIds, operation, extras = {}) {
  const ids = [...new Set((bankIds || []).map(id => String(id || '').trim()).filter(Boolean))]
  if (!ids.length) return { error: 'no_banks' }

  const op = String(operation || '').trim().toLowerCase()
  if (!['archive', 'restore', 'delete', 'set_category'].includes(op)) return { error: 'invalid_operation' }

  const payload = { bank_ids: ids, operation: op }
  if (op === 'set_category') {
    const category = String(extras.category || '').trim()
    if (!category) return { error: 'category_required' }
    payload.category = category
  }
  return { payload }
}

export function filterBankList(banks, { query = '', category = '' } = {}) {
  let list = Array.isArray(banks) ? banks.slice() : []
  const q = String(query || '').trim().toLowerCase()
  if (q) {
    list = list.filter(b => `${b.name || ''} ${b.description || ''} ${b.category || ''}`.toLowerCase().includes(q))
  }
  if (category) list = list.filter(b => (b.category || '') === category)
  return list
}

export function sortBankList(banks, sortKey = 'recent') {
  const list = Array.isArray(banks) ? banks.slice() : []
  if (sortKey === 'name') {
    return list.sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
  }
  if (sortKey === 'count') {
    return list.sort((a, b) => Number(b.question_count || 0) - Number(a.question_count || 0))
  }
  // "Recent" means recently touched: an edited bank should resurface even when
  // it was created long ago.
  return list.sort((a, b) => {
    const left = Date.parse(a.updated_at || a.created_at || '') || 0
    const right = Date.parse(b.updated_at || b.created_at || '') || 0
    return right - left
  })
}

/**
 * Flatten chapters into a depth-first tree so the manage page can render
 * indentation without a recursive component. Orphans are promoted to roots.
 */
export function flattenChapterTree(chapters) {
  const list = Array.isArray(chapters) ? chapters.slice() : []
  const byParent = new Map()
  const ids = new Set(list.map(c => c.id))
  for (const chapter of list) {
    const parent = chapter.parent_id && ids.has(chapter.parent_id) ? chapter.parent_id : null
    if (!byParent.has(parent)) byParent.set(parent, [])
    byParent.get(parent).push(chapter)
  }
  for (const children of byParent.values()) {
    children.sort((a, b) => (Number(a.sort_order || 0) - Number(b.sort_order || 0))
      || String(a.name || '').localeCompare(String(b.name || '')))
  }
  const result = []
  const seen = new Set()
  function walk(parentId, depth) {
    for (const chapter of byParent.get(parentId) || []) {
      if (seen.has(chapter.id)) continue
      seen.add(chapter.id)
      result.push({ ...chapter, depth })
      walk(chapter.id, depth + 1)
    }
  }
  walk(null, 0)
  for (const chapter of list) {
    if (!seen.has(chapter.id)) result.push({ ...chapter, depth: 0 })
  }
  return result
}

export function buildChapterReorderPayload(chapters, chapterId, direction) {
  const ordered = flattenChapterTree(chapters)
  const index = ordered.findIndex(c => c.id === chapterId)
  if (index === -1) return { error: 'chapter_not_found' }
  const target = ordered[index]
  const siblings = ordered.filter(c => (c.parent_id || null) === (target.parent_id || null))
  const siblingIndex = siblings.findIndex(c => c.id === chapterId)
  const swapWith = direction === 'up' ? siblingIndex - 1 : siblingIndex + 1
  if (swapWith < 0 || swapWith >= siblings.length) return { error: 'no_sibling' }

  const nextSiblings = siblings.slice()
  const [moved] = nextSiblings.splice(siblingIndex, 1)
  nextSiblings.splice(swapWith, 0, moved)
  const orderById = new Map(nextSiblings.map((chapter, idx) => [chapter.id, idx]))

  const items = ordered.map(c => ({
    id: c.id,
    parent_id: c.parent_id || null,
    sort_order: orderById.has(c.id) ? orderById.get(c.id) : Number(c.sort_order || 0),
  }))
  return { items }
}

export function paginateList(list, page = 1, pageSize = 20) {
  const items = Array.isArray(list) ? list : []
  const size = Math.max(1, Number(pageSize) || 20)
  const pages = Math.max(1, Math.ceil(items.length / size))
  const current = Math.min(Math.max(1, Number(page) || 1), pages)
  const start = (current - 1) * size
  return {
    items: items.slice(start, start + size),
    page: current,
    pages,
    total: items.length,
    pageSize: size,
  }
}

export function sortQuestionList(questions, sortKey = 'default') {
  const list = Array.isArray(questions) ? questions.slice() : []
  if (sortKey === 'id') {
    return list.sort((a, b) => String(a.id || '').localeCompare(String(b.id || '')))
  }
  if (sortKey === 'difficulty') {
    return list.sort((a, b) => Number(b.difficulty || 0) - Number(a.difficulty || 0))
  }
  if (sortKey === 'updated') {
    return list.sort((a, b) => (Date.parse(b.updated_at || '') || 0) - (Date.parse(a.updated_at || '') || 0))
  }
  return list
}
