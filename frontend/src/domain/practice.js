/**
 * Practice domain helper functions for session state hydration,
 * option normalization, and navigation lifecycle resets.
 */

/**
 * Hydrates practice session state from backend session payload.
 * Safely restores the current question index (clamped to questions boundary)
 * and answers dictionary.
 *
 * @param {Object|null} session - Backend session object
 * @param {number} questionsLength - Total number of questions in session
 * @returns {{ currentIndex: number, sessionAnswers: Object }}
 */
export function hydrateSessionPractice(session, questionsLength = 0) {
  const maxIdx = Math.max(0, questionsLength - 1)
  let currentIndex = 0
  if (session && session.current_index !== undefined && session.current_index !== null) {
    currentIndex = Math.min(Math.max(0, Number(session.current_index) || 0), maxIdx)
  }

  const sessionAnswers = {}
  if (session && session.answers && typeof session.answers === 'object') {
    Object.assign(sessionAnswers, session.answers)
  }

  return {
    currentIndex,
    sessionAnswers
  }
}

/**
 * Normalizes question options to ensure standard { key, content } contract.
 * Resilient to legacy or foreign data schemas where text was named 'text'.
 *
 * @param {Array<Object>} options - Raw options array
 * @returns {Array<{ key: string, content: string }>}
 */
export function normalizeQuestionOptions(options) {
  if (!Array.isArray(options)) return []
  return options.map((opt, index) => {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    const key = opt.key || letters[index] || `Option${index + 1}`
    const content = opt.content !== undefined && opt.content !== null
      ? String(opt.content)
      : (opt.text !== undefined && opt.text !== null ? String(opt.text) : '')
    return { key, content }
  })
}

/**
 * Determines whether question editing / temporary form state must be reset
 * based on question navigation transitions.
 *
 * @param {Object|null} current - Current question object
 * @param {Object|null} previous - Previous question object
 * @returns {boolean} True if question pointer has changed and state must be reset
 */
export function shouldResetQuestionForm(current, previous) {
  if (!current) return true
  if (!previous) return true
  return current.id !== previous.id
}
