<template>
  <main class="mistakes-page">
    <header class="page-header">
      <button type="button" @click="$emit('back')">返回</button>
      <div>
        <h1>{{ currentTab === 'mistakes' ? '错题与 FSRS 复习' : '斩杀题库 (已消灭)' }}</h1>
        <p v-if="currentTab === 'mistakes'">
          {{ selectedBankName ? `【${selectedBankName}】` : '全部题库 · ' }}共 {{ filteredMistakes.length }} 道错题 · {{ filteredDueReviews.length }} 道到期待复习
        </p>
        <p v-else>
          {{ selectedBankName ? `【${selectedBankName}】` : '全部题库 · ' }}共 {{ filteredKilled.length }} 道已斩杀题目
        </p>
      </div>
      <nav class="view-tabs">
        <button type="button" :class="{ active: currentTab === 'mistakes' }" @click="switchTab('mistakes')">错题复习</button>
        <button type="button" :class="{ active: currentTab === 'kills' }" @click="switchTab('kills')">斩杀题库</button>
      </nav>
    </header>

    <div class="mistake-toolbar">
      <div class="bank-selector">
        <label for="bank-filter">题库筛选：</label>
        <select id="bank-filter" v-model="selectedBankId">
          <option value="">全部题库 (跨题库查看)</option>
          <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
        </select>
      </div>

      <template v-if="currentTab === 'mistakes'">
        <!-- 到期复习按钮组 -->
        <template v-if="!selectedBankId && dueReviewsByBank.length > 1">
          <button
            v-for="g in dueReviewsByBank"
            :key="'due-' + g.bank_id"
            type="button"
            class="primary btn-compact"
            :disabled="startingSession"
            @click="startDueFsrs(g)"
          >
            {{ startingSession ? '正在启动…' : `FSRS 到期 · ${g.bank_name} (${g.items.length})` }}
          </button>
        </template>
        <button
          v-else
          type="button"
          class="primary"
          :disabled="filteredDueReviews.length === 0 || startingSession"
          @click="startDueFsrs()"
        >
          {{ startingSession ? '正在启动…' : `FSRS 到期复习 (${filteredDueReviews.length})` }}
        </button>

        <!-- 错题专项按钮组 -->
        <template v-if="!selectedBankId && mistakesByBank.length > 1">
          <button
            v-for="g in mistakesByBank"
            :key="'mistake-' + g.bank_id"
            type="button"
            class="btn-compact"
            :disabled="startingSession"
            @click="startMistakesPractice(null, g)"
          >
            {{ startingSession ? '正在启动…' : `错题刷题 · ${g.bank_name} (${g.items.length})` }}
          </button>
        </template>
        <button
          v-else
          type="button"
          :disabled="filteredMistakes.length === 0 || startingSession"
          @click="startMistakesPractice()"
        >
          错题专项刷题 ({{ filteredMistakes.length }})
        </button>
      </template>

      <template v-else>
        <template v-if="!selectedBankId && killedByBank.length > 1">
          <button
            v-for="g in killedByBank"
            :key="'kill-' + g.bank_id"
            type="button"
            class="primary btn-compact"
            :disabled="startingSession"
            @click="startEliminationPractice(null, g)"
          >
            {{ startingSession ? '正在启动…' : `查漏补缺 · ${g.bank_name} (${g.items.length})` }}
          </button>
        </template>
        <button
          v-else
          type="button"
          class="primary"
          :disabled="filteredKilled.length === 0 || startingSession"
          @click="startEliminationPractice()"
        >
          {{ startingSession ? '正在启动…' : `开始查漏补缺 (${filteredKilled.length})` }}
        </button>
      </template>
    </div>

    <p v-if="loading">正在加载…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <!-- 错题与到期复习列表 -->
    <template v-else-if="currentTab === 'mistakes'">
      <!-- 到期卡片高亮区（若包含薄弱标记题） -->
      <section v-if="weakOnlyDueReviews.length > 0" class="due-section">
        <h3 class="section-title">📌 薄弱标记到期待复习 ({{ weakOnlyDueReviews.length }})</h3>
        <div class="bank-grid">
          <article v-for="item in weakOnlyDueReviews" :key="'weak-' + item.question_id" class="bank-card mistake-card due-highlight">
            <div class="card-meta">
              <span class="badge">{{ item.type }}</span>
              <span class="badge-bank">{{ getBankName(item.bank_id) }}</span>
              <span class="badge-due due">薄弱标记 · FSRS 到期</span>
            </div>
            <h2>{{ item.stem }}</h2>
            <div class="mistake-detail">
              <p>自主标记为薄弱题目 · 到期需巩固</p>
            </div>
            <div class="card-actions">
              <button type="button" class="primary" @click="startSingleFsrs(item)">复习此题</button>
              <button type="button" class="kill-btn" @click="handleKill(item.question_id)">斩杀此题</button>
            </div>
          </article>
        </div>
      </section>

      <section class="mistakes-section">
        <h3 v-if="weakOnlyDueReviews.length > 0" class="section-title">📝 错题记录 ({{ filteredMistakes.length }})</h3>
        <div class="bank-grid">
          <article v-for="item in filteredMistakes" :key="item.question_id" class="bank-card mistake-card">
            <div class="card-meta">
              <span class="badge">{{ item.type }}</span>
              <span class="badge-bank">{{ getBankName(item.bank_id) }}</span>
              <span class="badge-due" :class="{ due: item.is_due }">{{ item.is_due ? 'FSRS 到期' : '等待复习' }}</span>
            </div>
            <h2>{{ item.stem }}</h2>
            <div class="mistake-detail">
              <p>错误 {{ item.mistake_count }} 次 · 连续正确 {{ item.consecutive_correct || 0 }} 次</p>
              <label class="cause-label">
                <span>错因归因：</span>
                <select :value="item.mistake_cause || ''" @change="updateMistakeCause(item, $event.target.value)">
                  <option value="">未分类</option>
                  <option v-for="c in mistakeCauses" :key="c" :value="c">{{ c }}</option>
                </select>
              </label>
            </div>
            <div class="card-actions">
              <button type="button" @click="startMistakesPractice(item)">练习此题</button>
              <button v-if="item.is_due" type="button" class="primary" @click="startSingleFsrs(item)">到期复习</button>
              <button type="button" class="kill-btn" @click="handleKill(item.question_id)">斩杀此题</button>
            </div>
          </article>
        </div>
        <p v-if="!filteredMistakes.length && !weakOnlyDueReviews.length">暂无待复习错题，继续保持！</p>
      </section>
    </template>

    <!-- 斩杀题库列表 -->
    <section v-else class="bank-grid">
      <article v-for="item in filteredKilled" :key="item.question_id" class="bank-card killed-card">
        <div class="card-meta">
          <span class="badge">{{ item.type }}</span>
          <span class="badge-bank">{{ getBankName(item.bank_id) }}</span>
          <small class="muted">{{ item.killed_at ? `斩杀于 ${item.killed_at.slice(0, 10)}` : '已斩杀' }}</small>
        </div>
        <h2>{{ item.stem }}</h2>
        <div class="card-actions">
          <button type="button" @click="startEliminationPractice(item)">查漏补缺练习</button>
          <button type="button" @click="handleUnkill(item.question_id)">恢复 (解除斩杀)</button>
        </div>
      </article>
      <p v-if="!filteredKilled.length">暂无已斩杀题目。做熟的题目可主动斩杀归档。</p>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { listDueMistakes, listMistakes, updateMistakeCause as updateMistakeCauseApi } from '../api/mistakes'
import { listKills, killQuestion, unkillQuestion } from '../api/kills'
import { listBanks } from '../api/banks'
import { startSession } from '../api/practice'

const props = defineProps({ token: { type: String, required: true } })
const emit = defineEmits(['back', 'start-session'])

const currentTab = ref('mistakes')
const selectedBankId = ref('')
const banks = ref([])
const mistakes = ref([])
const dueReviews = ref([])
const killedList = ref([])
const loading = ref(true)
const error = ref('')
const startingSession = ref(false)

const mistakeCauses = [
  '审题遗漏',
  '概念欠缺',
  '思路不熟',
  '陷阱诱导',
  '计算错误',
  '其他手误',
]

const selectedBankName = computed(() => {
  if (!selectedBankId.value) return ''
  const b = banks.value.find(item => item.id === selectedBankId.value)
  return b ? b.name : ''
})

const filteredMistakes = computed(() => {
  if (!selectedBankId.value) return mistakes.value
  return mistakes.value.filter(m => m.bank_id === selectedBankId.value)
})

const filteredDueReviews = computed(() => {
  if (!selectedBankId.value) return dueReviews.value
  return dueReviews.value.filter(d => d.bank_id === selectedBankId.value)
})

const filteredKilled = computed(() => {
  if (!selectedBankId.value) return killedList.value
  return killedList.value.filter(k => k.bank_id === selectedBankId.value)
})

// 找出在 dueReviews 中但不在 mistakes 中的题目（即标记薄弱、无做错记录但到期的题目）
const weakOnlyDueReviews = computed(() => {
  const mistakeQidSet = new Set(filteredMistakes.value.map(m => m.question_id))
  return filteredDueReviews.value.filter(d => !mistakeQidSet.has(d.question_id))
})

const mistakesByBank = computed(() => {
  const map = {}
  for (const item of filteredMistakes.value) {
    const bid = item.bank_id || 'unknown'
    if (!map[bid]) map[bid] = { bank_id: bid, bank_name: getBankName(bid), items: [] }
    map[bid].items.push(item)
  }
  return Object.values(map)
})

const dueReviewsByBank = computed(() => {
  const map = {}
  for (const item of filteredDueReviews.value) {
    const bid = item.bank_id || 'unknown'
    if (!map[bid]) map[bid] = { bank_id: bid, bank_name: getBankName(bid), items: [] }
    map[bid].items.push(item)
  }
  return Object.values(map)
})

const killedByBank = computed(() => {
  const map = {}
  for (const item of filteredKilled.value) {
    const bid = item.bank_id || 'unknown'
    if (!map[bid]) map[bid] = { bank_id: bid, bank_name: getBankName(bid), items: [] }
    map[bid].items.push(item)
  }
  return Object.values(map)
})

function getBankName(bankId) {
  const b = banks.value.find(item => item.id === bankId)
  return b ? b.name : '未知题库'
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [fetchedBanks, fetchedDues, fetchedMistakes, fetchedKills] = await Promise.all([
      listBanks(props.token).catch(() => []),
      listDueMistakes(props.token).catch(() => []),
      listMistakes(props.token).catch(() => []),
      listKills(props.token).catch(() => []),
    ])
    banks.value = fetchedBanks || []
    dueReviews.value = fetchedDues || []
    mistakes.value = fetchedMistakes || []
    killedList.value = fetchedKills || []
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    loading.value = false
  }
}

function switchTab(tab) {
  currentTab.value = tab
  void loadData()
}

async function handleKill(questionId) {
  try {
    await killQuestion(props.token, questionId)
    mistakes.value = mistakes.value.filter(m => m.question_id !== questionId)
    dueReviews.value = dueReviews.value.filter(d => d.question_id !== questionId)
    void loadData()
  } catch (err) {
    alert(`斩杀失败：${err.detail || err.message}`)
  }
}

async function handleUnkill(questionId) {
  try {
    await unkillQuestion(props.token, questionId)
    killedList.value = killedList.value.filter(k => k.question_id !== questionId)
    void loadData()
  } catch (err) {
    alert(`恢复失败：${err.detail || err.message}`)
  }
}

async function updateMistakeCause(item, cause) {
  item.mistake_cause = cause
  try {
    await updateMistakeCauseApi(props.token, item.question_id, cause)
  } catch (err) {
    error.value = `更新错因失败：${err.detail || err.message}`
  }
}

async function startDueFsrs(group) {
  const items = group ? group.items : filteredDueReviews.value
  if (!items || items.length === 0) return
  const targetBankId = group ? group.bank_id : (selectedBankId.value || items[0]?.bank_id)
  if (!targetBankId) return

  const bankItems = items.filter(i => i.bank_id === targetBankId)
  if (bankItems.length === 0) return

  startingSession.value = true
  try {
    const questionIds = bankItems.map(m => m.question_id)
    const session = await startSession(props.token, {
      bank_id: targetBankId,
      mode: 'FSRS',
      question_ids: questionIds,
    })
    emit('start-session', session)
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    startingSession.value = false
  }
}

async function startSingleFsrs(item) {
  if (!item?.bank_id || !item?.question_id) return
  startingSession.value = true
  try {
    const session = await startSession(props.token, {
      bank_id: item.bank_id,
      mode: 'FSRS',
      question_ids: [item.question_id],
    })
    emit('start-session', session)
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    startingSession.value = false
  }
}

async function startMistakesPractice(record, group) {
  const items = group ? group.items : filteredMistakes.value
  if (!record && (!items || items.length === 0)) return
  const targetBankId = record?.bank_id || (group ? group.bank_id : (selectedBankId.value || items[0]?.bank_id))
  if (!targetBankId) return

  startingSession.value = true
  try {
    const bankItems = record ? [record] : items.filter(m => m.bank_id === targetBankId)
    const questionIds = bankItems.map(m => m.question_id)
    const session = await startSession(props.token, {
      bank_id: targetBankId,
      mode: 'MISTAKE',
      question_ids: questionIds,
    })
    emit('start-session', session)
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    startingSession.value = false
  }
}

async function startEliminationPractice(record, group) {
  const items = group ? group.items : filteredKilled.value
  if (!record && (!items || items.length === 0)) return
  const targetBankId = record?.bank_id || (group ? group.bank_id : (selectedBankId.value || items[0]?.bank_id))
  if (!targetBankId) {
    error.value = '未找到该题所属的题库信息，无法启动查漏补缺练习。'
    return
  }

  startingSession.value = true
  try {
    const bankItems = record ? [record] : items.filter(k => k.bank_id === targetBankId)
    const questionIds = bankItems.map(k => k.question_id)
    const session = await startSession(props.token, {
      bank_id: targetBankId,
      mode: 'ELIMINATION',
      question_ids: questionIds,
    })
    emit('start-session', session)
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    startingSession.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.mistakes-page {
  width: min(100% - 2rem, 76rem);
  margin: 1.5rem auto;
}

.view-tabs {
  display: flex;
  gap: 0.5rem;
}

.view-tabs button {
  padding: 0.5rem 1rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--bg-card);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.15s ease;
}

.view-tabs button.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
  box-shadow: var(--shadow-xs);
}

.mistake-toolbar {
  display: flex;
  gap: 0.75rem;
  margin: 1.25rem 0;
  flex-wrap: wrap;
  align-items: center;
  background: var(--bg-card);
  padding: 0.85rem 1.15rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
}

.bank-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.bank-selector select {
  padding: 0.45rem 0.75rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  font-size: 0.875rem;
}

.btn-compact {
  padding: 0.45rem 0.75rem;
  font-size: 0.85rem;
  white-space: nowrap;
}


.section-title {
  margin: 1.5rem 0 0.85rem;
  font-size: 1.15rem;
  color: var(--text-main);
  letter-spacing: -0.01em;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.65rem;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  background: var(--bg-muted);
  border: 1px solid var(--border);
  color: var(--text-main);
}

.badge-bank {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  background: #f1f5f9;
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.badge-due {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  background: var(--bg-muted);
  color: var(--text-muted);
}

.badge-due.due {
  background: var(--danger-light);
  color: var(--danger);
  border: 1px solid var(--danger-border);
  font-weight: 600;
}

.due-highlight {
  border-left: 4px solid var(--warning);
}

.mistake-detail {
  margin: 0.75rem 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.cause-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
}

.cause-label select {
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  font-size: 0.8125rem;
}

.card-actions {
  margin-top: 1rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.card-actions button {
  cursor: pointer;
}

.kill-btn {
  color: var(--danger);
  border-color: var(--danger-border);
}

.kill-btn:hover:not(:disabled) {
  background: var(--danger-light);
  border-color: var(--danger);
}

@media (max-width: 640px) {
  .mistakes-page {
    width: min(100% - 1rem, 76rem);
    margin: 0.75rem auto;
  }
  .mistake-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .bank-selector {
    width: 100%;
  }
  .bank-selector select {
    flex: 1;
  }
}
</style>
