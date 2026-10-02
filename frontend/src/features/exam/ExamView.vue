<template>
  <main class="exam-page" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
    <header class="exam-header" :class="{ 'report-header': Boolean(report) }">
      <button type="button" class="btn-back" @click="handleBack">{{ t('ui.k0060') }}</button>
      <div class="exam-header-center" @click="!report && (showMobileSheet = true)">
        <h1>{{ report ? t('ui.k0649') : t('ui.k0650') }}</h1>
        <p v-if="!report">{{ session ? `${t('ui.k0651')} ${answeredCount} / ${questions.length}` : t('ui.k0652') }}</p>
      </div>
      <div v-if="!report" class="exam-clock" data-testid="exam-timer" role="timer" aria-live="off">
        {{ session?.time_limit ? formatRemainingTime(remainingSeconds) : t('ui.k0653') }}
      </div>
      <ThemeToggle compact />
      <LocaleToggle compact />
      <button v-if="!report" type="button" class="primary" :disabled="loading || isSubmitting || Boolean(report)" @click="showSubmitConfirm = true">{{ t('exam.submit_exam') }}</button>
    </header>


    <p v-if="error" class="exam-error" role="alert">{{ error }}</p>
    <p v-if="loading" class="exam-loading">{{ t('ui.k0061') }}</p>

    <section v-else-if="report" class="exam-report" aria-labelledby="exam-report-title">
      <h2 id="exam-report-title">{{ t('ui.k0062') }}</h2>
      <div class="report-summary">
        <article><small>{{ t('ui.k0063') }}</small><strong>{{ report.score }}</strong></article>
        <article><small>{{ t('ui.k0064') }}</small><strong>{{ report.accuracy }}%</strong></article>
        <article><small>{{ t('ui.k0065') }}</small><strong>{{ report.answered_count }} / {{ report.total_questions }}</strong></article>
        <article><small>{{ t('ui.k0066') }}</small><strong>{{ formatRemainingTime(report.time_spent ?? elapsedSeconds) }}</strong></article>
      </div>
      <p>{{ t('ui.k0067') }} {{ report.correct_count }} {{ t('ui.k0068') }} {{ report.partial_count }} {{ t('ui.k0069') }} {{ report.incorrect_count }} {{ t('ui.k0070') }} {{ report.unanswered_count }}</p>

      <section v-if="report.type_stats && Object.keys(report.type_stats).length" class="exam-stats-group">
        <h3>{{ t('ui.k0071') }}</h3>
        <div class="stats-table-wrapper">
          <table class="stats-table">
            <thead>
              <tr><th>{{ t('ui.k0072') }}</th><th>{{ t('ui.k0073') }}</th><th>{{ t('ui.k0067') }}</th><th>{{ t('ui.k0074') }}</th><th>{{ t('ui.k0075') }}</th><th>{{ t('ui.k0064') }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="(val, type) in report.type_stats" :key="type">
                <td>{{ formatQuestionTypeName(type) }}</td>
                <td>{{ val.attempted }}</td>
                <td>{{ val.correct }}</td>
                <td>{{ val.partial }}</td>
                <td>{{ val.incorrect }}</td>
                <td>{{ calculateAccuracy(val.correct, val.attempted) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="report.tag_stats && Object.keys(report.tag_stats).length" class="exam-stats-group">
        <h3>{{ t('ui.k0076') }}</h3>
        <div class="stats-table-wrapper">
          <table class="stats-table">
            <thead>
              <tr><th>{{ t('ui.k0077') }}</th><th>{{ t('ui.k0073') }}</th><th>{{ t('ui.k0067') }}</th><th>{{ t('ui.k0075') }}</th><th>{{ t('ui.k0064') }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="(val, tag) in report.tag_stats" :key="tag">
                <td>{{ tag }}</td>
                <td>{{ val.attempted }}</td>
                <td>{{ val.correct }}</td>
                <td>{{ val.incorrect }}</td>
                <td>{{ calculateAccuracy(val.correct, val.attempted) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="reviewQuestions.length" class="exam-review">
        <h3>{{ t('ui.k0078') }}</h3>
        <article v-for="item in reviewQuestions" :key="item.id" class="review-item">
          <h4>{{ item.stem }}</h4>
          <p>{{ t('ui.k0079') }}{{ displayAnswer(report.answers[item.id]?.user_answer) }}</p>
          <p>{{ t('ui.k0080') }}{{ displayAnswer(report.answers[item.id]?.correct_answer) }}</p>
          <p v-if="report.answers[item.id]?.explanation">{{ report.answers[item.id].explanation }}</p>
        </article>
      </section>
      <button type="button" class="primary" @click="handleBack">{{ t('ui.k0081') }}</button>
    </section>

    <template v-else-if="question">
      <div class="exam-layout">
        <section class="exam-question-card">
          <div class="question-meta"><span>{{ t('ui.k0082') }} {{ currentIndex + 1 }} {{ t('ui.k0083') }} {{ questions.length }}</span><span class="badge-type">{{ formatQuestionTypeName(question.type) }}</span></div>
          <h2>{{ question.stem }}</h2>
          <div v-if="question.options?.length" class="exam-options">
            <label
              v-for="option in question.options"
              :key="option.key"
              class="exam-option"
              :class="{ selected: isOptionSelected(option.key) }"
            >
              <kbd class="key-cap" :title="`${t('ui.k0084')} ${option.key} ${t('ui.k0085')}`">{{ option.key }}</kbd>
              <input
                :type="question.type === 'MULTI' ? 'checkbox' : 'radio'"
                :name="`question-${question.id}`"
                :checked="isOptionSelected(option.key)"
                @change="selectOption(option.key, $event.target.checked)"
              />
              <span class="option-content-text">{{ option.content }}</span>
            </label>
          </div>
          <label v-else class="exam-text-answer">
            <span>{{ ['ESSAY', 'SUBJECTIVE'].includes(question.type) ? t('ui.k0654') : t('ui.k0655') }}</span>
            <textarea
              :value="currentTextAnswer"
              :rows="['ESSAY', 'SUBJECTIVE'].includes(question.type) ? 8 : 2"
              :placeholder="['ESSAY', 'SUBJECTIVE'].includes(question.type) ? t('ui.k0086') : t('ui.k0087')"
              @input="setTextAnswer($event.target.value)"
            />
          </label>

          <div class="exam-question-actions exam-fixed-action-bar">
            <div class="exam-actions-inner">
              <button type="button" class="btn-flag-toggle" data-testid="exam-flag-toggle" :aria-pressed="isFlagged" @click="toggleCurrentFlag" :title="t('ui.k0088')">
                <span class="flag-icon">
                  <LinearIcon name="target" size="13" />
                </span>
                <span>{{ isFlagged ? t('ui.k0656') : t('ui.k0657') }}</span>
                <kbd class="hotkey-badge">F</kbd>
              </button>
              <div class="exam-nav-btns">
                <button type="button" class="btn-exam-nav" :disabled="currentIndex === 0" @click="goTo(currentIndex - 1)" :title="t('ui.k0089')">
                  {{ t('ui.k0090') }}
                  <kbd class="hotkey-badge">←</kbd>
                </button>
                <button type="button" class="btn-exam-nav primary" :disabled="currentIndex >= questions.length - 1" @click="goTo(currentIndex + 1)" :title="t('ui.k0091')">
                  {{ t('ui.k0092') }}
                  <kbd class="hotkey-badge">→</kbd>
                </button>
              </div>
            </div>
          </div>
        </section>

        <aside class="exam-answer-sheet" data-testid="exam-answer-sheet" :aria-label="t('ui.k0093')">
          <h2>{{ t('ui.k0093') }}</h2>
          <p>{{ answeredCount }} {{ t('ui.k0094') }} {{ flaggedCount }} {{ t('ui.k0095') }}</p>
          <div class="sheet-legend">
            <span class="legend-item"><span class="legend-badge answered">✔</span> {{ t('ui.k0096') }}</span>
            <span class="legend-item"><span class="legend-badge flagged"><LinearIcon name="target" size="10" /></span> {{ t('ui.k0097') }}</span>
            <span class="legend-item"><span class="legend-badge current">●</span> {{ t('ui.k0098') }}</span>
            <span class="legend-item"><span class="legend-badge">○</span> {{ t('ui.k0099') }}</span>
          </div>
          <div class="answer-grid">
            <button
              v-for="(item, index) in questions"
              :key="item.id"
              type="button"
              :class="answerButtonClass(item.id, index)"
              :aria-label="`${t('ui.k0082')} ${index + 1} ${t('ui.k0101')}${answerState(item.id).answered ? t('ui.k0096') : t('ui.k0099')}${answerState(item.id).flagged ? t('ui.k0100') : ''}`"
              @click="goTo(index)"
            >{{ index + 1 }}</button>
          </div>
        </aside>
      </div>
    </template>
    <p v-else-if="!loading" class="exam-loading">{{ t('ui.k0102') }}</p>

    <!-- 移动端答题卡抽屉 -->
    <div v-if="showMobileSheet" class="exam-sheet-modal-backdrop" @click.self="showMobileSheet = false">
      <div class="exam-sheet-modal-drawer">
        <div class="exam-sheet-drawer-header">
          <h3>{{ t('ui.k0103') }} {{ answeredCount }} / {{ questions.length }})</h3>
          <button type="button" class="btn-close-sheet" @click="showMobileSheet = false">✕</button>
        </div>
        <div class="sheet-legend">
          <span class="legend-item"><span class="legend-badge answered">✔</span> {{ t('ui.k0096') }}</span>
          <span class="legend-item"><span class="legend-badge flagged"><LinearIcon name="target" size="10" /></span> {{ t('ui.k0104') }}</span>
          <span class="legend-item"><span class="legend-badge current">●</span> {{ t('ui.k0098') }}</span>
          <span class="legend-item"><span class="legend-badge">○</span> {{ t('ui.k0099') }}</span>
        </div>
        <div class="answer-grid">
          <button
            v-for="(item, index) in questions"
            :key="item.id"
            type="button"
            :class="answerButtonClass(item.id, index)"
            @click="goTo(index); showMobileSheet = false"
          >{{ index + 1 }}</button>
        </div>
      </div>
    </div>

    <div v-if="showSubmitConfirm" class="exam-confirm-backdrop" @click.self="showSubmitConfirm = false">
      <section class="exam-confirm-dialog" data-testid="exam-submit-confirm" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">{{ t('ui.k0105') }}</h2>
        <p>
          {{ t('ui.k0106') }}
          <button
            v-if="questions.length - answeredCount > 0"
            type="button"
            class="btn-link-jump"
            :title="t('ui.k0107')"
            @click="jumpToFirstUnanswered"
          >
            <strong>{{ questions.length - answeredCount }} {{ t('ui.k0108') }}</strong>
          </button>
          <span v-else>{{ t('ui.k0109') }}</span>，{{ flaggedCount }} {{ t('ui.k0110') }}
        </p>
        <div class="exam-question-actions">
          <button type="button" :disabled="isSubmitting" @click="showSubmitConfirm = false">{{ t('ui.k0111') }}</button>
          <button type="button" class="primary" :disabled="isSubmitting" @click="submitExam(false)">{{ isSubmitting ? t('ui.k0658') : t('ui.k0659') }}</button>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import LinearIcon from '../../components/LinearIcon.vue'
import ThemeToggle from '../../components/ThemeToggle.vue'
import LocaleToggle from '../../components/LocaleToggle.vue'
import { useLocale } from '../../composables/useLocale.js'
import { completeSession, getSession, getSessionQuestions, submitAttempt, syncDraft, toggleFlag } from '../../api/practice'
import { calculateAccuracy, examAnswerState, findFirstUnansweredIndex, formatQuestionTypeName, formatRemainingTime, isSwipeGestureValid, normalizeExamAnswer } from '../../domain/exam'

const { t } = useLocale()
const router = useRouter()

const props = defineProps({ token: { type: String, required: true }, sessionId: { type: String, required: true } })
const emit = defineEmits(['back'])

function handleBack() {
  emit('back')
  if (router && window.history.length > 1) {
    router.back()
  } else if (router) {
    router.push('/')
  }
}
const session = ref(null)
const questions = ref([])
const answers = ref({})
const flags = ref([])
const currentIndex = ref(0)
const elapsedSeconds = ref(0)
const report = ref(null)
const loading = ref(true)
const error = ref('')
const showMobileSheet = ref(false)

let touchStartX = 0
let touchStartY = 0
function handleTouchStart(e) {
  if (!e.touches || e.touches.length !== 1) return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}
function handleTouchEnd(e) {
  if (!e.changedTouches || e.changedTouches.length !== 1) return
  const touchEndX = e.changedTouches[0].clientX
  const touchEndY = e.changedTouches[0].clientY
  const gesture = isSwipeGestureValid(touchStartX, touchStartY, touchEndX, touchEndY)
  if (gesture === 'prev' && currentIndex.value > 0) {
    goTo(currentIndex.value - 1)
  } else if (gesture === 'next' && currentIndex.value < questions.value.length - 1) {
    goTo(currentIndex.value + 1)
  }
}

const isSubmitting = ref(false)
const showSubmitConfirm = ref(false)
let tickHandle
let draftHandle
let draftPromise = null
const question = computed(() => questions.value[currentIndex.value])
const remainingSeconds = computed(() => Math.max(0, Number(session.value?.time_limit || 0) * 60 - elapsedSeconds.value))
const answeredCount = computed(() => questions.value.filter(item => answerState(item.id).answered).length)
const flaggedCount = computed(() => flags.value.length)
const isFlagged = computed(() => question.value ? flags.value.includes(question.value.id) : false)
const currentTextAnswer = computed(() => {
  const value = question.value ? answerValue(question.value.id) : ''
  return Array.isArray(value) ? value.join('') : String(value ?? '')
})
const reviewQuestions = computed(() => questions.value.filter(item => report.value?.answers?.[item.id]))

function answerValue(questionId) {
  const saved = answers.value[questionId]
  return saved && typeof saved === 'object' && !Array.isArray(saved)
    ? saved.user_answer ?? saved.answer ?? ''
    : saved ?? ''
}

function answerState(questionId) { return examAnswerState(questionId, answers.value, flags.value) }
function isOptionSelected(key) {
  const value = answerValue(question.value.id)
  return question.value.type === 'MULTI' ? Array.isArray(value) && value.includes(key) : value === key
}
function answerButtonClass(questionId, index) {
  const state = answerState(questionId)
  return { current: index === currentIndex.value, answered: state.answered, flagged: state.flagged }
}
function displayAnswer(value) {
  if (Array.isArray(value)) return value.join('、') || t('ui.k0112')
  return value === undefined || value === null || value === '' ? t('ui.k0112') : String(value)
}

function scheduleDraftSave() {
  clearTimeout(draftHandle)
  draftHandle = setTimeout(() => { void persistDraft() }, 400)
}

async function persistDraft(force = false) {
  if (!session.value || (isSubmitting.value && !force) || report.value) return
  if (draftPromise) await draftPromise
  if (!session.value || (isSubmitting.value && !force) || report.value) return
  draftPromise = syncDraft(props.token, props.sessionId, {
    current_index: currentIndex.value,
    answers: answers.value,
    flags: flags.value,
    time_spent: elapsedSeconds.value,
  })
  try {
    await draftPromise
  } catch (err) {
    error.value = `${t('ui.k0113')}${err.detail || err.message}`
  } finally {
    draftPromise = null
  }
}

function selectOption(key, checked) {
  if (!question.value) return
  if (question.value.type === 'MULTI') {
    const selected = Array.isArray(answerValue(question.value.id)) ? [...answerValue(question.value.id)] : []
    answers.value[question.value.id] = checked ? [...new Set([...selected, key])].sort() : selected.filter(value => value !== key)
  } else {
    answers.value[question.value.id] = key
  }
  scheduleDraftSave()
}

function setTextAnswer(value) {
  answers.value[question.value.id] = value
  scheduleDraftSave()
}

function goTo(index) {
  if (index < 0 || index >= questions.value.length) return
  currentIndex.value = index
  scheduleDraftSave()
}

async function toggleCurrentFlag() {
  if (!question.value) return
  error.value = ''
  try {
    const result = await toggleFlag(props.token, props.sessionId, question.value.id)
    flags.value = result.flags
    scheduleDraftSave()
  } catch (err) {
    error.value = err.detail || err.message
  }
}

async function submitExam(automatic) {
  if (isSubmitting.value || report.value) return
  isSubmitting.value = true
  error.value = ''
  showSubmitConfirm.value = false
  clearTimeout(draftHandle)
  clearInterval(tickHandle)
  try {
    await persistDraft(true)
    for (const item of questions.value) {
      const answer = normalizeExamAnswer(item.type, answerValue(item.id))
      if (!examAnswerState(item.id, { [item.id]: answer }, []).answered) continue
      await submitAttempt(props.token, props.sessionId, { question_id: item.id, user_answer: answer })
    }
    report.value = await completeSession(props.token, props.sessionId)
    report.value.time_spent = elapsedSeconds.value
    if (automatic) error.value = t('ui.k0114')
  } catch (err) {
    error.value = `${t('ui.k0115')}${err.detail || err.message}`
    isSubmitting.value = false
    tickHandle = setInterval(tick, 1000)
  }
}

function tick() {
  elapsedSeconds.value += 1
  if (session.value?.time_limit && remainingSeconds.value <= 0) void submitExam(true)
  else if (elapsedSeconds.value % 10 === 0) void persistDraft()
}

function jumpToFirstUnanswered() {
  const idx = findFirstUnansweredIndex(questions.value, answers.value)
  if (idx >= 0) {
    goTo(idx)
    showSubmitConfirm.value = false
  }
}

function handleKeyDown(e) {
  const targetTag = e.target?.tagName?.toLowerCase()
  if (targetTag === 'input' || targetTag === 'textarea' || targetTag === 'select') {
    return
  }

  const key = e.key.toUpperCase()

  // 1. Select options via A, B, C, D... or 1, 2, 3, 4...
  if (question.value?.options?.length && !report.value) {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    let optKey = null
    if (letters.includes(key)) {
      optKey = key
    } else if (['1', '2', '3', '4', '5', '6', '7', '8'].includes(e.key)) {
      const idx = parseInt(e.key, 10) - 1
      if (idx >= 0 && idx < question.value.options.length) {
        optKey = question.value.options[idx].key
      }
    }
    if (optKey) {
      const exists = question.value.options.some(o => o.key === optKey)
      if (exists) {
        e.preventDefault()
        const currentSelected = isOptionSelected(optKey)
        selectOption(optKey, !currentSelected)
        return
      }
    }
  }

  // 2. Next on Space, ArrowRight, J
  if (e.key === ' ' || e.key === 'ArrowRight' || key === 'J') {
    if (currentIndex.value < questions.value.length - 1) {
      e.preventDefault()
      goTo(currentIndex.value + 1)
      return
    }
  }

  // 3. Prev on ArrowLeft, K
  if (e.key === 'ArrowLeft' || key === 'K') {
    if (currentIndex.value > 0) {
      e.preventDefault()
      goTo(currentIndex.value - 1)
      return
    }
  }

  // 4. Toggle flag on F
  if (key === 'F') {
    e.preventDefault()
    toggleCurrentFlag()
    return
  }

  // 5. Esc closes confirm modal
  if (e.key === 'Escape' && showSubmitConfirm.value) {
    e.preventDefault()
    showSubmitConfirm.value = false
    return
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeyDown)
  try {
    session.value = await getSession(props.token, props.sessionId)
    questions.value = await getSessionQuestions(props.token, props.sessionId)
    answers.value = { ...(session.value.answers || {}) }
    flags.value = [...(session.value.flags || [])]
    currentIndex.value = Math.min(Number(session.value.current_index || 0), Math.max(0, questions.value.length - 1))
    elapsedSeconds.value = Number(session.value.time_spent || 0)
    if (session.value.is_completed) report.value = await completeSession(props.token, props.sessionId)
    if (!report.value && session.value.time_limit > 0) {
      const createdAt = Date.parse(`${session.value.created_at}Z`)
      if (Number.isFinite(createdAt)) elapsedSeconds.value = Math.max(elapsedSeconds.value, Math.floor((Date.now() - createdAt) / 1000))
    }
    if (!report.value) tickHandle = setInterval(tick, 1000)
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyDown)
  clearInterval(tickHandle)
  clearTimeout(draftHandle)
  if (session.value && !report.value) void persistDraft()
})
</script>

<style scoped>
.exam-page {
  width: min(100% - 2rem, 76rem);
  margin: 1.25rem auto;
  padding-bottom: 5.5rem;
}
.exam-header { display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.exam-header.report-header { display: flex; justify-content: flex-start; gap: 1.25rem; }
.exam-header h1 { font-size: 1.25rem; }
.exam-header p, .exam-answer-sheet p, .question-meta { color: var(--text-muted); }
.exam-clock { min-width: 5.5rem; padding: 0.5rem 0.75rem; border: 1px solid var(--border); border-radius: 0.65rem; background: var(--bg-card); text-align: center; font-variant-numeric: tabular-nums; font-weight: 700; }
.exam-clock.warning { color: var(--danger); }
.exam-layout { display: grid; grid-template-columns: minmax(0, 1fr) 17rem; gap: 1.25rem; align-items: start; }
.exam-question-card { padding: 1.5rem; border: 1px solid var(--border); border-radius: 1rem; background: var(--bg-card); box-shadow: var(--shadow-sm); }
.exam-report {
  padding: 2rem 1.75rem;
  border: 1px solid var(--border);
  border-radius: 1rem;
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  max-width: 52rem;
  margin: 0 auto;
}
.exam-answer-sheet {
  padding: 1.25rem;
  border: 1px solid var(--border);
  border-radius: 1rem;
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 1rem;
  max-height: calc(100vh - 7.5rem);
  overflow-y: auto;
}
.question-meta { display: flex; justify-content: space-between; margin-bottom: 1rem; }
.exam-question-card h2 { margin-bottom: 1.25rem; font-size: 1.2rem; white-space: pre-wrap; }
.exam-options { display: grid; gap: 0.65rem; }
.exam-option {
  display: flex;
  gap: 0.7rem;
  align-items: center;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--linear-bg-surface);
  cursor: pointer;
  transition: all 0.1s cubic-bezier(0.16, 1, 0.3, 1);
}
.exam-option:hover {
  border-color: var(--border-strong);
  background: var(--linear-bg-hover);
}
.exam-option.selected {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--text-main);
  box-shadow: 0 0 0 1px var(--primary);
}
.exam-option.selected .key-cap {
  background: var(--primary);
  color: var(--on-primary);
  border-color: var(--primary);
}
.exam-option input { margin: 0; accent-color: var(--primary); }
.exam-text-answer { display: grid; gap: 0.5rem; }
.exam-text-answer textarea { width: 100%; min-height: 4rem; padding: 0.75rem; border: 1px solid var(--border); border-radius: var(--radius-md); resize: vertical; }

.exam-fixed-action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: color-mix(in srgb, var(--bg-card) 94%, transparent);
  backdrop-filter: blur(10px);
  border-top: 1px solid var(--border);
  box-shadow: 0 -4px 16px color-mix(in srgb, var(--text-main) 16%, transparent);
  padding: 0.65rem 1.25rem;
  z-index: 50;
}

.exam-actions-inner {
  width: min(100%, 76rem);
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.btn-flag-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.9rem;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-main);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-flag-toggle[aria-pressed="true"] {
  background: var(--warning-light);
  border-color: var(--warning);
  color: var(--warning-hover);
}

.exam-nav-btns {
  display: flex;
  gap: 0.6rem;
  align-items: center;
}

.btn-exam-nav {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 1.1rem;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-main);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-exam-nav:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
}

.btn-exam-nav.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--on-primary);
}

.btn-exam-nav.primary:hover:not(:disabled) {
  background: var(--primary-hover);
}

.btn-exam-nav:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.exam-answer-sheet h2, .exam-answer-sheet p { margin-bottom: 0.5rem; }
.answer-grid { display: grid; grid-template-columns: repeat(5, minmax(2.2rem, 1fr)); gap: 0.45rem; margin-top: 1rem; }
.answer-grid button { min-height: 2.3rem; border: 1px solid var(--border); border-radius: 0.55rem; background: var(--bg-page); }
.answer-grid button.answered { border-color: var(--success); background: var(--success-light); }
.answer-grid button.flagged { box-shadow: inset 0 -3px var(--warning); }
.answer-grid button.current { outline: 2px solid var(--primary); outline-offset: 1px; }
.primary { padding: 0.65rem 0.9rem; border-radius: 0.6rem; background: var(--primary); color: var(--on-primary); }
.primary:disabled { opacity: 0.55; cursor: wait; }
.exam-error { margin: 0.75rem 0; color: var(--danger); }
.exam-loading { padding: 2rem; text-align: center; color: var(--text-muted); }
.exam-report h2, .exam-report h3 { margin-bottom: 1rem; }
.report-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin: 1rem 0; }
.report-summary article { display: grid; gap: 0.25rem; padding: 0.85rem; border-radius: 0.75rem; background: var(--bg-page); }
.report-summary small { color: var(--text-muted); }
.report-summary strong { font-size: 1.25rem; }
.exam-stats-group { margin: 1.25rem 0; }
.stats-table-wrapper { overflow-x: auto; }
.stats-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; font-size: 0.95rem; }
.stats-table th, .stats-table td { padding: 0.6rem 0.75rem; border: 1px solid var(--border); text-align: center; }
.stats-table th { background: var(--bg-page); font-weight: 600; }
.exam-review { margin: 1.5rem 0; }
.review-item { padding: 1rem 0; border-top: 1px solid var(--border); }
.exam-confirm-backdrop { position: fixed; inset: 0; z-index: 30; display: grid; place-items: center; padding: 1rem; background: color-mix(in srgb, var(--text-main) 44%, transparent); }
.exam-confirm-dialog { width: min(100%, 28rem); padding: 1.5rem; border-radius: 1rem; background: var(--bg-card); box-shadow: var(--shadow-lg); }
.exam-confirm-dialog p { margin-top: 0.5rem; color: var(--text-muted); }
.btn-back { padding: 0.4rem 0.65rem; border: 1px solid var(--border); border-radius: 0.5rem; background: var(--bg-card); cursor: pointer; }
.btn-exam-sheet-trigger { cursor: pointer; font-size: 0.85rem; padding: 0.4rem 0.65rem; }
.mobile-only-btn { display: none !important; }
.exam-header-center { cursor: pointer; }

/* Exam Mobile Sheet Modal Drawer */
.exam-sheet-modal-backdrop {
  position: fixed;
  inset: 0;
  background: color-mix(in srgb, var(--text-main) 44%, transparent);
  backdrop-filter: blur(2px);
  z-index: 100;
  display: flex;
  justify-content: center;
  align-items: flex-end;
}
.exam-sheet-modal-drawer {
  background: var(--bg-card);
  width: 100%;
  max-width: 42rem;
  max-height: 80vh;
  border-radius: 1rem 1rem 0 0;
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  padding: 1.15rem 1.25rem;
  overflow-y: auto;
  animation: slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.exam-sheet-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.85rem;
}
.btn-close-sheet {
  border: none;
  background: var(--bg-muted);
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 50%;
  cursor: pointer;
  font-weight: 700;
  color: var(--text-muted);
}

@media (max-width: 760px) {
  .exam-page { width: 100%; margin: 0; padding: 0.35rem 0.5rem 5.5rem; }
  .exam-layout { grid-template-columns: 1fr; }
  .exam-answer-sheet { display: none !important; } /* Hide stuck-at-bottom sheet on mobile, use modal drawer */
  .exam-header {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    flex-wrap: nowrap !important;
    gap: 0.35rem !important;
    padding: 0.4rem 0.65rem !important;
  }
  .exam-header-center {
    flex: 1;
    min-width: 0;
  }
  .exam-header h1 {
    font-size: 0.95rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .exam-header p { font-size: 0.725rem; white-space: nowrap; }
  .exam-clock { min-width: auto; padding: 0.25rem 0.45rem; font-size: 0.775rem; white-space: nowrap; }
  .mobile-only-btn { display: inline-flex !important; }
  .exam-question-card { padding: 0.85rem; border-radius: var(--radius-md); }
  .exam-question-card h2 { font-size: 1.05rem; margin-bottom: 0.85rem; line-height: 1.45; }
  .exam-options { gap: 0.5rem; }
  .exam-option { padding: 0.6rem 0.75rem; border-radius: var(--radius-md); }
  .exam-option input { display: none !important; }
  .key-cap { min-width: 1.5rem; height: 1.5rem; font-size: 0.8rem; }
  .hotkey-badge { display: none !important; }
  .answer-grid { grid-template-columns: repeat(8, minmax(2rem, 1fr)); }
  .report-summary { grid-template-columns: repeat(2, 1fr); }
  .exam-header .primary {
    font-size: 0.8rem;
    padding: 0.35rem 0.6rem;
    white-space: nowrap;
  }
  .exam-fixed-action-bar {
    padding: 0.45rem 0.75rem calc(0.45rem + env(safe-area-inset-bottom, 0px));
  }
  .btn-flag-toggle {
    padding: 0.45rem 0.7rem;
    font-size: 0.8rem;
  }
  .btn-exam-nav {
    padding: 0.45rem 0.85rem;
    font-size: 0.8rem;
  }
}
</style>
