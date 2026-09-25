<template>
  <main class="practice-page">
    <header class="page-header">
      <button type="button" @click="$emit('back')">返回</button>
      <div>
        <h1>{{ session?.mode === 'ELIMINATION' ? '斩杀查漏补缺' : session?.mode === 'FSRS' ? 'FSRS 复习' : '练习刷题' }}</h1>
        <small v-if="question">{{ index + 1 }} / {{ questions.length }} · {{ formatType(question.type) }}</small>
      </div>
      <div class="header-actions">
        <button type="button" class="btn-flag" :class="{ active: isWeak }" @click="toggleWeak">
          {{ isWeak ? '已标薄弱' : '标记薄弱' }}
        </button>
        <button type="button" class="btn-kill" @click="handleKill">
          斩杀此题
        </button>
        <button type="button" class="btn-edit-question" @click="toggleEditQuestion">
          {{ isEditingQuestion ? '取消编辑' : '编辑题目' }}
        </button>
        <button type="button" class="primary" @click="complete">交卷</button>
      </div>
    </header>

    <p v-if="loading">正在加载题目…</p>
    <section v-else-if="question" class="question-card">
      <!-- 离线暂存提示 -->
      <div v-if="offlineNotice" class="offline-banner" data-testid="offline-banner">
        <span>{{ offlineNotice }}</span>
        <button type="button" class="btn-sync-offline" @click="syncOfflineEdits">重试重放同步</button>
      </div>

      <!-- 题目编辑面板 -->
      <div v-if="isEditingQuestion" class="question-edit-panel" data-testid="question-edit-panel">
        <h3>编辑题目 (基于版本 v{{ question.version_number }})</h3>
        <label>题干：<input v-model="editStem" class="input-edit-stem" /></label>
        <label>解析：<input v-model="editExplanation" class="input-edit-exp" /></label>
        <div class="edit-actions">
          <button type="button" @click="isEditingQuestion = false">取消</button>
          <button type="button" class="primary btn-save-question-edit" @click="saveQuestionEdit">保存修改</button>
        </div>
      </div>

      <!-- 多端并发修改冲突保留与选择横幅 (基于服务端真实冲突检测) -->
      <div v-if="activeConflict || conflictResolvedMessage" class="conflict-banner" data-testid="conflict-banner">
        <div v-if="activeConflict" class="conflict-header">
          <span class="conflict-badge">⚠️ 检测到多端并发编辑冲突：您基于版本 v{{ activeConflict.base_version_number }} 的修改与服务端最新版本 v{{ activeConflict.server_version_number }} 发生冲突（双方版本均已完整保留在历史中）</span>
          <button type="button" class="btn-conflict-toggle" @click="showConflictModal = !showConflictModal">
            {{ showConflictModal ? '收起冲突比对' : '比对并选择最终采用版本' }}
          </button>
        </div>
        <p v-if="conflictResolvedMessage" class="conflict-resolved-msg">{{ conflictResolvedMessage }}</p>

        <div v-if="showConflictModal" class="conflict-list" data-testid="conflict-list">
          <div
            v-for="v in questionVersions"
            :key="v.id"
            class="conflict-version-item"
            :class="{ active: v.version_number === question.version_number }"
            :data-testid="`conflict-version-${v.version_number}`"
          >
            <div class="conflict-version-meta">
              <strong>版本 v{{ v.version_number }}</strong>
              <small>{{ v.created_at ? v.created_at.slice(0, 19).replace('T', ' ') : '' }}</small>
              <span v-if="v.version_number === question.version_number" class="badge-current">当前生效</span>
            </div>
            <div class="conflict-version-body">
              <p><strong>题干：</strong>{{ v.stem }}</p>
              <p><strong>答案：</strong>{{ v.answer }}</p>
              <p v-if="v.explanation"><strong>解析：</strong>{{ v.explanation }}</p>
            </div>
            <div class="conflict-version-actions">
              <button
                type="button"
                class="btn-adopt-version primary"
                :disabled="!activeConflict && v.version_number === question.version_number"
                @click="handleAdoptQuestionVersion(v)"
              >
                {{ !activeConflict && v.version_number === question.version_number ? '当前已是此版本' : `采用此版本 (v${v.version_number})` }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="stem-box">
        <h2>{{ question.stem }}</h2>
      </div>

      <!-- 客观选择题 -->
      <div v-if="question.options?.length" class="options-group">
        <label
          v-for="option in question.options"
          :key="option.key"
          class="option"
          :class="{ selected: isOptionSelected(option.key) }"
          @click.prevent="selectOption(option.key)"
        >
          <input
            :type="question.type === 'MULTI' ? 'checkbox' : 'radio'"
            :name="`practice-${question.id}`"
            :value="option.key"
            :checked="isOptionSelected(option.key)"
            :disabled="Boolean(result)"
          />
          <span>{{ option.key }}. {{ option.content }}</span>
        </label>
      </div>

      <!-- 主观题 / 填空题文本输入 -->
      <div v-else class="text-answer-box">
        <label>
          <span>作答内容</span>
          <textarea
            v-model="textAnswer"
            :disabled="Boolean(result)"
            rows="5"
            placeholder="输入你的答案或解题思路…"
          />
        </label>
      </div>

      <div class="submit-bar">
        <button v-if="!result" class="primary" :disabled="!hasAnswer" @click="submit">
          提交答案
        </button>
      </div>

      <!-- 判分结果卡片 -->
      <section v-if="result" class="result-card">
        <div class="result-header">
          <strong :class="result.correctness.toLowerCase()">
            {{ result.correctness === 'CORRECT' ? '完全正确' : result.correctness === 'PARTIAL' ? '部分得分' : result.is_objective ? '未完全答对' : '作答已保存（主观题）' }}
          </strong>
          <span v-if="result.is_objective">得分比例：{{ result.score_ratio }}</span>
        </div>

        <!-- FSRS 记忆评级交互区 (驱动下次复习时间) -->
        <div v-if="session?.mode === 'FSRS' || session?.mode === 'MISTAKE'" class="fsrs-rating-box">
          <h4>FSRS 记忆评级 (驱动下次复习时间)：</h4>
          <div class="fsrs-buttons">
            <button
              type="button"
              class="rating-btn again"
              :class="{ selected: selectedFsrsRating === 1 }"
              @click="submitRating(1)"
            >
              1 - 重来 (Again)
            </button>
            <button
              type="button"
              class="rating-btn hard"
              :disabled="result.correctness === 'INCORRECT'"
              :class="{ selected: selectedFsrsRating === 2 }"
              @click="submitRating(2)"
            >
              2 - 困难 (Hard)
            </button>
            <button
              type="button"
              class="rating-btn good"
              :disabled="result.correctness !== 'CORRECT'"
              :class="{ selected: selectedFsrsRating === 3 }"
              @click="submitRating(3)"
            >
              3 - 良好 (Good)
            </button>
            <button
              type="button"
              class="rating-btn easy"
              :disabled="result.correctness !== 'CORRECT'"
              :class="{ selected: selectedFsrsRating === 4 }"
              @click="submitRating(4)"
            >
              4 - 简单 (Easy)
            </button>
          </div>
          <p v-if="fsrsRatingStatus" class="fsrs-status">{{ fsrsRatingStatus }}</p>
        </div>

        <div v-if="question.explanation" class="official-explanation">
          <h4>官方解析</h4>
          <p>{{ question.explanation }}</p>
        </div>

        <div class="result-actions">
          <button type="button" @click="toggleAiPanel">
            {{ showAiPanel ? '收起助教' : 'AI 助教与解析' }}
          </button>
          <button type="button" class="primary" @click="next">
            {{ index < questions.length - 1 ? '下一题' : '已是最后一题' }}
          </button>
        </div>
      </section>

      <!-- AI 助教与多版本解释面板 -->
      <section v-if="showAiPanel" class="ai-panel">
        <div class="ai-toolbar">
          <h3>AI 助教与多版本解释</h3>
          <div class="ai-btn-group">
            <button type="button" :disabled="aiLoading" @click="generateExplanation">
              {{ aiLoading ? '正在分析…' : '重新生成 AI 解释' }}
            </button>
            <button type="button" :disabled="aiLoading" @click="handleVerifyWeb">
              {{ aiLoading ? '正在核查…' : '联网核查证据' }}
            </button>
          </div>
        </div>

        <!-- 自定义追问输入框 -->
        <div class="ai-ask-box">
          <input
            v-model="customQuery"
            type="text"
            placeholder="对这道题有疑问？输入追问内容，如：为什么选 B 不选 C…"
            @keyup.enter="askCustomQuery"
          />
          <button type="button" :disabled="!customQuery.trim() || aiLoading" @click="askCustomQuery">
            追问
          </button>
        </div>

        <p v-if="aiStatusMessage" class="ai-status">{{ aiStatusMessage }}</p>

        <!-- 连续追问对话历史 (MiaowTest 对话模型) -->
        <div v-if="chatMessages.length" class="ai-chat-thread">
          <h4>连续追问历史 ({{ chatMessages.length }})</h4>
          <div v-for="msg in chatMessages" :key="msg.id" class="chat-bubble" :class="msg.role">
            <div class="chat-sender">
              <strong>{{ msg.role === 'user' ? '我的追问' : 'AI 助教解答' }}</strong>
              <small class="muted">#{{ msg.sequence }}</small>
            </div>
            <p class="chat-text">{{ msg.content }}</p>
          </div>
        </div>

        <!-- 历史解释版本列表 -->
        <div v-if="answerVersions.length" class="ai-history">
          <h4>解释版本历史 ({{ answerVersions.length }})</h4>
          <article
            v-for="version in answerVersions"
            :key="version.id"
            class="version-card"
            :class="{ adopted: version.is_adopted }"
          >
            <div class="version-meta">
              <span class="source-tag">{{ formatSource(version.source) }}</span>
              <span v-if="version.is_adopted" class="badge-adopted">当前主解释</span>
              <small class="muted">{{ version.created_at ? version.created_at.slice(0, 19).replace('T', ' ') : '' }}</small>
            </div>

            <!-- 查看模式 -->
            <div v-if="editingVersionId !== version.id" class="version-content">
              <p class="content-text">{{ version.content }}</p>

              <!-- 联网证据展示 -->
              <div v-if="version.evidence?.length" class="evidence-box">
                <h5>联网检索证据依据 ({{ version.evidence.length }})</h5>
                <ul>
                  <li v-for="(ev, idx) in version.evidence" :key="idx">
                    <strong>{{ ev.title }}</strong>
                    <span v-if="ev.snippet"> - {{ ev.snippet }}</span>
                    <a v-if="ev.url" :href="ev.url" target="_blank" rel="noopener">来源链接</a>
                  </li>
                </ul>
              </div>

              <div class="version-actions">
                <button
                  v-if="!version.is_adopted"
                  type="button"
                  class="btn-adopt"
                  @click="adopt(version.id)"
                >采纳为主解释</button>
                <button
                  type="button"
                  @click="startEdit(version)"
                >编辑并存为个人解释</button>
              </div>
            </div>

            <!-- 编辑模式 -->
            <div v-else class="version-edit-box">
              <textarea v-model="editDraft" rows="4" />
              <div class="version-edit-actions">
                <button type="button" @click="editingVersionId = null">取消</button>
                <button type="button" class="primary" :disabled="!editDraft.trim()" @click="savePersonalExplanation">
                  保存为个人解释版本
                </button>
              </div>
            </div>
          </article>
        </div>
        <p v-else class="muted">暂无历史解释，点击上方按钮让 AI 展开剖析。</p>
      </section>
    </section>
    <p v-else>本题库暂无可练习题目。</p>
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getSession, getSessionQuestions, submitAttempt, completeSession } from '../api/practice'
import { getQuestion, listQuestionVersions, updateQuestion, getQuestionConflict, resolveQuestionConflict } from '../api/questions'
import { generateAnswer, listAnswerVersions, adoptAnswer, saveCandidate, verifyWeb, listQuestionConversations, listConversationMessages, sendChatMessage } from '../api/ai'
import { markWeak, unmarkWeak } from '../api/learning'
import { killQuestion } from '../api/kills'

const props = defineProps({ token: { type: String, required: true }, sessionId: { type: String, required: true } })
const emit = defineEmits(['back', 'completed'])

const session = ref(null)
const questions = ref([])
const index = ref(0)
const answer = ref([])
const textAnswer = ref('')
const result = ref(null)
const loading = ref(true)
const answerVersions = ref([])
const chatMessages = ref([])
const activeConversationId = ref(null)
const showAiPanel = ref(false)
const aiLoading = ref(false)
const aiStatusMessage = ref('')
const customQuery = ref('')
const editingVersionId = ref(null)
const editDraft = ref('')
const isWeak = ref(false)
const questionVersions = ref([])
const activeConflict = ref(null)
const showConflictModal = ref(false)
const conflictResolvedMessage = ref('')
const isEditingQuestion = ref(false)
const editStem = ref('')
const editExplanation = ref('')
const offlineNotice = ref('')

const question = computed(() => questions.value[index.value])

const hasAnswer = computed(() => {
  if (!question.value) return false
  if (question.value.options?.length) {
    return Array.isArray(answer.value) ? answer.value.length > 0 : Boolean(answer.value)
  }
  return textAnswer.value.trim().length > 0
})

function selectOption(key) {
  if (result.value) return
  if (question.value?.type === 'MULTI') {
    const list = Array.isArray(answer.value) ? [...answer.value] : []
    const idx = list.indexOf(key)
    if (idx >= 0) list.splice(idx, 1)
    else list.push(key)
    answer.value = list
  } else {
    answer.value = key
  }
}

function isOptionSelected(key) {
  if (question.value?.type === 'MULTI') {
    return Array.isArray(answer.value) && answer.value.includes(key)
  }
  return answer.value === key
}

function formatType(type) {
  const map = {
    SINGLE: '单选题',
    MULTI: '多选题',
    JUDGE: '判断题',
    FILL: '填空题',
    ESSAY: '主观题',
    SHORT_ANSWER: '简答题',
    SUBJECTIVE: '论述题',
  }
  return map[String(type || '').toUpperCase()] || String(type || '')
}

function formatSource(source) {
  const map = { AI: 'AI 助教生成', WEB: '联网核查', PERSONAL: '个人定制解释', OFFICIAL: '官方解析' }
  return map[source] || source
}

function normalizedAnswer() {
  if (question.value?.options?.length) {
    if (question.value?.type === 'MULTI') {
      const selected = Array.isArray(answer.value) ? answer.value : [answer.value]
      return [...selected].sort().join('')
    }
    return answer.value
  }
  return textAnswer.value.trim()
}

onMounted(async () => {
  window.addEventListener('online', syncOfflineEdits)
  try {
    session.value = await getSession(props.token, props.sessionId)
    questions.value = await getSessionQuestions(props.token, props.sessionId)
    await syncOfflineEdits()
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('online', syncOfflineEdits)
})

watch(question, async (current, prev) => {
  if (current) {
    const isDifferentQuestion = !prev || current.id !== prev.id
    if (isDifferentQuestion) {
      answer.value = current.type === 'MULTI' ? [] : ''
      textAnswer.value = ''
      result.value = null
      showConflictModal.value = false
      conflictResolvedMessage.value = ''
      isWeak.value = false
      customQuery.value = ''
      editingVersionId.value = null
      selectedFsrsRating.value = null
      fsrsRatingStatus.value = ''
    }
    answerVersions.value = await listAnswerVersions(props.token, current.id)
    try {
      questionVersions.value = await listQuestionVersions(props.token, current.id)
    } catch {
      questionVersions.value = []
    }
    try {
      const conf = await getQuestionConflict(props.token, current.id)
      activeConflict.value = conf?.has_conflict ? conf.conflict : null
    } catch {
      activeConflict.value = null
    }
    if (isDifferentQuestion) {
      try {
        const convs = await listQuestionConversations(props.token, current.id)
        if (convs?.length) {
          activeConversationId.value = convs[0].id
          chatMessages.value = await listConversationMessages(props.token, convs[0].id)
        } else {
          activeConversationId.value = null
          chatMessages.value = []
        }
      } catch {
        chatMessages.value = []
      }
    }
  }
}, { immediate: true })

const selectedFsrsRating = ref(null)
const fsrsRatingStatus = ref('')

async function submitRating(rating) {
  if (!question.value) return
  selectedFsrsRating.value = rating
  fsrsRatingStatus.value = '正在更新 FSRS 状态…'
  try {
    const res = await submitAttempt(props.token, props.sessionId, {
      question_id: question.value.id,
      user_answer: normalizedAnswer(),
      fsrs_rating: rating,
    })
    result.value = res
    fsrsRatingStatus.value = `已更新 FSRS 评级：${['', '重来(Again)', '困难(Hard)', '良好(Good)', '简单(Easy)'][rating]}，已计算下次复习时间`
  } catch (err) {
    fsrsRatingStatus.value = `评级失败：${err.detail || err.message}`
  }
}

async function submit() {
  if (!hasAnswer.value) return
  result.value = await submitAttempt(props.token, props.sessionId, {
    question_id: question.value.id,
    user_answer: normalizedAnswer(),
  })
  if (result.value?.correctness === 'INCORRECT' && (session.value?.mode === 'FSRS' || session.value?.mode === 'MISTAKE')) {
    selectedFsrsRating.value = 1
    fsrsRatingStatus.value = '答错已自动记录为 Again (重来)'
  }
}

function toggleAiPanel() {
  showAiPanel.value = !showAiPanel.value
}

async function generateExplanation() {
  if (!question.value) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const saved = await generateAnswer(props.token, question.value.id, { query: '请结合这道题详细解释解题思路与要点。' })
    answerVersions.value = [saved, ...answerVersions.value]
  } catch (err) {
    aiStatusMessage.value = `生成失败：${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function askCustomQuery() {
  if (!question.value || !customQuery.value.trim()) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const parentMsgId = chatMessages.value.length ? chatMessages.value[chatMessages.value.length - 1].id : null
    const res = await sendChatMessage(props.token, question.value.id, {
      content: customQuery.value.trim(),
      conversation_id: activeConversationId.value,
      parent_message_id: parentMsgId,
    })
    activeConversationId.value = res.conversation.id
    chatMessages.value.push(res.user_message)
    chatMessages.value.push(res.assistant_message)
    customQuery.value = ''
  } catch (err) {
    aiStatusMessage.value = `追问失败：${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function handleVerifyWeb() {
  if (!question.value) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const saved = await verifyWeb(props.token, question.value.id, { query: question.value.stem })
    answerVersions.value = [saved, ...answerVersions.value]
    if (saved.verification_status === 'UNAVAILABLE') {
      aiStatusMessage.value = '联网检索服务当前未配置或不可用，已保留离线空证据记录。'
    }
  } catch (err) {
    aiStatusMessage.value = `联网核查失败：${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function adopt(answerId) {
  const saved = await adoptAnswer(props.token, answerId)
  answerVersions.value = answerVersions.value.map(item =>
    item.question_id === saved.question_id ? { ...item, is_adopted: item.id === saved.id } : item
  )
}

function startEdit(version) {
  editingVersionId.value = version.id
  editDraft.value = version.content
}

async function savePersonalExplanation() {
  if (!question.value || !editDraft.value.trim()) return
  try {
    const saved = await saveCandidate(props.token, question.value.id, {
      content: editDraft.value.trim(),
      source: 'PERSONAL',
    })
    answerVersions.value = [saved, ...answerVersions.value]
    editingVersionId.value = null
  } catch (err) {
    alert(`保存失败：${err.detail || err.message}`)
  }
}

async function toggleWeak() {
  if (!question.value) return
  try {
    if (isWeak.value) {
      await unmarkWeak(props.token, question.value.id)
      isWeak.value = false
    } else {
      await markWeak(props.token, question.value.id)
      isWeak.value = true
    }
  } catch (err) {
    alert(`操作失败：${err.detail || err.message}`)
  }
}

async function handleKill() {
  if (!question.value) return
  try {
    await killQuestion(props.token, question.value.id)
    alert('已成功斩杀此题！此题将从普通刷题与错题队列移出，进入斩杀题库。')
    next()
  } catch (err) {
    alert(`斩杀失败：${err.detail || err.message}`)
  }
}

function next() {
  if (index.value < questions.value.length - 1) {
    index.value += 1
    answer.value = []
    textAnswer.value = ''
    result.value = null
    showAiPanel.value = false
  }
}

function toggleEditQuestion() {
  if (!question.value) return
  isEditingQuestion.value = !isEditingQuestion.value
  if (isEditingQuestion.value) {
    editStem.value = question.value.stem
    editExplanation.value = question.value.explanation || ''
  }
}

async function saveQuestionEdit() {
  if (!question.value || !editStem.value.trim()) return
  const payload = {
    stem: editStem.value.trim(),
    type: question.value.type || 'SINGLE',
    options: question.value.options || [],
    answer: question.value.answer || '',
    explanation: editExplanation.value.trim(),
    difficulty: question.value.difficulty ?? 3,
    tags: question.value.tags || [],
    base_version_number: question.value.version_number,
  }
  if (!window.navigator.onLine) {
    const queue = JSON.parse(localStorage.getItem('easyexam_offline_question_edits') || '[]')
    queue.push({ questionId: question.value.id, payload, queuedAt: Date.now() })
    localStorage.setItem('easyexam_offline_question_edits', JSON.stringify(queue))
    offlineNotice.value = '当前网络处于离线状态，修改已暂存本地队列，网络恢复后将自动重放同步至服务端。'
    isEditingQuestion.value = false
    return
  }
  try {
    const updated = await updateQuestion(props.token, question.value.id, payload)
    isEditingQuestion.value = false
    questions.value[index.value] = updated
    questionVersions.value = await listQuestionVersions(props.token, updated.id)
    const conf = await getQuestionConflict(props.token, updated.id)
    activeConflict.value = conf?.has_conflict ? conf.conflict : null
  } catch {
    const queue = JSON.parse(localStorage.getItem('easyexam_offline_question_edits') || '[]')
    queue.push({ questionId: question.value.id, payload, queuedAt: Date.now() })
    localStorage.setItem('easyexam_offline_question_edits', JSON.stringify(queue))
    offlineNotice.value = '连接服务端失败，修改已自动暂存本地队列，网络恢复后将自动重放同步至服务端。'
    isEditingQuestion.value = false
  }
}

let isSyncing = false
async function syncOfflineEdits() {
  if (isSyncing) return
  isSyncing = true
  try {
    const raw = localStorage.getItem('easyexam_offline_question_edits')
    if (!raw) return
    const queue = JSON.parse(raw)
    if (!queue.length) return
    localStorage.removeItem('easyexam_offline_question_edits')
    offlineNotice.value = '正在将离线修改重放至服务端…'
    const remaining = []
    for (const item of queue) {
      try {
        const updated = await updateQuestion(props.token, item.questionId, item.payload)
        if (question.value && question.value.id === item.questionId) {
          questions.value[index.value] = updated
          questionVersions.value = await listQuestionVersions(props.token, updated.id)
          const conf = await getQuestionConflict(props.token, updated.id)
          activeConflict.value = conf?.has_conflict ? conf.conflict : null
        }
      } catch {
        remaining.push(item)
      }
    }
    if (remaining.length) {
      localStorage.setItem('easyexam_offline_question_edits', JSON.stringify(remaining))
      offlineNotice.value = `仍有 ${remaining.length} 条离线修改重放失败`
    } else {
      offlineNotice.value = ''
    }
  } finally {
    isSyncing = false
  }
}

async function handleAdoptQuestionVersion(targetVer) {
  try {
    let updated
    if (activeConflict.value) {
      updated = await resolveQuestionConflict(props.token, question.value.id, targetVer.version_number)
      activeConflict.value = null
    } else {
      updated = await updateQuestion(props.token, question.value.id, {
        stem: targetVer.stem,
        type: targetVer.type || question.value.type || 'SINGLE',
        options: targetVer.options || question.value.options || [],
        answer: targetVer.answer || question.value.answer || '',
        explanation: targetVer.explanation || question.value.explanation || '',
        difficulty: targetVer.difficulty ?? question.value.difficulty ?? 3,
        tags: targetVer.tags || question.value.tags || [],
      })
    }
    conflictResolvedMessage.value = `已成功确认采用版本 v${targetVer.version_number} 内容，服务端已原子生成最新生效版本！`
    questions.value[index.value] = updated
    questionVersions.value = await listQuestionVersions(props.token, updated.id)
  } catch (err) {
    alert(`采用版本失败：${err.detail || err.message}`)
  }
}

async function complete() {
  const report = await completeSession(props.token, props.sessionId)
  window.alert(`本次练习结束！得分：${report.score}，正确率：${report.accuracy}%`)
  emit('completed', report)
  emit('back')
}
</script>

<style scoped>
.practice-page { width: min(100% - 2rem, 72rem); margin: 1.25rem auto; }
.header-actions { display: flex; gap: 0.5rem; align-items: center; }
.btn-flag.active { background: #fef08a; border-color: #eab308; color: #854d0e; }
.btn-kill { color: #dc2626; border-color: #fca5a5; }
.btn-kill:hover { background: #fee2e2; }
.question-card { padding: 1.5rem; border: 1px solid var(--border); border-radius: 1rem; background: var(--bg-card); box-shadow: var(--shadow-sm); }
.stem-box h2 { font-size: 1.25rem; margin-bottom: 1.25rem; white-space: pre-wrap; }
.options-group { display: grid; gap: 0.75rem; margin-bottom: 1.25rem; }
.option { display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.85rem; border: 1px solid var(--border); border-radius: 0.75rem; cursor: pointer; }
.text-answer-box textarea { width: 100%; padding: 0.75rem; border: 1px solid var(--border); border-radius: 0.75rem; resize: vertical; margin-top: 0.5rem; }
.submit-bar { margin: 1.25rem 0; }
.result-card { margin-top: 1.25rem; padding: 1.25rem; border-radius: 0.75rem; background: var(--bg-page); border: 1px solid var(--border); }
.result-header { display: flex; justify-content: space-between; font-size: 1.1rem; margin-bottom: 0.75rem; }
.result-header strong.correct { color: var(--success); }
.result-header strong.partial { color: #d97706; }
.result-header strong.incorrect { color: var(--danger); }
.official-explanation { margin: 1rem 0; padding: 0.75rem; background: var(--bg-card); border-radius: 0.5rem; border-left: 3px solid var(--primary); }
.result-actions { display: flex; justify-content: space-between; gap: 0.75rem; margin-top: 1rem; }
.fsrs-rating-box { margin: 1rem 0; padding: 0.85rem; background: var(--bg-card); border-radius: 0.5rem; border: 1px solid var(--border); }
.fsrs-rating-box h4 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.fsrs-buttons { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.rating-btn { padding: 0.4rem 0.75rem; border-radius: 0.375rem; border: 1px solid var(--border); cursor: pointer; font-size: 0.85rem; background: var(--bg-card); }
.rating-btn.again { color: #dc2626; border-color: #fca5a5; }
.rating-btn.hard { color: #d97706; border-color: #fcd34d; }
.rating-btn.good { color: #2563eb; border-color: #93c5fd; }
.rating-btn.easy { color: #16a34a; border-color: #86efac; }
.rating-btn.selected { font-weight: bold; box-shadow: 0 0 0 2px currentColor; }
.rating-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.fsrs-status { margin-top: 0.5rem; font-size: 0.85rem; color: var(--primary); }
.ai-panel { margin-top: 1.5rem; padding: 1.25rem; border: 1px dashed var(--primary); border-radius: 0.75rem; background: var(--bg-page); }
.ai-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
.ai-btn-group { display: flex; gap: 0.5rem; }
.ai-ask-box { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.ai-ask-box input { flex: 1; padding: 0.65rem; border: 1px solid var(--border); border-radius: 0.5rem; }
.ai-status { color: #d97706; font-size: 0.9rem; margin-bottom: 0.75rem; }
.ai-history { display: grid; gap: 0.75rem; margin-top: 1rem; }
.version-card { padding: 1rem; border: 1px solid var(--border); border-radius: 0.5rem; background: var(--bg-card); }
.version-card.adopted { border-color: var(--success); box-shadow: 0 0 0 1px var(--success); }
.version-meta { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
.source-tag { font-size: 0.8rem; font-weight: 600; padding: 0.15rem 0.4rem; background: var(--bg-page); border-radius: 0.25rem; }
.badge-adopted { font-size: 0.8rem; color: var(--success); font-weight: 700; }
.content-text { white-space: pre-wrap; line-height: 1.5; margin-bottom: 0.5rem; }
.evidence-box { margin: 0.5rem 0; padding: 0.5rem; background: var(--bg-page); border-radius: 0.35rem; font-size: 0.85rem; }
.evidence-box ul { margin-left: 1rem; }
.version-actions { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
.btn-adopt { color: var(--success); border-color: var(--success); }
.version-edit-box textarea { width: 100%; padding: 0.5rem; border: 1px solid var(--border); border-radius: 0.35rem; }
.version-edit-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.5rem; }
.ai-chat-thread { margin: 1rem 0; display: grid; gap: 0.75rem; }
.ai-chat-thread h4 { margin: 0; font-size: 0.95rem; }
.chat-bubble { padding: 0.75rem 1rem; border-radius: 0.75rem; border: 1px solid var(--border); background: var(--bg-card); }
.chat-bubble.user { background: #eff6ff; border-color: #bfdbfe; margin-left: 1.5rem; }
.chat-bubble.assistant { background: var(--bg-card); border-color: #cbd5e1; margin-right: 1.5rem; }
.chat-sender { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.35rem; font-weight: 600; }
.chat-text { margin: 0; white-space: pre-wrap; line-height: 1.5; font-size: 0.95rem; }
.conflict-banner { margin-bottom: 1.25rem; padding: 1rem; border: 1px solid #f59e0b; background: #fffbeb; border-radius: 0.75rem; }
.conflict-header { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.conflict-badge { font-weight: 600; color: #b45309; font-size: 0.95rem; }
.btn-conflict-toggle { padding: 0.35rem 0.75rem; border: 1px solid #d97706; background: #fef3c7; color: #92400e; border-radius: 0.375rem; cursor: pointer; font-size: 0.85rem; }
.conflict-resolved-msg { margin-top: 0.5rem; color: var(--success); font-weight: 600; font-size: 0.9rem; }
.conflict-list { display: grid; gap: 0.75rem; margin-top: 1rem; }
.conflict-version-item { padding: 0.85rem; border: 1px solid #e5e7eb; border-radius: 0.5rem; background: #ffffff; }
.conflict-version-item.active { border-color: #3b82f6; box-shadow: 0 0 0 1px #3b82f6; }
.conflict-version-meta { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.5rem; }
.badge-current { font-size: 0.75rem; background: #dbeafe; color: #1e40af; padding: 0.1rem 0.4rem; border-radius: 0.25rem; font-weight: 600; }
.conflict-version-body p { margin: 0.25rem 0; font-size: 0.9rem; }
.conflict-version-actions { margin-top: 0.5rem; display: flex; justify-content: flex-end; }
.btn-adopt-version { padding: 0.35rem 0.75rem; font-size: 0.85rem; }
.offline-banner { margin-bottom: 1rem; padding: 0.75rem 1rem; background: #fef2f2; border: 1px solid #f87171; border-radius: 0.5rem; color: #991b1b; display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; font-size: 0.9rem; }
.btn-sync-offline { padding: 0.3rem 0.65rem; border: 1px solid #dc2626; background: #fff; color: #dc2626; border-radius: 0.375rem; cursor: pointer; font-size: 0.85rem; }
.question-edit-panel { margin-bottom: 1.25rem; padding: 1.25rem; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 0.75rem; display: grid; gap: 0.75rem; }
.question-edit-panel h3 { margin: 0; font-size: 1.05rem; }
.question-edit-panel label { display: grid; gap: 0.35rem; font-weight: 600; font-size: 0.9rem; }
.input-edit-stem, .input-edit-exp { padding: 0.5rem; border: 1px solid var(--border); border-radius: 0.375rem; font-size: 0.95rem; }
.edit-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem; }
.btn-edit-question { border: 1px solid var(--border); background: var(--bg-card); cursor: pointer; }
</style>
