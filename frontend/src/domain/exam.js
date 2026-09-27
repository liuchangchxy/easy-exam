export function normalizeExamAnswer(type, value) {
  if (type === 'MULTI') {
    const selected = Array.isArray(value) ? value : typeof value === 'string' ? [...value] : []
    const uniqueSorted = Array.from(new Set(selected.map(String).map(s => s.trim().toUpperCase()))).filter(Boolean).sort()
    return uniqueSorted.join('')
  }
  if (type === 'FILL' || type === 'SHORT_ANSWER' || type === 'ESSAY' || type === 'SUBJECTIVE') {
    return typeof value === 'string' ? value.trim() : ''
  }
  return value ?? ''
}

export function examAnswerState(questionId, answers, flags) {
  const value = answers?.[questionId]
  const answer = value && typeof value === 'object' && !Array.isArray(value)
    ? value.user_answer ?? value.answer
    : value
  const answered = Array.isArray(answer) ? answer.length > 0 : String(answer ?? '').trim().length > 0
  return { answered, flagged: (flags || []).includes(questionId) }
}

export function formatRemainingTime(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  const pad = value => String(value).padStart(2, '0')
  return hours > 0 ? `${pad(hours)}:${pad(minutes)}:${pad(remainder)}` : `${pad(minutes)}:${pad(remainder)}`
}

export function formatQuestionTypeName(type) {
  const map = {
    SINGLE: '单选题',
    MULTI: '多选题',
    JUDGE: '判断题',
    FILL: '填空题',
    SHORT_ANSWER: '主观题',
    ESSAY: '主观题',
    SUBJECTIVE: '主观题',
  }
  return map[String(type || '').toUpperCase()] || String(type || '')
}

export function calculateAccuracy(correct, attempted) {
  const att = Number(attempted) || 0
  const corr = Number(correct) || 0
  if (att <= 0) return '0.0%'
  return `${(Math.round((corr / att) * 1000) / 10).toFixed(1)}%`
}

export function findFirstUnansweredIndex(questions, answers) {
  if (!Array.isArray(questions)) return -1
  return questions.findIndex(q => {
    const state = examAnswerState(q.id, answers, [])
    return !state.answered
  })
}

export function findNextUnansweredIndex(questions, answers, currentIndex = 0) {
  if (!Array.isArray(questions) || !questions.length) return -1
  const len = questions.length
  // Search from currentIndex + 1 to end
  for (let i = currentIndex + 1; i < len; i++) {
    const state = examAnswerState(questions[i]?.id, answers, [])
    if (!state.answered) return i
  }
  // Wrap around from 0 to currentIndex
  for (let i = 0; i <= currentIndex; i++) {
    const state = examAnswerState(questions[i]?.id, answers, [])
    if (!state.answered) return i
  }
  return -1
}

export function formatVerdictTitle(questionType, correctness, isObjective) {
  const type = String(questionType || 'SINGLE').toUpperCase()
  if (!isObjective || type === 'ESSAY' || type === 'SHORT_ANSWER' || type === 'SUBJECTIVE') {
    return '作答已保存（主观题）'
  }
  if (correctness === 'CORRECT') {
    return type === 'MULTI' ? '回答完全正确！' : '回答正确！'
  }
  if (correctness === 'PARTIAL' && type === 'MULTI') {
    return '部分得分（漏选）'
  }
  return '回答错误'
}

export function isSwipeGestureValid(startX, startY, endX, endY, minDistance = 50) {
  // Prevent edge gesture collision with iOS / browser back navigation (first 25px)
  if (startX <= 25) return null
  const deltaX = endX - startX
  const deltaY = endY - startY
  const absX = Math.abs(deltaX)
  const absY = Math.abs(deltaY)

  if (absX < minDistance) return null
  // Must be primarily horizontal (|deltaX| > |deltaY| * 1.5)
  if (absX <= absY * 1.5) return null

  return deltaX < 0 ? 'next' : 'prev'
}

