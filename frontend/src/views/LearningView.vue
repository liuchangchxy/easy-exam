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

    <p v-if="store.loading.value">{{ t('ui.k0385') }}</p>
    <p v-else-if="store.error.value" class="error">{{ store.error.value }}</p>

    <template v-else-if="store.trends.value">
      <!-- 1. Hero 学习行动发射台 (Practice Launchpad for Today) -->
      <section class="learning-hero-card">
        <div class="hero-top-row">
          <div class="hero-info">
            <div class="hero-badge-row">
              <span class="hero-badge">
                <LinearIcon name="target" size="14" />
                {{ days === 1 ? t('learning.day_sprint') : t('learning.today_task') }}
              </span>
              <span v-if="todayDay?.focus" class="hero-focus-tag">{{ todayDay.focus }}</span>
            </div>
            <h2 class="hero-title">
              {{ todayDay?.title || t('learning.hero_today_title') }}
            </h2>
            <p class="hero-desc">
              {{ todayDay?.focus_description || t('learning.hero_today_desc') }}
            </p>
            <div class="hero-stats-chips">
              <span class="chip">
                {{ t('learning.quota_label') }}：<strong>{{ todayDay?.question_count || 0 }}</strong> {{ t('ui.k0101') }}
              </span>
              <span class="chip">
                {{ t('learning.time_budget_label') }}：<strong>{{ todayDay?.estimated_minutes || 0 }}</strong> {{ t('ui.k0231') }}
              </span>
              <span v-if="store.plan.value" class="chip">
                {{ t('ui.k0429') }}：<strong>{{ store.plan.value.question_count || 0 }}</strong> {{ t('ui.k0101') }}
              </span>
            </div>
          </div>
          <div class="hero-action-box">
            <button
              type="button"
              class="primary hero-play-btn"
              :disabled="!todayDay || !todayDay.question_ids?.length"
              @click="startTodayPlan"
            >
              <LinearIcon name="play" size="18" />
              <span>{{ t('learning.btn_start_today') }} ({{ todayDay?.question_count || 0 }} {{ t('ui.k0101') }})</span>
            </button>
          </div>
        </div>

        <!-- 计划参数快速调优工具条 -->
        <div class="hero-toolbar">
          <div class="toolbar-item">
            <span class="toolbar-label">{{ t('ui.k0432') }}</span>
            <select v-model="planBankId" @change="updatePlan">
              <option value="">{{ t('ui.k0433') }}</option>
              <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
            </select>
          </div>
          <div class="toolbar-item">
            <span class="toolbar-label">{{ t('ui.k0434') }}</span>
            <select v-model.number="days" @change="updatePlan">
              <option :value="1">{{ t('ui.k0435') }} ({{ t('learning.day_sprint') }})</option>
              <option :value="3">{{ t('ui.k0436') }}</option>
              <option :value="7">{{ t('ui.k0437') }}</option>
              <option :value="14">{{ t('ui.k0438') }}</option>
              <option :value="21">{{ t('ui.k0439') }}</option>
              <option :value="30">{{ t('ui.k0440') }}</option>
            </select>
          </div>
          <div class="toolbar-item toolbar-item-quota">
            <div class="toolbar-mode-switch">
              <button
                type="button"
                :class="{ active: planMode === 'quota' }"
                @click="planMode = 'quota'; updatePlan()"
              >{{ t('learning.plan_mode_quota') }}</button>
              <button
                type="button"
                :class="{ active: planMode === 'time' }"
                @click="planMode = 'time'; updatePlan()"
              >{{ t('learning.plan_mode_time') }}</button>
            </div>
            <select v-if="planMode === 'quota'" v-model="questionsPerDay" @change="updatePlan">
              <option :value="15">{{ t('learning.quota_15') }}</option>
              <option :value="30">{{ t('learning.quota_30') }}</option>
              <option :value="50">{{ t('learning.quota_50') }}</option>
              <option :value="100">{{ t('learning.quota_100') }}</option>
              <option value="all">{{ t('learning.quota_all') }}</option>
            </select>
            <select v-else v-model.number="minutesPerDay" @change="updatePlan">
              <option :value="15">{{ t('ui.k0442') }}</option>
              <option :value="30">{{ t('ui.k0443') }}</option>
              <option :value="45">{{ t('ui.k0444') }}</option>
              <option :value="60">{{ t('ui.k0445') }}</option>
              <option :value="90">{{ t('ui.k0446') }}</option>
            </select>
          </div>
        </div>
      </section>

      <!-- 2. 紧凑概览指标条 -->
      <section class="metrics-grid">
        <article class="bank-card stat-box">
          <small>{{ t('ui.k0386') }}</small>
          <strong>{{ store.trends.value.coverage_percent ?? 0 }}%</strong>
          <p>{{ store.trends.value.attempted_questions ?? 0 }} / {{ store.trends.value.total_questions ?? 0 }} {{ t('ui.k0387') }}</p>
        </article>
        <article class="bank-card stat-box">
          <small>{{ t('ui.k0388') }}</small>
          <strong>{{ store.trends.value.review_completion_rate ?? 100 }}%</strong>
          <p>{{ t('ui.k0389') }} {{ store.trends.value.reviews_completed ?? 0 }} {{ t('ui.k0390') }} {{ store.trends.value.due_reviews ?? 0 }} {{ t('ui.k0101') }}</p>
        </article>
        <article class="bank-card stat-box">
          <small>{{ t('ui.k0391') }}</small>
          <strong>{{ store.trends.value.recent?.correct_rate ?? 0 }}%</strong>
          <p>{{ t('ui.k0392') }} {{ store.trends.value.window_days ?? 7 }} {{ t('ui.k0393') }} {{ store.trends.value.recent?.attempts ?? 0 }} {{ t('ui.k0394') }}</p>
        </article>
        <article class="bank-card stat-box">
          <small>{{ t('ui.k0395') }}</small>
          <strong>{{ store.trends.value.recent?.avg_time_per_question ?? 0 }} {{ t('ui.k0396') }}</strong>
          <p>{{ t('ui.k0397') }} {{ Math.round((store.trends.value.recent?.time_spent || 0) / 60) }} {{ t('ui.k0231') }}</p>
        </article>
      </section>

      <!-- 3. 双栏工作区 (主栏：学习计划日程；侧栏：薄弱点榜单与提分推荐) -->
      <div class="learning-two-column-layout">
        <!-- 左侧主栏：学习规划日程 -->
        <section class="bank-card plan-timeline-panel">
          <div class="panel-header">
            <h3>
              <LinearIcon name="calendar" size="16" />
              <span>{{ t('learning.timeline_title') }}</span>
              <span v-if="store.plan.value?.days?.length" class="badge font-mono-code">{{ store.plan.value.days.length }} {{ t('ui.k0447') }}</span>
            </h3>
          </div>

          <div v-if="store.plan.value?.days?.length" class="days-container">
            <div
              v-for="day in store.plan.value.days"
              :key="day.day_number"
              class="day-card"
              :class="{ 'day-empty': !day.question_count, 'day-today': day.day_number === 1 }"
            >
              <div class="day-card-header">
                <div class="day-info">
                  <span class="day-badge">{{ t('ui.k0082') }} {{ day.day_number }} {{ t('ui.k0447') }}</span>
                  <h4>{{ day.title }}</h4>
                  <span v-if="day.focus" class="day-focus-pill">{{ day.focus }}</span>
                </div>
                <div class="day-meta">
                  <span class="day-stats">{{ day.question_count }} {{ t('ui.k0448') }} {{ day.estimated_minutes }} {{ t('ui.k0231') }}</span>
                  <button
                    type="button"
                    class="primary btn-start-day"
                    :disabled="!day.question_ids?.length"
                    @click="startDayPlan(day)"
                  >
                    {{ t('ui.k0449') }} {{ day.day_number }} {{ t('ui.k0450') }}{{ day.question_count }} {{ t('ui.k0123') }}
                  </button>
                </div>
              </div>

              <p class="day-focus-desc">{{ day.focus_description }}</p>

              <!-- 题目清单专属抽屉触发按钮 (告别行内挤压溢出) -->
              <div v-if="day.items?.length" class="day-items-section">
                <button
                  type="button"
                  class="btn-toggle-items"
                  @click="selectedDrawerDay = day"
                >
                  <LinearIcon name="layers" size="13" />
                  <span>{{ `${t('ui.k0708')}${day.items.length} ${t('ui.k0709')}` }}</span>
                </button>
              </div>
            </div>
          </div>
          <p v-else class="muted empty-plan-hint">{{ t('learning.no_questions_in_plan') }}</p>
        </section>

        <!-- 右侧边栏：薄弱考点与智能推荐 -->
        <aside class="learning-sidebar">
          <!-- 薄弱知识点排行 -->
          <section class="bank-card weak-section">
            <div class="panel-header">
              <h3>
                <LinearIcon name="alert-triangle" size="15" />
                <span>{{ t('learning.weak_points_title') }}</span>
              </h3>
            </div>
            <ul v-if="store.trends.value.weak_points?.length" class="weak-list">
              <li v-for="(item, idx) in store.trends.value.weak_points" :key="idx" class="weak-item">
                <span class="rank-num">{{ idx + 1 }}</span>
                <span class="point-name" :title="item.name">{{ item.name }}</span>
                <span class="mistake-count">{{ item.mistakes }} {{ t('ui.k0394') }}</span>
              </li>
            </ul>
            <p v-else class="muted empty-sidebar-hint">{{ t('common.empty') }}</p>
          </section>

          <!-- 提分推荐 -->
          <section class="bank-card recommendations-section">
            <div class="panel-header rec-header-row">
              <div class="rec-title-group">
                <LinearIcon name="zap" size="16" />
                <h3>{{ t('learning.recs_title') }}</h3>
                <span v-if="store.recommendations.value?.length" class="badge-rec-count font-mono-code">
                  {{ store.recommendations.value.length }} {{ t('ui.k0101') }}
                </span>
              </div>
              <div v-if="recsByBank.length" class="rec-actions">
                <button
                  v-for="group in recsByBank"
                  :key="group.bank_id"
                  type="button"
                  class="primary btn-start-rec"
                  @click="startRecommendedPractice(group)"
                >
                  <LinearIcon name="play" size="12" />
                  <span>{{ recsByBank.length > 1 ? `${group.bank_name} (${group.items.length})` : `${t('ui.k0704')}${group.items.length}` }}</span>
                </button>
              </div>
            </div>

            <!-- 紧凑响应式筛选栏 (完全消除横向挤压与溢出) -->
            <div class="rec-controls-bar">
              <select id="select-rec-type" v-model="filterType" class="rec-filter-select" :title="t('ui.k0366')" @change="applyFilters">
                <option value="">{{ t('ui.k0414') }}</option>
                <option value="SINGLE">{{ t('ui.k0050') }}</option>
                <option value="MULTI">{{ t('ui.k0051') }}</option>
                <option value="JUDGE">{{ t('ui.k0052') }}</option>
              </select>
              <select id="select-rec-ratio" v-model.number="filterNewRatio" class="rec-filter-select" :title="t('ui.k0410')" @change="applyFilters">
                <option :value="0.5">{{ t('ui.k0421') }}</option>
                <option :value="0.3">{{ t('ui.k0422') }}</option>
                <option :value="0.7">{{ t('ui.k0423') }}</option>
                <option :value="1.0">{{ t('ui.k0424') }}</option>
                <option :value="0.0">{{ t('ui.k0425') }}</option>
              </select>
            </div>
            <ul v-if="store.recommendations.value?.length" class="rec-list">
              <li v-for="item in store.recommendations.value" :key="item.question_id" class="rec-item">
                <span class="rec-reason">{{ item.reason }}</span>
                <span class="rec-stem" :title="item.stem">{{ item.stem }}</span>
                <small class="muted">{{ item.type }}</small>
              </li>
            </ul>
            <p v-else class="muted empty-sidebar-hint">{{ t('ui.k0426') }}</p>
          </section>
        </aside>
      </div>

      <!-- 4. 底部可折叠基线对比卡片 -->
      <section class="bank-card collapsible-baseline-section">
        <div class="baseline-toggle-header" @click="toggleBaseline">
          <div class="toggle-header-left">
            <LinearIcon name="activity" size="16" />
            <h3>{{ t('learning.baseline_title') }}</h3>
            <span :class="trendClass" class="trend-badge">{{ trendText || t('ui.k0700') }}</span>
          </div>
          <button type="button" class="btn-toggle-baseline">
            <span>{{ showBaseline ? t('ui.k0707') : t('learning.toggle_baseline') }}</span>
            <LinearIcon name="chevron-right" size="14" :style="{ transform: showBaseline ? 'rotate(90deg)' : 'none', transition: 'transform 150ms ease' }" />
          </button>
        </div>

        <div v-if="showBaseline" class="comparison-grid">
          <div class="comp-col recent">
            <h4>{{ t('ui.k0399') }} {{ store.trends.value.window_days ?? 7 }} {{ t('ui.k0400') }}</h4>
            <ul>
              <li><span>{{ t('ui.k0401') }}</span><strong>{{ store.trends.value.recent?.attempts ?? 0 }} {{ t('ui.k0394') }}</strong></li>
              <li><span>{{ t('ui.k0402') }}</span><strong>{{ store.trends.value.recent?.correct_rate ?? 0 }}%</strong></li>
              <li><span>{{ t('ui.k0403') }}</span><strong>{{ store.trends.value.recent?.avg_time_per_question ?? 0 }} {{ t('ui.k0396') }}</strong></li>
              <li><span>{{ t('ui.k0404') }}</span><strong>{{ store.trends.value.recent?.attempted_questions ?? 0 }} {{ t('ui.k0101') }}</strong></li>
            </ul>
          </div>
          <div class="comp-col baseline">
            <h4>{{ t('ui.k0405') }}</h4>
            <ul>
              <li><span>{{ t('ui.k0401') }}</span><strong>{{ store.trends.value.baseline?.attempts ?? 0 }} {{ t('ui.k0394') }}</strong></li>
              <li><span>{{ t('ui.k0402') }}</span><strong>{{ store.trends.value.baseline?.correct_rate ?? 0 }}%</strong></li>
              <li><span>{{ t('ui.k0403') }}</span><strong>{{ store.trends.value.baseline?.avg_time_per_question ?? 0 }} {{ t('ui.k0396') }}</strong></li>
              <li><span>{{ t('ui.k0406') }}</span><strong :class="trendClass">{{ trendText || t('ui.k0700') }}</strong></li>
            </ul>
          </div>
        </div>
      </section>
    </template>

    <!-- 专属任务题目清单抽屉 (Slide-over Drawer，彻底杜绝行内溢出) -->
    <div v-if="selectedDrawerDay" class="task-drawer-backdrop" @click.self="selectedDrawerDay = null">
      <aside class="task-drawer" role="dialog" aria-modal="true">
        <div class="task-drawer-header">
          <div class="task-drawer-title-group">
            <span class="day-badge">{{ t('ui.k0082') }} {{ selectedDrawerDay.day_number }} {{ t('ui.k0447') }}</span>
            <h3>{{ selectedDrawerDay.title }}</h3>
            <span class="drawer-count-pill font-mono-code">{{ selectedDrawerDay.items?.length || 0 }} {{ t('ui.k0101') }}</span>
          </div>
          <button type="button" class="btn-close-drawer" @click="selectedDrawerDay = null">✕</button>
        </div>

        <div class="task-drawer-subheader">
          <p class="drawer-focus-desc">{{ selectedDrawerDay.focus_description }}</p>
          <button
            type="button"
            class="primary-btn btn-drawer-start"
            :disabled="!selectedDrawerDay.question_ids?.length"
            @click="startDayPlan(selectedDrawerDay)"
          >
            <LinearIcon name="play" size="14" />
            <span>{{ t('ui.k0449') }} {{ selectedDrawerDay.day_number }} {{ t('ui.k0450') }}{{ selectedDrawerDay.question_count }} {{ t('ui.k0123') }}</span>
          </button>
        </div>

        <div class="task-drawer-body">
          <div
            v-for="(q, qIdx) in selectedDrawerDay.items"
            :key="q.question_id"
            class="drawer-question-card"
          >
            <div class="drawer-q-top">
              <span class="q-num font-mono-code">#{{ qIdx + 1 }}</span>
              <span class="item-type-tag">{{ formatQuestionTypeName(q.type) }}</span>
              <span v-if="q.reason" class="item-reason-tag">{{ q.reason }}</span>
            </div>
            <div class="drawer-q-stem">
              <p>{{ q.stem }}</p>
            </div>
          </div>
        </div>
      </aside>
    </div>
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
const planMode = ref('quota')
const questionsPerDay = ref(30)
const showBaseline = ref(false)
const selectedDrawerDay = ref(null)

const filterNew = ref(true)
const filterWeak = ref(true)
const filterDue = ref(true)
const filterType = ref('')
const filterDifficulty = ref('')
const filterNewRatio = ref(0.5)

function getBankName(bankId) {
  const b = banks.value.find(item => item.id === bankId)
  return b ? b.name : t('ui.k0453')
}

const todayDay = computed(() => {
  return store.plan.value?.days?.[0] || null
})

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
  if (!store.trends.value?.baseline?.attempts) return t('ui.k0454')
  const diff = Math.round((recentRate - baseRate) * 10) / 10
  if (diff > 0) return `${t('ui.k0455')}${diff}%`
  if (diff < 0) return `${t('ui.k0456')} ${diff}%`
  return t('ui.k0457')
})

const trendClass = computed(() => {
  const recentRate = store.trends.value?.recent?.correct_rate || 0
  const baseRate = store.trends.value?.baseline?.correct_rate || 0
  if (!store.trends.value?.baseline?.attempts) return ''
  return recentRate >= baseRate ? 'trend-up' : 'trend-down'
})

const PLAN_PREFS_KEY = 'easyexam_learning_plan_prefs'

function loadSavedPrefs() {
  try {
    const raw = localStorage.getItem(PLAN_PREFS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed.days && [1, 3, 7, 14, 21, 30].includes(Number(parsed.days))) {
        days.value = Number(parsed.days)
      }
      if (parsed.planMode && ['quota', 'time'].includes(parsed.planMode)) {
        planMode.value = parsed.planMode
      }
      if (parsed.questionsPerDay !== undefined) {
        questionsPerDay.value = parsed.questionsPerDay === 'all' ? 'all' : Number(parsed.questionsPerDay)
      }
      if (parsed.minutesPerDay && Number(parsed.minutesPerDay) > 0) {
        minutesPerDay.value = Number(parsed.minutesPerDay)
      }
      if (parsed.selectedBankId) {
        selectedBankId.value = String(parsed.selectedBankId)
      }
      if (parsed.planBankId) {
        planBankId.value = String(parsed.planBankId)
      }
    }
  } catch (_) {}
}

function savePrefs() {
  try {
    localStorage.setItem(PLAN_PREFS_KEY, JSON.stringify({
      days: days.value,
      planMode: planMode.value,
      questionsPerDay: questionsPerDay.value,
      minutesPerDay: minutesPerDay.value,
      selectedBankId: selectedBankId.value,
      planBankId: planBankId.value,
    }))
  } catch (_) {}
}

function onBankChange() {
  savePrefs()
  load()
}

function toggleBaseline() {
  showBaseline.value = !showBaseline.value
}

function load() {
  const qQuota = planMode.value === 'quota' ? (questionsPerDay.value === 'all' ? 9999 : Number(questionsPerDay.value)) : null
  store.load(props.token, selectedBankId.value, minutesPerDay.value, days.value, qQuota)
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
    alert(`${t('ui.k0458')}${err.detail || err.message}`)
  }
}

function formatQuestionTypeName(type) {
  const map = {
    SINGLE: t('ui.k0050'),
    MULTI: t('ui.k0051'),
    JUDGE: t('ui.k0052'),
    ESSAY: t('ui.k0054')
  }
  return map[type] || type || t('ui.k0050')
}

function isDayExpanded(dayNum) {
  return Boolean(expandedDays.value[dayNum])
}

function toggleDayExpand(dayNum) {
  expandedDays.value[dayNum] = !expandedDays.value[dayNum]
}

async function updatePlan() {
  savePrefs()
  planLoading.value = true
  try {
    const targetBank = planBankId.value || selectedBankId.value
    const qQuota = planMode.value === 'quota' ? (questionsPerDay.value === 'all' ? 9999 : Number(questionsPerDay.value)) : null
    await store.reloadStudyPlan(props.token, targetBank, minutesPerDay.value, days.value, qQuota)
  } finally {
    planLoading.value = false
  }
}

async function startDayPlan(day) {
  selectedDrawerDay.value = null
  if (!day.question_ids || !day.question_ids.length) {
    alert(t('ui.k0459'))
    return
  }
  const targetBankId = day.bank_id || planBankId.value || selectedBankId.value || banks.value[0]?.id
  if (!targetBankId) {
    alert(t('ui.k0460'))
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
    alert(`${t('ui.k0461')}${err.detail || err.message}`)
  }
}

function startTodayPlan() {
  if (todayDay.value) {
    startDayPlan(todayDay.value)
  }
}

onMounted(async () => {
  loadSavedPrefs()
  try {
    banks.value = await listBanks(props.token)
    if (selectedBankId.value && !banks.value.some(b => b.id === selectedBankId.value)) {
      selectedBankId.value = ''
    }
  } catch (e) {
    console.error(t('ui.k0462'), e)
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
  gap: 1.25rem;
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

/* 1. Hero 学习行动发射台样式 */
.learning-hero-card {
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-xl);
  padding: 1.5rem 1.75rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
}

.hero-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.hero-info {
  flex: 1;
  min-width: 18rem;
}

.hero-badge-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.45rem;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  background: var(--primary-light);
  color: var(--primary);
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
}

.hero-focus-tag {
  font-size: 0.75rem;
  color: var(--text-muted);
  background: var(--bg-page);
  border: 1px solid var(--border);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

.hero-title {
  font-size: 1.35rem;
  font-weight: 700;
  margin: 0 0 0.35rem 0;
  color: var(--text-main);
  letter-spacing: -0.01em;
}

.hero-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0 0 0.85rem 0;
  max-width: 42rem;
  line-height: 1.5;
}

.hero-stats-chips {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.chip {
  font-size: 0.78rem;
  background: var(--bg-page);
  border: 1px solid var(--border);
  padding: 0.25rem 0.65rem;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
}

.chip strong {
  color: var(--text-main);
  font-family: var(--linear-mono);
}

.hero-action-box {
  display: flex;
  align-items: center;
}

.hero-play-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.75rem 1.6rem;
  font-size: 0.95rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
  cursor: pointer;
  transition: all 150ms ease;
}

.hero-play-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.35);
}

/* 计划参数调优工具条 */
.hero-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}

.toolbar-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.82rem;
  max-width: 100%;
  min-width: 0;
}

.toolbar-label {
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.toolbar-item select {
  font-size: 0.82rem;
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-page);
  color: var(--text-main);
  max-width: 16rem;
  min-width: 0;
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.toolbar-item-quota {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.toolbar-mode-switch {
  display: inline-flex;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 2px;
}

.toolbar-mode-switch button {
  border: none;
  background: transparent;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  border-radius: 3px;
  cursor: pointer;
  color: var(--text-muted);
  transition: all 120ms ease;
}

.toolbar-mode-switch button.active {
  background: var(--bg-card);
  color: var(--primary);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.btn-regen-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-main);
  cursor: pointer;
  margin-left: auto;
  transition: all 120ms ease;
}

.btn-regen-toolbar:hover:not(:disabled) {
  background: var(--bg-subtle);
  border-color: var(--border-strong);
}

/* 2. 概览指标行 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 1rem;
  min-width: 0;
}

.stat-box {
  display: grid;
  gap: 0.35rem;
  padding: 1.15rem 1.25rem;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  min-width: 0;
}

.stat-box strong {
  font-size: 1.65rem;
  color: var(--primary);
  font-weight: 700;
  letter-spacing: -0.02em;
  font-family: var(--linear-mono);
}

.stat-box small {
  color: var(--text-muted);
  font-size: 0.82rem;
  font-weight: 500;
}

.stat-box p {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0;
}

.bank-card {
  min-width: 0;
  max-width: 100%;
}

/* 3. 双栏工作区 */
.learning-two-column-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 1.5rem;
  align-items: start;
  min-width: 0;
  width: 100%;
}

.plan-timeline-panel {
  padding: 1.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  min-width: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  min-width: 0;
  flex-wrap: wrap;
}

.panel-header h3 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-main);
  min-width: 0;
}

.learning-sidebar {
  display: grid;
  gap: 1.25rem;
  min-width: 0;
  max-width: 100%;
}

.weak-section,
.recommendations-section {
  padding: 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

/* 提分推荐顶栏与过滤条 */
.rec-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
  min-width: 0;
}

.rec-title-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.rec-title-group h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
}

.badge-rec-count {
  font-size: 0.72rem;
  background: var(--bg-subtle);
  color: var(--text-muted);
  border: 1px solid var(--border);
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
}

.rec-controls-bar {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 0.85rem;
  min-width: 0;
  width: 100%;
}

.rec-filter-select {
  width: 100%;
  min-width: 0;
  font-size: 0.8rem;
  padding: 0.4rem 0.6rem;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  color: var(--text-main);
  text-overflow: ellipsis;
  box-sizing: border-box;
  outline: none;
  transition: all 120ms ease;
}

.rec-filter-select:focus {
  border-color: var(--primary);
  background: var(--bg-card);
}

.btn-start-rec {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  white-space: nowrap;
}

.weak-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.5rem;
  min-width: 0;
}

.weak-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.rank-num {
  font-weight: 700;
  font-size: 0.78rem;
  color: var(--danger);
  width: 1.2rem;
  flex-shrink: 0;
  font-family: var(--linear-mono);
}

.point-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
  font-weight: 500;
}

.mistake-count {
  font-size: 0.75rem;
  color: var(--danger);
  background: var(--danger-light);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  flex-shrink: 0;
  font-family: var(--linear-mono);
}

.rec-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.5rem;
  min-width: 0;
}

.rec-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 0.82rem;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.rec-reason {
  font-size: 0.72rem;
  padding: 0.15rem 0.4rem;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
}

.rec-stem {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
}

/* 4. 日程卡片与题目清单 */
.days-container {
  display: grid;
  gap: 0.85rem;
}

.day-card {
  padding: 1rem 1.25rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
  transition: all 120ms ease;
}

.day-card.day-today {
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.08);
}

.day-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.day-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.day-badge {
  font-size: 0.72rem;
  font-weight: 700;
  background: var(--primary);
  color: #fff;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-family: var(--linear-mono);
}

.day-info h4 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-main);
}

.day-focus-pill {
  font-size: 0.72rem;
  padding: 0.12rem 0.45rem;
  border-radius: 4px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-muted);
}

.day-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.day-stats {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-family: var(--linear-mono);
}

.btn-start-day {
  padding: 0.35rem 0.8rem;
  font-size: 0.82rem;
  white-space: nowrap;
}

.day-focus-desc {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin: 0.5rem 0 0.5rem 0;
  line-height: 1.4;
}

.day-items-section {
  margin-top: 0.65rem;
  padding-top: 0.5rem;
  border-top: 1px dashed var(--border);
}

.btn-toggle-items {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: none;
  border: none;
  color: var(--primary);
  font-size: 0.78rem;
  font-weight: 500;
  padding: 0.2rem 0;
  cursor: pointer;
  transition: color 120ms ease;
}

.btn-toggle-items:hover {
  color: var(--primary-hover, #1d4ed8);
}

.day-items-list {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-height: 20rem;
  overflow-y: auto;
  padding: 0.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  scrollbar-width: thin;
}

.day-item-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  min-width: 0;
  padding: 0.35rem 0.5rem;
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  transition: background 120ms ease;
}

.day-item-row:hover {
  background: var(--bg-subtle);
}

.item-index {
  font-size: 0.72rem;
  color: var(--text-tertiary);
  font-family: var(--linear-mono);
  min-width: 1.5rem;
  text-align: right;
  flex-shrink: 0;
}

.item-type-tag {
  font-size: 0.68rem;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-family: var(--linear-mono);
  white-space: nowrap;
  flex-shrink: 0;
}

.item-stem {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
}

.item-reason-tag {
  font-size: 0.68rem;
  color: var(--primary);
  background: var(--primary-light);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
}

/* 5. 底部可折叠基线对比 */
.collapsible-baseline-section {
  padding: 1.25rem 1.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
}

.baseline-toggle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.toggle-header-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.toggle-header-left h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-main);
}

.trend-badge {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-family: var(--linear-mono);
}

.trend-up {
  color: var(--success);
  background: var(--success-light);
}

.trend-down {
  color: var(--danger);
  background: var(--danger-light);
}

.btn-toggle-baseline {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: pointer;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1.25rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.comp-col {
  padding: 1.25rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-page);
}

.comp-col h4 {
  margin: 0 0 0.75rem 0;
  font-size: 0.9rem;
  color: var(--text-main);
}

.comp-col ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.45rem;
}

.comp-col li {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.comp-col li strong {
  color: var(--text-main);
  font-family: var(--linear-mono);
}

/* 响应式断点 */
@media (max-width: 1080px) {
  .learning-two-column-layout {
    grid-template-columns: 1fr;
  }
  .hero-top-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .hero-play-btn {
    width: 100%;
    justify-content: center;
  }
}

/* 专属任务题目清单抽屉 (Slide-over Drawer) */
.task-drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  animation: drawerFadeIn 150ms ease;
}

.task-drawer {
  width: 500px;
  max-width: 100vw;
  height: 100vh;
  background: var(--bg-card);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.16);
  animation: drawerSlideIn 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes drawerFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes drawerSlideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.task-drawer-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.task-drawer-title-group {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.task-drawer-title-group h3 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-main);
}

.drawer-count-pill {
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 9999px;
  color: var(--text-muted);
}

.btn-close-drawer {
  background: none;
  border: none;
  color: var(--text-tertiary);
  font-size: 1.15rem;
  cursor: pointer;
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-sm);
  transition: all 120ms ease;
}

.btn-close-drawer:hover {
  color: var(--text-main);
  background: var(--bg-subtle);
}

.task-drawer-subheader {
  padding: 1rem 1.5rem;
  background: var(--bg-page);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.drawer-focus-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.45;
}

.btn-drawer-start {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.65rem 1rem;
  font-size: 0.9rem;
}

.task-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  scrollbar-width: thin;
}

.drawer-question-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}

.drawer-question-card:hover {
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.06);
}

.drawer-q-top {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.q-num {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-tertiary);
}

.drawer-q-stem p {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.55;
  color: var(--text-main);
  word-break: break-word;
}

@media (max-width: 768px) {
  .task-drawer {
    width: 100vw;
    border-left: none;
  }
  .task-drawer-header {
    padding: 1rem 1.15rem;
  }
  .task-drawer-subheader {
    padding: 0.85rem 1.15rem;
  }
  .task-drawer-body {
    padding: 0.85rem 1.15rem calc(1rem + env(safe-area-inset-bottom, 0));
  }
  .btn-close-drawer {
    width: 36px;
    height: 36px;
    font-size: 1.1rem;
  }
}
</style>
