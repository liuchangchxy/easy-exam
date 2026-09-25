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

