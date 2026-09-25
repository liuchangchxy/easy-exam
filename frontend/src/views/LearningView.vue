<template>
  <main class="learning-page">
    <header class="page-header">
      <button type="button" @click="$emit('back')">返回</button>
      <div>
        <h1>学习诊断与提分推荐</h1>
        <p>基于真实作答与抗遗忘算法的多维学习画像</p>
      </div>
    </header>

    <p v-if="store.loading.value">正在计算学习趋势与诊断报告…</p>
    <p v-else-if="store.error.value" class="error">{{ store.error.value }}</p>

    <template v-else-if="store.trends.value">
      <!-- 概览指标行 -->
      <section class="metrics-grid">
        <article class="bank-card stat-box">
          <small>题库覆盖率</small>
          <strong>{{ store.trends.value.coverage_percent }}%</strong>
          <p>{{ store.trends.value.attempted_questions }} / {{ store.trends.value.total_questions }} 题已练习</p>
        </article>

        <article class="bank-card stat-box">
          <small>复习完成度</small>
          <strong>{{ store.trends.value.review_completion_rate ?? 100 }}%</strong>
          <p>已复习 {{ store.trends.value.reviews_completed ?? 0 }} 题 · 待复习 {{ store.trends.value.due_reviews }} 题</p>
        </article>

        <article class="bank-card stat-box">
          <small>近期平均正确率</small>
          <strong>{{ store.trends.value.recent.correct_rate }}%</strong>
          <p>近 {{ store.trends.value.window_days }} 天作答 {{ store.trends.value.recent.attempts }} 次</p>
        </article>

        <article class="bank-card stat-box">
          <small>近期单题平均耗时</small>
          <strong>{{ store.trends.value.recent.avg_time_per_question ?? 0 }} 秒</strong>
          <p>累计用时 {{ Math.round((store.trends.value.recent.time_spent || 0) / 60) }} 分钟</p>
        </article>
      </section>

      <!-- 近期表现 vs 长期基线对比卡片 -->
      <section class="bank-card comparison-section">
        <h2>近期表现 vs 长期历史基线</h2>
        <div class="comparison-grid">
          <div class="comp-col recent">
            <h3>近期窗口（近 {{ store.trends.value.window_days }} 天）</h3>
            <ul>
              <li><span>作答次数：</span><strong>{{ store.trends.value.recent.attempts }}</strong></li>
              <li><span>正确率：</span><strong>{{ store.trends.value.recent.correct_rate }}%</strong></li>
              <li><span>单题均耗时：</span><strong>{{ store.trends.value.recent.avg_time_per_question ?? 0 }} 秒</strong></li>
              <li><span>练习题量：</span><strong>{{ store.trends.value.recent.attempted_questions }} 题</strong></li>
            </ul>
          </div>
          <div class="comp-col baseline">
            <h3>长期历史基线（此前全部记录）</h3>
            <ul>
              <li><span>作答次数：</span><strong>{{ store.trends.value.baseline.attempts }}</strong></li>
              <li><span>正确率：</span><strong>{{ store.trends.value.baseline.correct_rate }}%</strong></li>
              <li><span>单题均耗时：</span><strong>{{ store.trends.value.baseline.avg_time_per_question ?? 0 }} 秒</strong></li>
              <li><span>趋势状态：</span><strong :class="trendClass">{{ trendText }}</strong></li>
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
            <button
              v-if="store.recommendations.value?.length"
              type="button"
              class="primary btn-start-rec"
              @click="startRecommendedPractice"
            >开始推荐刷题 ({{ store.recommendations.value.length }} 题)</button>
          </div>
        </div>

        <ul v-if="store.recommendations.value?.length" class="rec-list">
          <li v-for="item in store.recommendations.value" :key="item.question_id" class="rec-item">
            <span class="rec-reason">{{ item.reason }}</span>
            <span class="rec-stem">{{ item.stem }}</span>
            <small class="muted">{{ item.type }}</small>
          </li>
        </ul>
        <p v-else class="muted">当前筛选条件下暂无推荐题目。</p>
      </section>

      <!-- 智能学习计划 -->
      <section class="bank-card plan-controls">
        <h2>学习计划定制</h2>
        <div class="plan-form">
          <label>每天刷题时长（分钟）：
            <input v-model.number="minutesPerDay" type="number" min="5" max="600" />
          </label>
          <label>计划周期：
            <select v-model.number="days">
              <option :value="1">1 天计划</option>
              <option :value="3">3 天计划</option>
              <option :value="7">7 天计划</option>
            </select>
          </label>
          <button type="button" class="primary" @click="load">更新计划</button>
        </div>
        <p class="plan-meta">{{ store.plan.value?.question_count || 0 }} 题 · 预计 {{ store.plan.value?.planned_minutes || 0 }} 分钟</p>
        <div v-for="day in store.plan.value?.days || []" :key="day.day_number" class="day-plan">
          <h3>第 {{ day.day_number }} 天 ({{ day.estimated_minutes ?? day.total_minutes ?? 0 }} 分钟)</h3>
          <ul>
            <li v-for="item in day.items" :key="item.question_id">
              <strong>{{ item.reason }}</strong>：{{ item.stem }}（{{ item.estimated_minutes }} 分钟）
            </li>
          </ul>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useLearningStore } from '../stores/learningStore'
import { startSession } from '../api/practice'

const props = defineProps({ token: { type: String, required: true } })
const emit = defineEmits(['back', 'start-session'])

const store = useLearningStore()
const minutesPerDay = ref(30)
const days = ref(7)

const filterNew = ref(true)
const filterWeak = ref(true)
const filterDue = ref(true)
const filterType = ref('')
const filterDifficulty = ref('')
const filterNewRatio = ref(0.5)

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

function load() {
  store.load(props.token, '', minutesPerDay.value, days.value)
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
  store.reloadRecommendations(props.token, '', options)
}

async function startRecommendedPractice() {
  const recs = store.recommendations.value || []
  if (!recs.length) return
  const qIds = recs.map(r => r.question_id)
  const bankId = recs[0].bank_id || ''
  try {
    const sess = await startSession(props.token, {
      bank_id: bankId,
      mode: 'PRACTICE',
      question_ids: qIds,
    })
    emit('start-session', sess)
  } catch (err) {
    alert(`启动练习失败：${err.detail || err.message}`)
  }
}

onMounted(load)
</script>

<style scoped>
.learning-page { width: min(100% - 2rem, 76rem); margin: 1.25rem auto; display: grid; gap: 1.25rem; }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: 1rem; }
.stat-box { display: grid; gap: 0.35rem; padding: 1.25rem; }
.stat-box strong { font-size: 1.6rem; color: var(--primary); }
.stat-box small { color: var(--text-muted); font-size: 0.85rem; }
.stat-box p { font-size: 0.85rem; color: var(--text-muted); margin: 0; }
.comparison-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-top: 1rem; }
.comp-col { padding: 1rem; border-radius: 0.75rem; border: 1px solid var(--border); background: var(--bg-page); }
.comp-col h3 { font-size: 1rem; margin-bottom: 0.75rem; }
.comp-col ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.5rem; }
.comp-col li { display: flex; justify-content: space-between; font-size: 0.95rem; }
.trend-up { color: var(--success); }
.trend-down { color: var(--danger); }
.weak-list { list-style: none; padding: 0; margin: 1rem 0 0 0; display: grid; gap: 0.5rem; }
.weak-item { display: flex; align-items: center; gap: 1rem; padding: 0.65rem 1rem; border: 1px solid var(--border); border-radius: 0.5rem; background: var(--bg-page); }
.rank-num { width: 1.5rem; height: 1.5rem; display: grid; place-items: center; border-radius: 50%; background: #fee2e2; color: #b91c1c; font-weight: 700; font-size: 0.85rem; }
.point-name { flex: 1; font-weight: 600; }
.mistake-count { color: var(--danger); font-size: 0.85rem; }
.rec-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; }
.rec-controls { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
.ctrl-check { display: flex; gap: 0.35rem; align-items: center; font-size: 0.85rem; cursor: pointer; }
.ctrl-select select { padding: 0.35rem 0.65rem; border-radius: 0.4rem; border: 1px solid var(--border); }
.rec-list { list-style: none; padding: 0; margin: 1rem 0 0 0; display: grid; gap: 0.5rem; }
.rec-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.65rem 0.9rem; border: 1px solid var(--border); border-radius: 0.5rem; background: var(--bg-page); }
.rec-reason { font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 0.35rem; background: var(--primary); color: white; }
.rec-stem { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.plan-form { display: flex; gap: 1rem; align-items: center; margin: 1rem 0; flex-wrap: wrap; }
.plan-form label { display: flex; align-items: center; gap: 0.5rem; }
.plan-form input, .plan-form select { padding: 0.45rem 0.65rem; border-radius: 0.4rem; border: 1px solid var(--border); }
.day-plan { margin-top: 1rem; padding: 0.75rem; border: 1px solid var(--border); border-radius: 0.5rem; background: var(--bg-page); }
.day-plan h3 { font-size: 0.95rem; margin-bottom: 0.5rem; }
.day-plan ul { margin-left: 1rem; }
@media (max-width: 640px) {
  .comparison-grid { grid-template-columns: 1fr; }
}
</style>
