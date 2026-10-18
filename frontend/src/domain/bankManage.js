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

    // 1. Keyword filter matches stem or tags
    if (kw) {
      const stemMatch = q.stem ? String(q.stem).toLowerCase().includes(kw) : false
      const tagsMatch = Array.isArray(q.tags)
        ? q.tags.some(t => t && String(t).toLowerCase().includes(kw))
        : false
      if (!stemMatch && !tagsMatch) return false
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
