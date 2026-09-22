<template>
  <div class="practice-container">
    <!-- Top Navigation Bar -->
    <header class="top-nav">
      <button class="nav-back-btn" @click="handleBack" aria-label="返回题库">
        <span class="back-arrow">‹</span>
        <span class="back-text">题库</span>
      </button>

      <div class="nav-center">
        <span class="mode-badge" :class="'badge-' + mode.toLowerCase()">
          {{ modeLabel }}
        </span>
        <span class="progress-indicator">
          {{ currentQuestionIndex + 1 }} / {{ questions.length || 0 }}
        </span>
      </div>

      <div class="nav-actions">
        <!-- Timer -->
        <div class="timer-display" :class="{ 'timer-warning': mode === 'EXAM' && remainingSeconds < 300 }">
          ⏱️ {{ formattedTimer }}
        </div>

        <!-- Toggle Doubt/Flag -->
        <button
          class="btn-flag"
          :class="{ 'is-flagged': isCurrentFlagged }"
          @click="toggleFlag"
          title="标记存疑题目"
        >
          ★
        </button>

        <!-- Answer Drawer Toggle Button -->
        <button class="btn-sheet" @click="isAnswerDrawerOpen = true" title="答题卡">
          <span class="sheet-icon">▦</span>
        </button>
      </div>
    </header>

    <!-- Combo Streak Notification Banner -->
    <transition name="combo">
      <div v-if="comboStreak >= 2 && showCombo" class="combo-banner animate-combo">
        <span class="combo-icon">🔥</span>
        <span class="combo-text">连对 {{ comboStreak }} 题！{{ comboTagline }}</span>
      </div>
    </transition>

    <!-- Auto-Jump Next & Mode Options Sub-bar -->
    <div class="sub-bar">
      <div class="draft-indicator">
        <span class="dot-sync" :class="'sync-' + syncStatus"></span>
        <span class="sync-text">{{ syncLabel }}</span>
      </div>

      <div v-if="mode === 'PRACTICE'" class="auto-jump-toggle">
        <label class="toggle-label">
          <input v-model="autoJumpNext" type="checkbox" class="toggle-checkbox" />
          <span class="toggle-switch"></span>
          <span class="toggle-text">答对自动下一题</span>
        </label>
      </div>

      <button
        v-if="mode === 'EXAM'"
        class="btn-quick-submit"
        @click="confirmSubmitSession"
      >
        交卷
      </button>
    </div>

    <!-- Main Question Swipe Area -->
    <main ref="swipeContainer" class="question-main">
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>正在装载题目...</p>
      </div>

      <div v-else-if="currentQuestion" class="question-card">
        <!-- Question Meta -->
        <div class="question-meta">
          <span class="qtype-tag">{{ typeLabel(currentQuestion.type) }}</span>
          <span class="difficulty-stars" :title="'难度 ' + (currentQuestion.difficulty || 3)">
            {{ '★'.repeat(currentQuestion.difficulty || 3) }}
          </span>
          <span v-if="currentQuestion.tags && currentQuestion.tags.length" class="meta-tag">
            {{ currentQuestion.tags[0] }}
          </span>
        </div>

        <!-- Question Stem -->
        <h2 class="question-stem">{{ currentQuestion.stem }}</h2>

        <!-- Options Container -->
        <div class="options-list">
          <button
            v-for="(opt, idx) in formattedOptions"
            :key="opt.key"
            class="option-item"
            :class="getOptionClass(opt.key)"
            :disabled="isOptionDisabled(opt.key)"
            @click="handleSelectOption(opt.key)"
          >
            <div class="option-key-badge">{{ opt.key }}</div>
            <div class="option-text">{{ opt.text }}</div>
            <div class="option-feedback-icon">
              <span v-if="getOptionIcon(opt.key)" class="feedback-icon">{{ getOptionIcon(opt.key) }}</span>
            </div>
          </button>
        </div>

        <!-- Multi-choice confirmation button -->
        <div v-if="currentQuestion.type === 'MULTI' && !currentResult" class="multi-confirm-bar">
          <button
            class="btn-multi-submit"
            :disabled="!currentMultiAnswers.length"
            @click="submitMultiAnswer"
          >
            确认提交选择 (已选 {{ currentMultiAnswers.join(', ') || '无' }})
          </button>
        </div>

        <!-- Instant Practice Feedback & Explanation Card -->
        <transition name="fade">
          <div v-if="currentResult" class="explanation-card">
            <div class="result-header" :class="currentResult.is_correct ? 'res-correct' : 'res-wrong'">
              <span class="res-status-icon">{{ currentResult.is_correct ? '✓' : '✕' }}</span>
              <span class="res-status-text">
                {{ currentResult.is_correct ? '回答正确！' : '回答错误' }}
              </span>
              <span class="res-answers-text">
                正确答案: <strong>{{ currentResult.correct_answer }}</strong>
                <span v-if="!currentResult.is_correct && currentAnswer">
                  (你的作答: {{ currentAnswer }})
                </span>
              </span>
            </div>

            <!-- 6-Level Mistake Taxonomy Selector (shown when wrong) -->
            <div v-if="!currentResult.is_correct" class="mistake-cause-section">
              <p class="cause-title">🎯 错题归因靶向诊断 (点击记录错因):</p>
              <div class="cause-capsules">
                <button
                  v-for="cause in mistakeCauses"
                  :key="cause.key"
                  class="cause-capsule"
                  :class="{ 'cause-active': selectedCauses[currentQuestion.id] === cause.key }"
                  @click="handleSelectCause(cause.key)"
                >
                  <span class="cause-icon">{{ cause.icon }}</span>
                  <span class="cause-label">{{ cause.label }}</span>
                </button>
              </div>
            </div>

            <!-- Official Explanation -->
            <div class="official-explanation">
              <div class="explanation-title">💡 官方解析</div>
              <p class="explanation-content">
                {{ currentResult.explanation || currentQuestion.explanation || '暂无官方详细解析。' }}
              </p>
            </div>

            <!-- AI Tutor Trigger Button -->
            <div class="tutor-trigger-bar">
              <button class="btn-ask-tutor" @click="isAiTutorOpen = true">
                <span class="tutor-emoji">🤖</span>
                <span class="tutor-btn-text">问 AI 助教 · 针对性点拨错题</span>
              </button>
            </div>
          </div>
        </transition>
      </div>

      <div v-else class="empty-state">
        <p>未找到题目</p>
      </div>
    </main>

    <!-- Bottom Action Bar -->
    <footer class="bottom-bar">
      <button
        class="nav-step-btn"
        :disabled="currentQuestionIndex <= 0"
        @click="goPrev"
      >
        ‹ 上一题
      </button>

      <button class="sheet-toggle-btn" @click="isAnswerDrawerOpen = true">
        <span class="sheet-summary">答题卡 ({{ answeredCount }}/{{ questions.length }})</span>
      </button>

      <button
        v-if="currentQuestionIndex < questions.length - 1"
        class="nav-step-btn btn-primary-step"
        @click="goNext"
      >
        下一题 ›
      </button>
      <button
        v-else
        class="nav-step-btn btn-finish-step"
        @click="confirmSubmitSession"
      >
        {{ mode === 'EXAM' ? '交卷' : '完成' }}
      </button>
    </footer>

    <!-- Answer Sheet Bottom Drawer -->
    <AnswerDrawer
      :visible="isAnswerDrawerOpen"
      :total="questions.length"
      :current-index="currentQuestionIndex"
      :questions="questions"
      :answers="answers"
      :results="results"
      :flags="flags"
      :mode="mode"
      @close="isAnswerDrawerOpen = false"
      @select="handleJumpToQuestion"
      @submit="confirmSubmitSession"
    />

    <!-- AI Tutor Drawer -->
    <AiTutorDrawer
      :visible="isAiTutorOpen"
      :context="currentTutorContext"
      @close="isAiTutorOpen = false"
    />

    <!-- Exam / Practice Diagnosis Report Modal -->
    <div v-if="isCompleted && report" class="modal-overlay">
      <div class="report-card animate-slide-up">
        <div class="report-header" :class="report.passed ? 'report-passed' : 'report-failed'">
          <div class="report-trophy">{{ report.passed ? '🎉' : '📊' }}</div>
          <h2 class="report-title">{{ report.passed ? '恭喜通过本次考核！' : '考核完成，继续努力！' }}</h2>
          <p class="report-subtitle">
            得分: <strong class="report-score-num">{{ report.score }}</strong> / {{ report.total_score }} 分
            (正确率: {{ (report.accuracy * 100).toFixed(1) }}%)
          </p>
        </div>

        <div class="report-stats-grid">
          <div class="stat-box">
            <span class="stat-label">总题数</span>
            <span class="stat-val">{{ report.total_questions }}</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">已作答</span>
            <span class="stat-val">{{ report.answered_questions }}</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">用时</span>
            <span class="stat-val">{{ formatSeconds(report.time_spent) }}</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">及格线</span>
            <span class="stat-val">{{ report.passing_score }} 分</span>
          </div>
        </div>

        <!-- Breakdown table -->
        <div v-if="report.breakdown && Object.keys(report.breakdown).length" class="report-breakdown">
          <h4 class="breakdown-title">题型得分详情</h4>
          <table class="breakdown-table">
            <thead>
              <tr>
                <th>题型</th>
                <th>题数</th>
                <th>正确</th>
                <th>得分</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(b, t) in report.breakdown" :key="t">
                <td>{{ typeLabel(t) }}</td>
                <td>{{ b.total }}</td>
                <td>{{ b.correct }}</td>
                <td>{{ b.score }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="report-actions">
          <button class="btn-review-wrong" @click="handleReviewWrongQuestions">
            🔍 查看错题解析
          </button>
          <button class="btn-finish-all" @click="handleBack">
            返回主页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useSwipe } from '../composables/useSwipe'
import { useDraftStorage } from '../composables/useDraftStorage'
import AnswerDrawer from '../components/AnswerDrawer.vue'
import AiTutorDrawer from '../components/AiTutorDrawer.vue'

const props = defineProps({
  sessionId: {
    type: String,
    required: true
  },
  bankId: {
    type: String,
    required: true
  },
  initialMode: {
    type: String,
    default: 'PRACTICE'
  },
  initialTimeLimit: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['back', 'session-completed'])

// Main state
const loading = ref(true)
const mode = ref(props.initialMode)
const questions = ref([])
const currentQuestionIndex = ref(0)
const answers = ref({})
const results = ref({})
const flags = ref([])
const selectedCauses = ref({})

// Multi-choice helper
const currentMultiAnswers = ref([])

// Combo streak state
const comboStreak = ref(0)
const showCombo = ref(false)
let comboTimer = null

// Auto jump next toggle in practice mode
const autoJumpNext = ref(true)

// Drawers
const isAnswerDrawerOpen = ref(false)
const isAiTutorOpen = ref(false)

// Timer
const elapsedSeconds = ref(0)
const remainingSeconds = ref(props.initialTimeLimit > 0 ? props.initialTimeLimit * 60 : 0)
let timerInterval = null

// Result & Report
const isCompleted = ref(false)
const report = ref(null)

// Gestures & swipe ref
const swipeContainer = ref(null)

// Draft storage
const {
  syncStatus,
  saveLocal,
  loadLocal,
  clearLocal,
  flushSync,
  queueSync
} = useDraftStorage(props.sessionId)

// Setup swipe gesture with vertical scroll protection: |Δx| >= 40 and |Δx / Δy| >= 1.73
useSwipe(swipeContainer, {
  onSwipeLeft: () => goNext(),
  onSwipeRight: () => goPrev(),
  threshold: 40,
  ratio: 1.73
})

// 6-level taxonomy causes
const mistakeCauses = [
  { key: 'READING_MISS', label: '审题粗心', icon: '👀' },
  { key: 'CONCEPT_GAP', label: '概念盲区', icon: '📖' },
  { key: 'METHOD_GAP', label: '思路不熟', icon: '🧩' },
  { key: 'OPTION_TRAP', label: '陷阱诱导', icon: '🕳️' },
  { key: 'CALCULATION_ERROR', label: '计算失误', icon: '🔢' },
  { key: 'CARELESSNESS', label: '其他手滑', icon: '🖐️' }
]

// Computed labels
const modeLabel = computed(() => {
  if (mode.value === 'EXAM') return '全真模考'
  if (mode.value === 'ELIMINATION') return '错题攻坚'
  return '刷题练习'
})

const syncLabel = computed(() => {
  if (syncStatus.value === 'saving') return '同步中...'
  if (syncStatus.value === 'synced') return '已实时云同步'
  if (syncStatus.value === 'error') return '离线草稿保护'
  return '草稿保护中'
})

const currentQuestion = computed(() => {
  if (!questions.value.length) return null
  return questions.value[currentQuestionIndex.value] || null
})

const currentAnswer = computed(() => {
  if (!currentQuestion.value) return null
  return answers.value[currentQuestion.value.id]
})

const currentResult = computed(() => {
  if (!currentQuestion.value) return null
  return results.value[currentQuestion.value.id] || null
})

const isCurrentFlagged = computed(() => {
  if (!currentQuestion.value) return false
  return flags.value.includes(currentQuestion.value.id)
})

const answeredCount = computed(() => {
  return Object.keys(answers.value).filter(k => answers.value[k] !== undefined && answers.value[k] !== null && answers.value[k] !== '').length
})

const comboTagline = computed(() => {
  if (comboStreak.value >= 10) return '独步天下，无人能挡！⚡'
  if (comboStreak.value >= 5) return '势如破竹！超常发挥！🚀'
  if (comboStreak.value >= 3) return '手感火热！保持节奏！✨'
  return '渐入佳境！'
})

const formattedTimer = computed(() => {
  const sec = mode.value === 'EXAM' ? remainingSeconds.value : elapsedSeconds.value
  return formatSeconds(sec)
})

const formattedOptions = computed(() => {
  if (!currentQuestion.value) return []
  const opts = currentQuestion.value.options || []
  if (opts.length === 0 && currentQuestion.value.type === 'JUDGE') {
    return [
      { key: 'T', text: '正确 (True)' },
      { key: 'F', text: '错误 (False)' }
    ]
  }

  const defaultKeys = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
  return opts.map((opt, idx) => {
    if (typeof opt === 'object' && opt !== null) {
      return {
        key: opt.key || defaultKeys[idx] || String(idx + 1),
        text: opt.value || opt.text || JSON.stringify(opt)
      }
    }
    // String option like "A. xxx" or "xxx"
    const strOpt = String(opt)
    const match = strOpt.match(/^([A-Za-z0-9])[\.、\s]\s*(.*)$/)
    if (match) {
      return { key: match[1].toUpperCase(), text: match[2] }
    }
    return { key: defaultKeys[idx] || String(idx + 1), text: strOpt }
  })
})

const currentTutorContext = computed(() => {
  if (!currentQuestion.value) return {}
  const q = currentQuestion.value
  const res = currentResult.value
  return {
    stem: q.stem,
    options: formattedOptions.value.map(o => `${o.key}. ${o.text}`),
    user_answer: currentAnswer.value,
    correct_answer: res ? res.correct_answer : q.answer,
    official_explanation: res ? res.explanation : q.explanation,
    mistake_cause: selectedCauses.value[q.id] || ''
  }
})

// Lifecycle
onMounted(async () => {
  await loadSessionData()
  startTimer()
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
  if (comboTimer) clearTimeout(comboTimer)
  // Flush draft on leave
  flushSync()
})

// Multi selection sync helper
function syncMultiSelectionForCurrent() {
  const q = currentQuestion.value
  if (q && q.type === 'MULTI') {
    const existing = answers.value[q.id]
    if (Array.isArray(existing)) {
      currentMultiAnswers.value = [...existing].map(c => String(c).trim().toUpperCase()).filter(Boolean).sort()
    } else if (typeof existing === 'string') {
      currentMultiAnswers.value = existing.trim().toUpperCase().split('').filter(Boolean).sort()
    } else {
      currentMultiAnswers.value = []
    }
  } else {
    currentMultiAnswers.value = []
  }
}

// Watch question switch to reset multi selection
watch(currentQuestionIndex, () => {
  syncMultiSelectionForCurrent()
})

// Methods
function formatSeconds(sec) {
  const s = Math.max(0, Math.floor(sec || 0))
  const m = Math.floor(s / 60)
  const remaining = s % 60
  const h = Math.floor(m / 60)
  if (h > 0) {
    const mm = m % 60
    return `${h}:${String(mm).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
}

function typeLabel(type) {
  const map = {
    SINGLE: '单选题',
    MULTI: '多选题',
    JUDGE: '判断题',
    JUDGMENT: '判断题',
    ESSAY: '问答题'
  }
  return map[type] || '题目'
}

function startTimer() {
  timerInterval = setInterval(() => {
    elapsedSeconds.value += 1
    if (mode.value === 'EXAM') {
      if (remainingSeconds.value > 0) {
        remainingSeconds.value -= 1
        if (remainingSeconds.value === 0) {
          confirmSubmitSession(true)
        }
      }
    }
  }, 1000)
}

async function loadSessionData() {
  loading.value = true
  try {
    // 1. Fetch bank questions
    let allQuestions = []
    const qRes = await fetch(`/api/banks/${props.bankId}/questions`)
    if (qRes.ok) {
      allQuestions = await qRes.json()
      questions.value = allQuestions
    }

    // 2. Fetch remote session state
    const sRes = await fetch(`/api/sessions/${props.sessionId}`)
    if (sRes.ok) {
      const sData = await sRes.json()
      mode.value = sData.mode || props.initialMode
      // Filter and sort questions by session.question_ids if present
      if (sData.question_ids && Array.isArray(sData.question_ids) && sData.question_ids.length > 0) {
        const qMap = new Map(allQuestions.map(q => [q.id, q]))
        const ordered = sData.question_ids.map(id => qMap.get(id)).filter(Boolean)
        if (ordered.length > 0) {
          questions.value = ordered
        }
      }
      if (sData.answers) answers.value = sData.answers
      if (sData.flags) flags.value = sData.flags
      if (sData.time_spent) elapsedSeconds.value = sData.time_spent
      if (sData.is_completed) isCompleted.value = true
    }

    // 3. Load & merge zero-loss localStorage draft
    const draft = loadLocal()
    if (draft) {
      if (draft.answers) {
        answers.value = { ...answers.value, ...draft.answers }
      }
      if (draft.flags) {
        flags.value = draft.flags
      }
      if (typeof draft.currentIndex === 'number' && draft.currentIndex < questions.value.length) {
        currentQuestionIndex.value = draft.currentIndex
      }
    }

    // Ensure array multi-select answers are sorted and joined into uppercase strings during draft recovery
    const normalized = { ...answers.value }
    for (const [qId, ansVal] of Object.entries(normalized)) {
      if (Array.isArray(ansVal)) {
        normalized[qId] = ansVal
          .map(c => String(c).trim().toUpperCase())
          .filter(Boolean)
          .sort()
          .join('')
      } else if (typeof ansVal === 'string') {
        normalized[qId] = ansVal.trim().toUpperCase()
      }
    }
    answers.value = normalized

    // Sync multi-select state for the initial question if applicable
    syncMultiSelectionForCurrent()

    // If practice mode and answers exist, populate results locally
    if (mode.value === 'PRACTICE') {
      for (const q of questions.value) {
        if (answers.value[q.id] !== undefined) {
          // If question has standard answer, reconstruct result
          const uAns = String(answers.value[q.id]).trim().toUpperCase()
          const cAns = String(q.answer).trim().toUpperCase()
          results.value[q.id] = {
            is_correct: uAns === cAns,
            correct_answer: q.answer,
            explanation: q.explanation
          }
        }
      }
    }
  } catch (err) {
    console.warn('Failed loading session data:', err)
  } finally {
    loading.value = false
  }
}

function handleSelectOption(key) {
  const q = currentQuestion.value
  if (!q) return

  if (q.type === 'MULTI') {
    // Toggle multi selection
    const idx = currentMultiAnswers.value.indexOf(key)
    if (idx >= 0) {
      currentMultiAnswers.value.splice(idx, 1)
    } else {
      currentMultiAnswers.value.push(key)
      currentMultiAnswers.value.sort()
    }
    return
  }

  // SINGLE / JUDGE
  if (mode.value === 'EXAM') {
    // In Exam mode: save selection, no instant feedback
    answers.value[q.id] = key
    persistDraft()
    return
  }

  // PRACTICE mode: Instant Answer & Feedback
  submitAnswerToBackend(q.id, key)
}

function submitMultiAnswer() {
  const q = currentQuestion.value
  if (!q || !currentMultiAnswers.value.length) return

  const sortedAnswers = [...currentMultiAnswers.value].map(c => String(c).trim().toUpperCase()).filter(Boolean).sort()
  const answerVal = sortedAnswers.join('')
  answers.value[q.id] = answerVal

  if (mode.value === 'EXAM') {
    persistDraft()
  } else {
    submitAnswerToBackend(q.id, answerVal)
  }
}

async function submitAnswerToBackend(questionId, userAnswer) {
  answers.value[questionId] = userAnswer
  persistDraft()

  try {
    const res = await fetch(`/api/sessions/${props.sessionId}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question_id: questionId,
        user_answer: userAnswer,
        time_spent_delta: 2
      })
    })

    if (res.ok) {
      const data = await res.json()
      results.value[questionId] = {
        is_correct: data.is_correct,
        correct_answer: data.correct_answer,
        explanation: data.explanation
      }

      // Combo streak logic
      if (data.is_correct) {
        comboStreak.value += 1
        showCombo.value = true
        if (comboTimer) clearTimeout(comboTimer)
        comboTimer = setTimeout(() => {
          showCombo.value = false
        }, 2200)

        // Auto jump next if option enabled
        if (autoJumpNext.value && currentQuestionIndex.value < questions.value.length - 1) {
          setTimeout(() => {
            goNext()
          }, 650)
        }
      } else {
        comboStreak.value = 0
        showCombo.value = false
      }
    }
  } catch (err) {
    console.warn('Submit answer failed:', err)
  }
}

async function handleSelectCause(causeKey) {
  const q = currentQuestion.value
  if (!q) return
  selectedCauses.value[q.id] = causeKey

  try {
    await fetch(`/api/sessions/${props.sessionId}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question_id: q.id,
        user_answer: answers.value[q.id],
        mistake_cause: causeKey
      })
    })
  } catch (err) {
    console.warn('Tag mistake cause failed:', err)
  }
}

async function toggleFlag() {
  const q = currentQuestion.value
  if (!q) return

  const idx = flags.value.indexOf(q.id)
  if (idx >= 0) {
    flags.value.splice(idx, 1)
  } else {
    flags.value.push(q.id)
  }

  persistDraft()

  try {
    await fetch(`/api/sessions/${props.sessionId}/toggle-flag`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_id: q.id })
    })
  } catch (err) {
    console.warn('Toggle flag remote failed:', err)
  }
}

function persistDraft(immediate = false) {
  queueSync(
    {
      currentIndex: currentQuestionIndex.value,
      answers: answers.value,
      flags: flags.value,
      time_spent: elapsedSeconds.value
    },
    immediate
  )
}

function goPrev() {
  if (currentQuestionIndex.value > 0) {
    currentQuestionIndex.value -= 1
    persistDraft(true)
  }
}

function goNext() {
  if (currentQuestionIndex.value < questions.value.length - 1) {
    currentQuestionIndex.value += 1
    persistDraft(true)
  }
}

function handleJumpToQuestion(index) {
  if (index >= 0 && index < questions.value.length) {
    currentQuestionIndex.value = index
    persistDraft(true)
  }
}

function getOptionClass(key) {
  const q = currentQuestion.value
  if (!q) return ''
  const qId = q.id
  const result = results.value[qId]
  const userAns = answers.value[qId]

  if (q.type === 'MULTI') {
    if (result) {
      const correctSet = new Set(String(result.correct_answer).toUpperCase().split(''))
      const isSelected = currentMultiAnswers.value.includes(key)
      if (isSelected && correctSet.has(key)) return 'opt-correct'
      if (isSelected && !correctSet.has(key)) return 'opt-wrong'
      if (!isSelected && correctSet.has(key)) return 'opt-correct-missed'
    } else {
      if (currentMultiAnswers.value.includes(key)) return 'opt-selected'
    }
    return ''
  }

  // Single / Judge
  if (mode.value === 'EXAM') {
    if (userAns === key) return 'opt-selected'
    return ''
  }

  // Practice mode
  if (result) {
    const isUserChoice = userAns === key || String(userAns).toUpperCase() === key
    const isCorrectKey = result.correct_answer === key || String(result.correct_answer).toUpperCase() === key
    if (isUserChoice && result.is_correct) return 'opt-correct'
    if (isUserChoice && !result.is_correct) return 'opt-wrong'
    if (isCorrectKey) return 'opt-correct'
  } else if (userAns === key) {
    return 'opt-selected'
  }

  return ''
}

function getOptionIcon(key) {
  const q = currentQuestion.value
  if (!q) return null
  const result = results.value[q.id]
  if (!result) return null

  const userAns = answers.value[q.id]
  const isUserChoice = (q.type === 'MULTI')
    ? (Array.isArray(userAns) ? userAns.includes(key) : String(userAns || '').toUpperCase().includes(key))
    : (userAns === key)
  const isCorrectChoice = result.correct_answer === key || (q.type === 'MULTI' && String(result.correct_answer).toUpperCase().includes(key))

  if (isUserChoice && result.is_correct) return '✓'
  if (isUserChoice && !result.is_correct) return '✕'
  if (!isUserChoice && isCorrectChoice) return '★'
  return null
}

function isOptionDisabled(key) {
  const q = currentQuestion.value
  if (!q) return false
  if (mode.value === 'PRACTICE' && results.value[q.id]) {
    return true
  }
  return false
}

async function confirmSubmitSession(force = false) {
  if (!force) {
    const unans = questions.value.length - answeredCount.value
    let msg = '确定交卷并结束本次作答吗？'
    if (unans > 0) {
      msg = `还有 ${unans} 题未作答，确定现在交卷吗？`
    }
    if (!window.confirm(msg)) return
  }

  try {
    const res = await fetch(`/api/sessions/${props.sessionId}/complete`, {
      method: 'POST'
    })
    if (res.ok) {
      report.value = await res.json()
      isCompleted.value = true
      isAnswerDrawerOpen.value = false
      clearLocal()
      emit('session-completed', report.value)
    }
  } catch (err) {
    console.warn('Complete session failed:', err)
  }
}

function handleReviewWrongQuestions() {
  isCompleted.value = false
  mode.value = 'PRACTICE'
  // Jump to first wrong question
  const wrongIdx = questions.value.findIndex(q => {
    const r = results.value[q.id]
    return r && !r.is_correct
  })
  if (wrongIdx >= 0) {
    currentQuestionIndex.value = wrongIdx
  }
}

function handleBack() {
  persistDraft(true)
  emit('back')
}
</script>

<style scoped>
.practice-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 768px;
  margin: 0 auto;
  width: 100%;
  background-color: var(--bg-card);
  position: relative;
}

/* Top Nav */
.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background-color: #ffffff;
  border-bottom: 1px solid var(--border);
  z-index: 10;
}

.nav-back-btn {
  display: flex;
  align-items: center;
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--text-main);
  padding: 4px 8px;
  border-radius: 8px;
}
.nav-back-btn:hover {
  background-color: #f1f5f9;
}
.back-arrow {
  font-size: 1.5rem;
  line-height: 1;
  margin-right: 2px;
}

.nav-center {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
}
.badge-practice {
  background-color: var(--primary-light);
  color: var(--primary);
}
.badge-exam {
  background-color: #fef3c7;
  color: #b45309;
}
.badge-elimination {
  background-color: var(--danger-light);
  color: var(--danger);
}

.progress-indicator {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-main);
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.timer-display {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-muted);
  background-color: #f1f5f9;
  padding: 4px 8px;
  border-radius: 6px;
  font-variant-numeric: tabular-nums;
}
.timer-warning {
  background-color: var(--danger-light);
  color: var(--danger);
  animation: pulse-ring 1.5s infinite;
}

.btn-flag {
  font-size: 1.25rem;
  color: #cbd5e1;
  line-height: 1;
  padding: 4px;
  transition: transform 0.15s;
}
.btn-flag.is-flagged {
  color: var(--warning);
  transform: scale(1.15);
}

.btn-sheet {
  font-size: 1.125rem;
  color: var(--text-main);
  background-color: #f1f5f9;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Combo Banner */
.combo-banner {
  background: linear-gradient(135deg, #f59e0b, #ef4444);
  color: #ffffff;
  padding: 8px 16px;
  text-align: center;
  font-weight: 700;
  font-size: 0.9375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  box-shadow: 0 4px 6px rgba(239, 68, 68, 0.25);
  z-index: 20;
}

/* Sub-bar */
.sub-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 16px;
  background-color: #f8fafc;
  border-bottom: 1px solid var(--border);
  font-size: 0.75rem;
}

.draft-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
}
.dot-sync {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.sync-saving { background-color: var(--warning); animation: pulse-ring 1s infinite; }
.sync-synced { background-color: var(--success); }
.sync-error { background-color: var(--danger); }
.sync-idle { background-color: #cbd5e1; }

.auto-jump-toggle {
  display: flex;
  align-items: center;
}
.toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--text-muted);
}
.toggle-checkbox {
  cursor: pointer;
}

.btn-quick-submit {
  padding: 2px 10px;
  background-color: var(--primary);
  color: #ffffff;
  border-radius: 6px;
  font-weight: 600;
}

/* Main Swipe Area */
.question-main {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.question-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.question-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qtype-tag {
  background-color: var(--primary-light);
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.difficulty-stars {
  color: #f59e0b;
  font-size: 0.8125rem;
  letter-spacing: 1px;
}
.meta-tag {
  background-color: #f1f5f9;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
}

.question-stem {
  font-size: 1.125rem;
  font-weight: 600;
  line-height: 1.6;
  color: var(--text-main);
  user-select: text;
}

/* Options */
.options-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  background-color: #ffffff;
  text-align: left;
  transition: all 0.15s ease;
  min-height: 52px;
}
.option-item:hover:not(:disabled) {
  border-color: #94a3b8;
  background-color: #f8fafc;
}
.option-item:active:not(:disabled) {
  transform: scale(0.99);
}

.option-key-badge {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: #f1f5f9;
  color: var(--text-main);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.875rem;
  flex-shrink: 0;
}

.option-text {
  flex: 1;
  font-size: 0.9375rem;
  line-height: 1.45;
  color: var(--text-main);
  user-select: text;
}

.option-feedback-icon {
  width: 24px;
  text-align: center;
  font-weight: bold;
}

/* Option States */
.opt-selected {
  border-color: var(--primary) !important;
  background-color: var(--primary-light) !important;
}
.opt-selected .option-key-badge {
  background-color: var(--primary);
  color: #ffffff;
}

.opt-correct {
  border-color: var(--success) !important;
  background-color: var(--success-light) !important;
}
.opt-correct .option-key-badge {
  background-color: var(--success);
  color: #ffffff;
}
.opt-correct .feedback-icon {
  color: var(--success);
  font-size: 1.25rem;
}

.opt-correct-missed {
  border-color: var(--success) !important;
  border-style: dashed !important;
  background-color: var(--success-light) !important;
}

.opt-wrong {
  border-color: var(--danger) !important;
  background-color: var(--danger-light) !important;
}
.opt-wrong .option-key-badge {
  background-color: var(--danger);
  color: #ffffff;
}
.opt-wrong .feedback-icon {
  color: var(--danger);
  font-size: 1.25rem;
}

.multi-confirm-bar {
  margin-top: 4px;
}
.btn-multi-submit {
  width: 100%;
  padding: 12px;
  background-color: var(--primary);
  color: #ffffff;
  border-radius: 10px;
  font-weight: 600;
}
.btn-multi-submit:disabled {
  background-color: #cbd5e1;
  cursor: not-allowed;
}

/* Explanation Card */
.explanation-card {
  margin-top: 8px;
  background-color: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 1rem;
}
.res-correct {
  color: var(--success);
}
.res-wrong {
  color: var(--danger);
}
.res-status-icon {
  font-size: 1.25rem;
}
.res-answers-text {
  margin-left: auto;
  font-size: 0.875rem;
  color: var(--text-main);
}

.mistake-cause-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cause-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-muted);
}
.cause-capsules {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cause-capsule {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background-color: #ffffff;
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 0.75rem;
  transition: all 0.15s ease;
}
.cause-capsule:hover {
  border-color: var(--warning);
}
.cause-active {
  background-color: var(--warning-light);
  border-color: var(--warning);
  color: #b45309;
  font-weight: 600;
}

.official-explanation {
  background-color: #ffffff;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
}
.explanation-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 6px;
}
.explanation-content {
  font-size: 0.875rem;
  line-height: 1.6;
  color: #334155;
  white-space: pre-wrap;
  user-select: text;
}

.tutor-trigger-bar {
  display: flex;
}
.btn-ask-tutor {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9375rem;
  box-shadow: 0 4px 8px rgba(37, 99, 235, 0.2);
  transition: opacity 0.2s;
}
.btn-ask-tutor:active {
  opacity: 0.9;
}
.tutor-emoji {
  font-size: 1.25rem;
}

/* Bottom Bar */
.bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background-color: #ffffff;
  border-top: 1px solid var(--border);
  gap: 12px;
}

.nav-step-btn {
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 0.9375rem;
  font-weight: 600;
  background-color: #f1f5f9;
  color: var(--text-main);
}
.nav-step-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-primary-step {
  background-color: var(--primary-light);
  color: var(--primary);
}

.btn-finish-step {
  background-color: var(--primary);
  color: #ffffff;
}

.sheet-toggle-btn {
  flex: 1;
  text-align: center;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-muted);
  padding: 10px;
  border-radius: 8px;
  background-color: #f8fafc;
}

/* Modal Report */
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(4px);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.report-card {
  background-color: #ffffff;
  border-radius: 20px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  box-shadow: var(--shadow-lg);
}

.report-header {
  text-align: center;
  padding: 16px 0;
  border-radius: 12px;
}
.report-passed {
  background-color: var(--success-light);
  color: var(--success);
}
.report-failed {
  background-color: #fef2f2;
  color: var(--danger);
}
.report-trophy {
  font-size: 3rem;
  margin-bottom: 6px;
}
.report-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin-bottom: 4px;
}
.report-subtitle {
  font-size: 0.9375rem;
  color: var(--text-main);
}
.report-score-num {
  font-size: 1.5rem;
  color: var(--primary);
}

.report-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  background-color: #f8fafc;
  padding: 12px;
  border-radius: 12px;
}
.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.stat-val {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-main);
  margin-top: 2px;
}

.report-breakdown {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.breakdown-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-main);
}
.breakdown-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}
.breakdown-table th, .breakdown-table td {
  padding: 8px;
  text-align: center;
  border-bottom: 1px solid var(--border);
}
.breakdown-table th {
  background-color: #f1f5f9;
  color: var(--text-muted);
  font-weight: 600;
}

.report-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.btn-review-wrong {
  width: 100%;
  padding: 12px;
  background-color: var(--primary-light);
  color: var(--primary);
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9375rem;
}
.btn-finish-all {
  width: 100%;
  padding: 12px;
  background-color: var(--primary);
  color: #ffffff;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9375rem;
}

.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  color: var(--text-muted);
  gap: 12px;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e2e8f0;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
