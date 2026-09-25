<template>
  <main class="exam-page">
    <header class="exam-header">
      <button type="button" @click="$emit('back')">返回</button>
      <div>
        <h1>模拟考试</h1>
        <p>{{ session ? `已作答 ${answeredCount} / ${questions.length}` : '正在载入考试…' }}</p>
      </div>
      <div class="exam-clock" data-testid="exam-timer" role="timer" aria-live="off">
        {{ session?.time_limit ? formatRemainingTime(remainingSeconds) : '不限时' }}
      </div>
      <button type="button" class="primary" :disabled="loading || isSubmitting || Boolean(report)" @click="showSubmitConfirm = true">交卷</button>
    </header>

    <p v-if="error" class="exam-error" role="alert">{{ error }}</p>
    <p v-if="loading" class="exam-loading">正在恢复考试进度…</p>

    <section v-else-if="report" class="exam-report" aria-labelledby="exam-report-title">
      <h2 id="exam-report-title">考试报告</h2>
      <div class="report-summary">
        <article><small>得分</small><strong>{{ report.score }}</strong></article>
        <article><small>正确率</small><strong>{{ report.accuracy }}%</strong></article>
        <article><small>答题数</small><strong>{{ report.answered_count }} / {{ report.total_questions }}</strong></article>
        <article><small>耗时</small><strong>{{ formatRemainingTime(report.time_spent ?? elapsedSeconds) }}</strong></article>
      </div>
      <p>正确 {{ report.correct_count }} · 部分得分 {{ report.partial_count }} · 错误 {{ report.incorrect_count }} · 未作答 {{ report.unanswered_count }}</p>

      <section v-if="report.type_stats && Object.keys(report.type_stats).length" class="exam-stats-group">
        <h3>题型统计</h3>
        <div class="stats-table-wrapper">
          <table class="stats-table">
            <thead>
              <tr><th>题型</th><th>作答</th><th>正确</th><th>部分分</th><th>错误</th><th>正确率</th></tr>
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
        <h3>知识点掌握</h3>
        <div class="stats-table-wrapper">
          <table class="stats-table">
            <thead>
              <tr><th>知识点</th><th>作答</th><th>正确</th><th>错误</th><th>正确率</th></tr>
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
        <h3>答题回顾</h3>
        <article v-for="item in reviewQuestions" :key="item.id" class="review-item">
          <h4>{{ item.stem }}</h4>
          <p>你的答案：{{ displayAnswer(report.answers[item.id]?.user_answer) }}</p>
          <p>标准答案：{{ displayAnswer(report.answers[item.id]?.correct_answer) }}</p>
          <p v-if="report.answers[item.id]?.explanation">{{ report.answers[item.id].explanation }}</p>
        </article>
      </section>
      <button type="button" class="primary" @click="$emit('back')">返回题库</button>
    </section>

    <template v-else-if="question">
      <div class="exam-layout">
        <section class="exam-question-card">
          <div class="question-meta"><span>第 {{ currentIndex + 1 }} 题 / {{ questions.length }}</span><span>{{ question.type }}</span></div>
          <h2>{{ question.stem }}</h2>
          <div v-if="question.options?.length" class="exam-options">
            <label v-for="option in question.options" :key="option.key" class="exam-option">
              <input
                :type="question.type === 'MULTI' ? 'checkbox' : 'radio'"
                :name="`question-${question.id}`"
                :checked="isOptionSelected(option.key)"
                @change="selectOption(option.key, $event.target.checked)"
              />
              <span>{{ option.key }}. {{ option.content }}</span>
            </label>
          </div>
          <label v-else class="exam-text-answer">
            <span>{{ ['ESSAY', 'SUBJECTIVE'].includes(question.type) ? '作答内容' : '填写答案' }}</span>
            <textarea
              :value="currentTextAnswer"
              :rows="['ESSAY', 'SUBJECTIVE'].includes(question.type) ? 8 : 2"
              :placeholder="['ESSAY', 'SUBJECTIVE'].includes(question.type) ? '输入你的作答' : '输入答案'"
              @input="setTextAnswer($event.target.value)"
            />
          </label>

          <div class="exam-question-actions">
            <button type="button" data-testid="exam-flag-toggle" :aria-pressed="isFlagged" @click="toggleCurrentFlag">
              {{ isFlagged ? '取消待复查' : '标记待复查' }}
            </button>
            <div>
              <button type="button" :disabled="currentIndex === 0" @click="goTo(currentIndex - 1)">上一题</button>
              <button type="button" :disabled="currentIndex >= questions.length - 1" @click="goTo(currentIndex + 1)">下一题</button>
            </div>
          </div>
        </section>

        <aside class="exam-answer-sheet" data-testid="exam-answer-sheet" aria-label="答题卡">
          <h2>答题卡</h2>
          <p>{{ answeredCount }} 题已答 · {{ flaggedCount }} 题待复查</p>
          <div class="answer-grid">
            <button
              v-for="(item, index) in questions"
              :key="item.id"
              type="button"
              :class="answerButtonClass(item.id, index)"
              :aria-label="`第 ${index + 1} 题${answerState(item.id).answered ? '已答' : '未答'}${answerState(item.id).flagged ? '，待复查' : ''}`"
              @click="goTo(index)"
            >{{ index + 1 }}</button>
          </div>
        </aside>
      </div>
    </template>
    <p v-else-if="!loading" class="exam-loading">本次考试没有可用题目。</p>

    <div v-if="showSubmitConfirm" class="exam-confirm-backdrop">
      <section class="exam-confirm-dialog" data-testid="exam-submit-confirm" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">确认交卷？</h2>
        <p>还有 {{ questions.length - answeredCount }} 题未答，{{ flaggedCount }} 题待复查。</p>
        <div class="exam-question-actions">
          <button type="button" :disabled="isSubmitting" @click="showSubmitConfirm = false">继续作答</button>
          <button type="button" class="primary" :disabled="isSubmitting" @click="submitExam(false)">{{ isSubmitting ? '正在交卷…' : '确认交卷' }}</button>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { completeSession, getSession, getSessionQuestions, submitAttempt, syncDraft, toggleFlag } from '../../api/practice'
import { calculateAccuracy, examAnswerState, formatQuestionTypeName, formatRemainingTime, normalizeExamAnswer } from '../../domain/exam'

const props = defineProps({ token: { type: String, required: true }, sessionId: { type: String, required: true } })
defineEmits(['back'])
const session = ref(null)
const questions = ref([])
const answers = ref({})
const flags = ref([])
const currentIndex = ref(0)
const elapsedSeconds = ref(0)
const report = ref(null)
const loading = ref(true)
const error = ref('')
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
  if (Array.isArray(value)) return value.join('、') || '未作答'
  return value === undefined || value === null || value === '' ? '未作答' : String(value)
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
    error.value = `进度暂未同步：${err.detail || err.message}`
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
    if (automatic) error.value = '考试时间已到，系统已自动交卷。'
  } catch (err) {
    error.value = `交卷未完成，请检查网络后重试：${err.detail || err.message}`
    isSubmitting.value = false
    tickHandle = setInterval(tick, 1000)
  }
}

function tick() {
  elapsedSeconds.value += 1
  if (session.value?.time_limit && remainingSeconds.value <= 0) void submitExam(true)
  else if (elapsedSeconds.value % 10 === 0) void persistDraft()
}

onMounted(async () => {
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
  clearInterval(tickHandle)
  clearTimeout(draftHandle)
  if (session.value && !report.value) void persistDraft()
})
</script>

<style scoped>
.exam-page { width: min(100% - 2rem, 76rem); margin: 1.25rem auto; }
.exam-header { display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.exam-header h1 { font-size: 1.25rem; }
.exam-header p, .exam-answer-sheet p, .question-meta { color: var(--text-muted); }
.exam-clock { min-width: 5.5rem; padding: 0.5rem 0.75rem; border: 1px solid var(--border); border-radius: 0.65rem; background: var(--bg-card); text-align: center; font-variant-numeric: tabular-nums; font-weight: 700; }
.exam-clock.warning { color: var(--danger); }
.exam-layout { display: grid; grid-template-columns: minmax(0, 1fr) 17rem; gap: 1rem; align-items: start; }
.exam-question-card, .exam-answer-sheet, .exam-report { padding: 1.25rem; border: 1px solid var(--border); border-radius: 1rem; background: var(--bg-card); box-shadow: var(--shadow-sm); }
.question-meta { display: flex; justify-content: space-between; margin-bottom: 1rem; }
.exam-question-card h2 { margin-bottom: 1.25rem; font-size: 1.2rem; white-space: pre-wrap; }
.exam-options { display: grid; gap: 0.65rem; }
.exam-option { display: flex; gap: 0.7rem; align-items: flex-start; padding: 0.8rem; border: 1px solid var(--border); border-radius: 0.7rem; cursor: pointer; }
.exam-option input { margin-top: 0.3rem; }
.exam-text-answer { display: grid; gap: 0.5rem; }
.exam-text-answer textarea { width: 100%; min-height: 4rem; padding: 0.75rem; border: 1px solid var(--border); border-radius: 0.7rem; resize: vertical; }
.exam-question-actions { display: flex; justify-content: space-between; gap: 0.75rem; margin-top: 1.25rem; }
.exam-question-actions > div { display: flex; gap: 0.5rem; }
.exam-answer-sheet h2, .exam-answer-sheet p { margin-bottom: 0.5rem; }
.answer-grid { display: grid; grid-template-columns: repeat(5, minmax(2.2rem, 1fr)); gap: 0.45rem; margin-top: 1rem; }
.answer-grid button { min-height: 2.3rem; border: 1px solid var(--border); border-radius: 0.55rem; background: var(--bg-page); }
.answer-grid button.answered { border-color: var(--success); background: var(--success-light); }
.answer-grid button.flagged { box-shadow: inset 0 -3px var(--warning); }
.answer-grid button.current { outline: 2px solid var(--primary); outline-offset: 1px; }
.primary { padding: 0.65rem 0.9rem; border-radius: 0.6rem; background: var(--primary); color: white; }
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
.exam-confirm-backdrop { position: fixed; inset: 0; z-index: 30; display: grid; place-items: center; padding: 1rem; background: rgb(15 23 42 / 0.48); }
.exam-confirm-dialog { width: min(100%, 28rem); padding: 1.5rem; border-radius: 1rem; background: var(--bg-card); box-shadow: var(--shadow-lg); }
.exam-confirm-dialog p { margin-top: 0.5rem; color: var(--text-muted); }
@media (max-width: 760px) {
  .exam-layout { grid-template-columns: 1fr; }
  .exam-answer-sheet { order: -1; }
  .answer-grid { grid-template-columns: repeat(8, minmax(2rem, 1fr)); }
  .report-summary { grid-template-columns: repeat(2, 1fr); }
  .exam-header { grid-template-columns: auto 1fr auto; }
  .exam-header .primary { grid-column: 1 / -1; }
}
</style>
