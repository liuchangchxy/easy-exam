<template>
  <main class="learning-page">
    <header class="page-header learning-header">
      <div class="header-left">
        <button type="button" class="btn-back" @click="$emit('back')">← {{ t('common.back') }}</button>
        <div>
          <h1>{{ t('learning.title') }}</h1>
          <p>{{ t('learning.fsrs_stats') }}</p>
        </div>
      </div>
    </header>

    <p v-if="store.loading.value">正在计算学习趋势与诊断报告…</p>
    <p v-else-if="store.error.value" class="error">{{ store.error.value }}</p>

    <template v-else-if="store.trends.value">
      <!-- 概览指标行 -->
      <section class="metrics-grid">
        <article class="bank-card stat-box">
          <small>题库覆盖率</small>
          <strong>{{ store.trends.value.coverage_percent ?? 0 }}%</strong>
          <p>{{ store.trends.value.attempted_questions ?? 0 }} / {{ store.trends.value.total_questions ?? 0 }} 题已练习</p>
        </article>

        <article class="bank-card stat-box">
          <small>复习完成度</small>
          <strong>{{ store.trends.value.review_completion_rate ?? 100 }}%</strong>
          <p>已复习 {{ store.trends.value.reviews_completed ?? 0 }} 题 · 待复习 {{ store.trends.value.due_reviews ?? 0 }} 题</p>
        </article>

        <article class="bank-card stat-box">
          <small>近期平均正确率</small>
          <strong>{{ store.trends.value.recent?.correct_rate ?? 0 }}%</strong>
          <p>近 {{ store.trends.value.window_days ?? 7 }} 天作答 {{ store.trends.value.recent?.attempts ?? 0 }} 次</p>
        </article>

        <article class="bank-card stat-box">
          <small>近期单题平均耗时</small>
          <strong>{{ store.trends.value.recent?.avg_time_per_question ?? 0 }} 秒</strong>
          <p>累计用时 {{ Math.round((store.trends.value.recent?.time_spent || 0) / 60) }} 分钟</p>
        </article>
      </section>

      <!-- 近期表现 vs 长期基线对比卡片 -->
      <section class="bank-card comparison-section">
        <h2>近期表现 vs 长期历史基线</h2>
        <div class="comparison-grid">
          <div class="comp-col recent">
            <h3>近期窗口（近 {{ store.trends.value.window_days ?? 7 }} 天）</h3>
            <ul>
              <li><span>作答次数：</span><strong>{{ store.trends.value.recent?.attempts ?? 0 }} 次</strong></li>
              <li><span>正确率：</span><strong>{{ store.trends.value.recent?.correct_rate ?? 0 }}%</strong></li>
              <li><span>单题均耗时：</span><strong>{{ store.trends.value.recent?.avg_time_per_question ?? 0 }} 秒</strong></li>
              <li><span>练习题量：</span><strong>{{ store.trends.value.recent?.attempted_questions ?? 0 }} 题</strong></li>
            </ul>
          </div>
          <div class="comp-col baseline">
            <h3>长期历史基线（此前全部记录）</h3>
            <ul>
              <li><span>作答次数：</span><strong>{{ store.trends.value.baseline?.attempts ?? 0 }} 次</strong></li>
              <li><span>正确率：</span><strong>{{ store.trends.value.baseline?.correct_rate ?? 0 }}%</strong></li>
              <li><span>单题均耗时：</span><strong>{{ store.trends.value.baseline?.avg_time_per_question ?? 0 }} 秒</strong></li>
              <li><span>趋势状态：</span><strong :class="trendClass">{{ trendText || '数据积累中' }}</strong></li>
            </ul>
          </div>
        </div>
      </section>

      <!-- 薄弱知识点排行 -->
      <section v-if="store.trends.value.weak_points?.length" class="bank-card weak-section">
        <h2>薄弱知识点与高频错因排行</h2>
        <ul class="weak-list">
          <li v-for="(item, idx) in store.trends.value.weak_points" :key="idx" class="weak-item">
            <span class="rank-num">{{ idx + 1 }}</span>
            <span class="point-name">{{ item.name }}</span>
            <span class="mistake-count">累计错题/错误 {{ item.mistakes }} 次</span>
          </li>
        </ul>
      </section>

      <!-- 提分推荐（可调整参数） -->
      <section class="bank-card recommendations-section">
        <div class="rec-header">
          <h2>动态提分推荐</h2>
          <div class="rec-controls">
            <div class="rec-filter-groups">
              <div class="rec-switch-group">
                <label class="ctrl-check">
                  <input type="checkbox" v-model="filterNew" @change="applyFilters" />
                  <span>新题覆盖</span>
                </label>
                <label class="ctrl-check">
                  <input type="checkbox" v-model="filterWeak" @change="applyFilters" />
                  <span>薄弱强化</span>
                </label>
                <label class="ctrl-check">
                  <input type="checkbox" v-model="filterDue" @change="applyFilters" />
                  <span>到期复习</span>
                </label>
              </div>
              <div class="rec-select-group">
                <label class="ctrl-select bank-filter-ctrl">
                  <select id="select-rec-bank" v-model="selectedBankId" @change="onBankChange">
                    <option value="">全部题库</option>
                    <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
                  </select>
                </label>
                <label class="ctrl-select">
                  <select id="select-rec-type" v-model="filterType" @change="applyFilters">
                    <option value="">全部题型</option>
                    <option value="SINGLE">单选题</option>
                    <option value="MULTI">多选题</option>
                    <option value="JUDGE">判断题</option>
                    <option value="ESSAY">主观题</option>
                  </select>
                </label>
                <label class="ctrl-select">
                  <select id="select-rec-diff" v-model="filterDifficulty" @change="applyFilters">
                    <option value="">全部难度</option>
                    <option value="1">难度 1</option>
                    <option value="2">难度 2</option>
                    <option value="3">难度 3</option>
                    <option value="4">难度 4</option>
                    <option value="5">难度 5</option>
                  </select>
                </label>
                <label class="ctrl-select">
                  <select id="select-rec-ratio" v-model.number="filterNewRatio" @change="applyFilters">
                    <option :value="0.5">新题比 50%</option>
                    <option :value="0.3">新题比 30%</option>
                    <option :value="0.7">新题比 70%</option>
                    <option :value="1.0">纯新题 100%</option>
                    <option :value="0.0">纯复习 0%</option>
                  </select>
                </label>
              </div>
            </div>
            <div v-if="recsByBank.length" class="rec-actions">
              <button
                v-for="group in recsByBank"
                :key="group.bank_id"
                type="button"
                class="primary btn-start-rec"
                @click="startRecommendedPractice(group)"
              >
                {{ recsByBank.length > 1 ? `开始【${group.bank_name}】推荐刷题 (${group.items.length} 题)` : `开始推荐刷题 (${group.items.length} 题)` }}
              </button>
            </div>
          </div>
        </div>

        <ul v-if="store.recommendations.value?.length" class="rec-list">
          <li v-for="item in store.recommendations.value" :key="item.question_id" class="rec-item">
            <span class="rec-reason">{{ item.reason }}</span>
            <span v-if="!selectedBankId" class="badge-bank">{{ getBankName(item.bank_id) }}</span>
            <span class="rec-stem">{{ item.stem }}</span>
            <small class="muted">{{ item.type }}</small>
          </li>
        </ul>
        <p v-else class="muted">当前筛选条件下暂无推荐题目。</p>
      </section>

      <!-- 智能学习计划 -->
      <section class="bank-card plan-controls">
        <div class="plan-header-title">
          <div>
            <h2>智能学习计划定制</h2>
            <p class="plan-desc">根据遗忘曲线与薄弱图谱，科学平摊复习负荷，告别盲目刷题</p>
          </div>
          <div v-if="store.plan.value" class="plan-summary-badge">
            <span>总计 <strong>{{ store.plan.value.question_count || 0 }}</strong> 题</span>
            <span class="sep">·</span>
            <span>预计 <strong>{{ store.plan.value.planned_minutes || 0 }}</strong> 分钟</span>
            <span class="sep">·</span>
            <span>日均 <strong>{{ Math.round((store.plan.value.question_count || 0) / (days || 1)) }}</strong> 题</span>
          </div>
        </div>

        <div class="plan-form-grid">
          <label class="form-item">
            <span class="label-text">目标题库：</span>
            <select v-model="planBankId" @change="updatePlan">
              <option value="">全部已选关联题库</option>
              <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
            </select>
          </label>
          <label class="form-item">
            <span class="label-text">计划周期：</span>
            <select v-model.number="days" @change="updatePlan">
              <option :value="1">1 天冲刺（考前急救）</option>
              <option :value="3">3 天突击（周末攻坚）</option>
              <option :value="7">7 天巩固（单周闭环）</option>
              <option :value="14">14 天进阶（双周强化）</option>
              <option :value="21">21 天提升（习惯养成）</option>
              <option :value="30">30 天突破（全真覆盖）</option>
            </select>
          </label>
          <label class="form-item">
            <span class="label-text">每日时长：</span>
            <select v-model.number="minutesPerDay" @change="updatePlan">
              <option :value="15">15 分钟（碎片速刷）</option>
              <option :value="30">30 分钟（标准训练）</option>
              <option :value="45">45 分钟（深度攻坚）</option>
              <option :value="60">60 分钟（高强突破）</option>
              <option :value="90">90 分钟（全速冲关）</option>
            </select>
          </label>
          <div class="form-actions">
            <button type="button" class="primary btn-regen-plan" :disabled="planLoading" @click="updatePlan">
              {{ planLoading ? '正在智能排布…' : '重新排布计划' }}
            </button>
          </div>
        </div>

        <div v-if="store.plan.value?.days?.length" class="days-container">
          <div
            v-for="day in store.plan.value.days"
            :key="day.day_number"
            class="day-card"
            :class="{ 'day-empty': !day.question_count }"
          >
            <div class="day-card-header">
              <div class="day-info">
                <span class="day-badge">第 {{ day.day_number }} 天</span>
                <h4>{{ day.title }}</h4>
                <span v-if="day.focus" class="day-focus-pill">{{ day.focus }}</span>
              </div>
              <div class="day-meta">
                <span class="day-stats">{{ day.question_count }} 题 · 约 {{ day.estimated_minutes }} 分钟</span>
                <button
                  type="button"
                  class="primary btn-start-day"
                  :disabled="!day.question_ids?.length"
                  @click="startDayPlan(day)"
                >
                  开始第 {{ day.day_number }} 天 ({{ day.question_count }} 题)
                </button>
              </div>
            </div>

            <p class="day-focus-desc">{{ day.focus_description }}</p>

            <!-- 题目清单折叠展开 -->
            <div v-if="day.items?.length" class="day-items-section">
              <button
                type="button"
                class="btn-toggle-items"
                @click="toggleDayExpand(day.day_number)"
              >
                {{ isDayExpanded(day.day_number) ? '收起题目明细 ▲' : `展开题目清单 (${day.items.length} 题) ▼` }}
              </button>

              <ul v-if="isDayExpanded(day.day_number)" class="day-item-list">
                <li v-for="(it, idx) in day.items" :key="idx" class="day-item-row">
                  <span class="item-reason-tag">{{ it.reason }}</span>
                  <span class="item-stem">{{ it.stem }}</span>
                  <span class="item-duration">{{ it.estimated_minutes }} 分钟</span>
                </li>
              </ul>
            </div>
            <div v-else class="day-empty-tip">
              <span>今日无待复习任务，已达到抗遗忘目标或推荐库已学完。</span>
            </div>
          </div>
        </div>
        <p v-else class="muted">暂未生成学习计划，点击上方按钮排布。</p>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import { useLearningStore } from '../stores/learningStore'
import { listBanks } from '../api/banks'
import { startSession } from '../api/practice'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({ token: { type: String, required: true } })
const emit = defineEmits(['back', 'start-session'])

const store = useLearningStore()
const banks = ref([])
const selectedBankId = ref('')
const planBankId = ref('')
const planLoading = ref(false)
const expandedDays = ref({})
const minutesPerDay = ref(30)
const days = ref(7)

const filterNew = ref(true)
const filterWeak = ref(true)
const filterDue = ref(true)
const filterType = ref('')
const filterDifficulty = ref('')
const filterNewRatio = ref(0.5)

function getBankName(bankId) {
  const b = banks.value.find(item => item.id === bankId)
  return b ? b.name : '未知题库'
}

const recsByBank = computed(() => {
  const map = {}
  const list = store.recommendations.value || []
  for (const item of list) {
    const bid = item.bank_id || 'unknown'
    if (!map[bid]) {
      map[bid] = { bank_id: bid, bank_name: getBankName(bid), items: [] }
    }
    map[bid].items.push(item)
  }
  return Object.values(map)
})

const trendText = computed(() => {
  const recentRate = store.trends.value?.recent?.correct_rate || 0
  const baseRate = store.trends.value?.baseline?.correct_rate || 0
  if (!store.trends.value?.baseline?.attempts) return '历史数据积累中'
  const diff = Math.round((recentRate - baseRate) * 10) / 10
  if (diff > 0) return `较基线提升 +${diff}%`
  if (diff < 0) return `较基线下降 ${diff}%`
  return '持平基线'
})

const trendClass = computed(() => {
  const recentRate = store.trends.value?.recent?.correct_rate || 0
  const baseRate = store.trends.value?.baseline?.correct_rate || 0
  if (!store.trends.value?.baseline?.attempts) return ''
  return recentRate >= baseRate ? 'trend-up' : 'trend-down'
})

function onBankChange() {
  load()
}

function load() {
  store.load(props.token, selectedBankId.value, minutesPerDay.value, days.value)
}

function applyFilters() {
  const options = {
    include_new: filterNew.value,
    include_weak: filterWeak.value,
    include_due: filterDue.value,
    new_ratio: filterNewRatio.value,
  }
  if (filterType.value) {
    options.question_type = filterType.value
  }
  if (filterDifficulty.value !== '') {
    options.difficulty = Number(filterDifficulty.value)
  }
  store.reloadRecommendations(props.token, selectedBankId.value, options)
}

async function startRecommendedPractice(group) {
  const items = group ? group.items : (store.recommendations.value || [])
  if (!items.length) return
  const targetBankId = group ? group.bank_id : (selectedBankId.value || items[0].bank_id)
  const bankItems = items.filter(r => r.bank_id === targetBankId)
  if (!bankItems.length) return
  const qIds = bankItems.map(r => r.question_id)
  try {
    const sess = await startSession(props.token, {
      bank_id: targetBankId,
      mode: 'PRACTICE',
      question_ids: qIds,
    })
    emit('start-session', sess)
  } catch (err) {
    alert(`启动练习失败：${err.detail || err.message}`)
  }
}

function formatQuestionTypeName(type) {
  const map = {
    SINGLE: '单选题',
    MULTI: '多选题',
    JUDGE: '判断题',
    ESSAY: '主观题'
  }
  return map[type] || type || '单选题'
}

function isDayExpanded(dayNum) {
  return Boolean(expandedDays.value[dayNum])
}

function toggleDayExpand(dayNum) {
  expandedDays.value[dayNum] = !expandedDays.value[dayNum]
}

async function updatePlan() {
  planLoading.value = true
  try {
    const targetBank = planBankId.value || selectedBankId.value
    await store.reloadStudyPlan(props.token, targetBank, minutesPerDay.value, days.value)
  } finally {
    planLoading.value = false
  }
}

async function startDayPlan(day) {
  if (!day.question_ids || !day.question_ids.length) {
    alert('该日程没有分配题目')
    return
  }
  const targetBankId = day.bank_id || planBankId.value || selectedBankId.value || banks.value[0]?.id
  if (!targetBankId) {
    alert('请选择题库后再开始刷题')
    return
  }
  try {
    const sess = await startSession(props.token, {
      bank_id: targetBankId,
      mode: 'PRACTICE',
      question_ids: day.question_ids,
    })
    emit('start-session', sess)
  } catch (err) {
    alert(`启动日程练习失败：${err.detail || err.message}`)
  }
}

onMounted(async () => {
  try {
    banks.value = await listBanks(props.token)
  } catch (e) {
    console.error('加载题库列表失败', e)
  }
  load()
})
</script>

<style scoped>
.learning-page {
  width: min(100% - 2rem, 76rem);
  max-width: 76rem;
  margin: 1.5rem auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1.5rem;
  min-width: 0;
  overflow-x: hidden;
}

.learning-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  min-width: 0;
}

.learning-header .header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-width: 0;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 1.25rem;
  min-width: 0;
}

.stat-box {
  display: grid;
  gap: 0.35rem;
  padding: 1.35rem;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  min-width: 0;
}

.stat-box strong {
  font-size: 1.85rem;
  color: var(--primary);
  font-weight: 700;
  letter-spacing: -0.02em;
}

.stat-box small {
  color: var(--text-muted);
  font-size: 0.875rem;
  font-weight: 500;
}

.bank-card {
  min-width: 0;
  max-width: 100%;
}

.stat-box p {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin: 0;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1.25rem;
  margin-top: 1.25rem;
  min-width: 0;
}

.comp-col {
  padding: 1.25rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-page);
  min-width: 0;
}

.comp-col h3 {
  font-size: 1rem;
  margin-bottom: 0.85rem;
}

.comp-col ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.65rem;
}

.comp-col li {
  display: flex;
  justify-content: space-between;
  font-size: 0.925rem;
}

.trend-up {
  color: var(--success);
  font-weight: 600;
}

.trend-down {
  color: var(--danger);
  font-weight: 600;
}

.weak-list {
  list-style: none;
  padding: 0;
  margin: 1rem 0 0 0;
  display: grid;
  gap: 0.65rem;
}

.weak-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-page);
}

.rank-num {
  width: 1.6rem;
  height: 1.6rem;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--danger-light);
  color: var(--danger);
  font-weight: 700;
  font-size: 0.8125rem;
}

.point-name {
  flex: 1;
  font-weight: 600;
  font-size: 0.95rem;
}

.mistake-count {
  color: var(--danger);
  font-size: 0.875rem;
  font-weight: 500;
}

.rec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.rec-controls {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
  width: 100%;
  justify-content: space-between;
  margin-top: 0.5rem;
}

.rec-filter-groups {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.rec-switch-group {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.35rem 0.75rem;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.rec-select-group {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.ctrl-check {
  display: flex;
  gap: 0.35rem;
  align-items: center;
  font-size: 0.875rem;
  cursor: pointer;
  user-select: none;
}

.ctrl-select select {
  padding: 0.35rem 0.65rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  font-size: 0.85rem;
}

.rec-list {
  list-style: none;
  padding: 0;
  margin: 1.25rem 0 0 0;
  display: grid;
  gap: 0.65rem;
}

.rec-item {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-page);
  min-width: 0;
  max-width: 100%;
}

.rec-reason {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
  white-space: nowrap;
}

.rec-stem {
  flex: 1 1 0%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.925rem;
}

.plan-header-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.plan-desc {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.plan-summary-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.75rem;
  background: var(--primary-light);
  border: 1px solid var(--primary-border);
  border-radius: var(--radius-sm);
  font-family: var(--linear-mono);
  font-size: 0.8rem;
  color: var(--linear-cyan);
}

.plan-summary-badge .sep {
  color: var(--border-strong);
}

.plan-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)) auto;
  gap: 1rem;
  align-items: flex-end;
  padding: 1.25rem;
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: 1.5rem;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.form-item select {
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--bg-card);
  font-size: 0.9rem;
}

.form-actions {
  display: flex;
  align-items: flex-end;
}

.btn-regen-plan {
  padding: 0.52rem 1.15rem;
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
}

.days-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.day-card {
  padding: 1.25rem;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  transition: border-color 0.2s;
}

.day-card:hover {
  border-color: var(--primary-border);
}

.day-card.day-empty {
  opacity: 0.75;
  background: var(--bg-subtle);
}

.day-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.day-info {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.day-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
}

.day-info h4 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-main);
}

.day-focus-pill {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  background: var(--primary-light);
  border: 1px solid var(--primary-border);
  color: var(--primary);
}

.day-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.day-stats {
  font-size: 0.875rem;
  color: var(--text-muted);
  font-weight: 500;
}

.btn-start-day {
  padding: 0.45rem 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  white-space: nowrap;
}

.day-focus-desc {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin: 0.5rem 0 0.75rem 0;
}

.day-items-section {
  margin-top: 0.5rem;
  border-top: 1px dashed var(--border);
  padding-top: 0.65rem;
}

.btn-toggle-items {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.825rem;
  color: var(--primary);
  cursor: pointer;
  text-decoration: underline;
}

.btn-toggle-items:hover {
  color: var(--primary-hover);
}

.day-item-list {
  list-style: none;
  padding: 0;
  margin: 0.65rem 0 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.day-item-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.45rem 0.65rem;
  background: var(--bg-page);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  min-width: 0;
  max-width: 100%;
}

.item-reason-tag {
  font-size: 0.725rem;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 600;
  white-space: nowrap;
}

.item-stem {
  flex: 1 1 0%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-duration {
  font-size: 0.775rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.day-empty-tip {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
  font-style: italic;
}

@media (max-width: 768px) {
  .learning-page {
    width: 100% !important;
    max-width: 100vw !important;
    padding: 0 0.5rem !important;
    margin: 0.5rem auto !important;
    gap: 0.85rem !important;
    overflow-x: hidden !important;
    box-sizing: border-box !important;
  }
  .bank-card {
    min-width: 0 !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 0.5rem !important;
    width: 100% !important;
    box-sizing: border-box !important;
  }
  .stat-box {
    padding: 0.75rem 0.65rem !important;
    min-width: 0 !important;
    overflow: hidden !important;
  }
  .stat-box strong {
    font-size: 1.25rem !important;
  }
  .stat-box small {
    font-size: 0.75rem !important;
  }
  .stat-box p {
    font-size: 0.7rem !important;
    line-height: 1.3 !important;
    word-break: break-all !important;
  }
  .comparison-grid {
    grid-template-columns: 1fr !important;
    gap: 0.85rem !important;
  }
  .rec-controls {
    width: 100% !important;
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 0.45rem !important;
  }
  .ctrl-select select {
    max-width: 100% !important;
  }
  .rec-item {
    flex-wrap: wrap !important;
  }
}
</style>
