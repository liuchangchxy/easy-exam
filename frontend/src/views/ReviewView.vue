<template>
  <div class="review-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.nav.study') }}</div>
        <h1 class="page-title">{{ t('ep.review.title') }}</h1>
        <p class="page-sub">{{ t('ep.review.sub') }}</p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn btn-primary" :disabled="!dueReviews.length || starting" @click="startDueAll">
          <LinearIcon name="play" :size="14" />{{ t('ep.review.start_due') }}
        </button>
      </div>
    </div>

    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key" type="button" class="tab" :class="{ 'is-active': activeTab === tab.key }" :data-testid="'review-tab-' + tab.key" @click="selectTab(tab.key)">
        {{ t(tab.label) }}<span class="count">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="notice" class="notice bad review-notice">
      <LinearIcon name="alert" :size="15" /><span>{{ notice }}</span>
    </div>

    <div v-if="loading" class="skeleton-rows">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </div>

    <div v-else-if="loadError" class="notice bad review-notice review-load-error" role="alert">
      <LinearIcon name="alert" :size="15" />
      <span>{{ t('ep.common.load_failed') }}</span>
      <button type="button" class="btn btn-sm" @click="load">{{ t('ep.common.retry') }}</button>
    </div>

    <template v-else>
      <!-- Due -->
      <div v-if="activeTab === 'due'" class="review-layout review-workspace">
        <div class="review-main review-hub-main">
          <div class="stat-row review-stats">
            <div class="stat">
              <div class="stat-num">{{ dueReviews.length }}</div>
              <div class="stat-cap">{{ t('ep.review.tab_due') }}</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ mistakes.length }}</div>
              <div class="stat-cap">{{ t('ep.review.tab_mistakes') }}</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ killed.length }}</div>
              <div class="stat-cap">{{ t('ep.review.tab_killed') }}</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ dueBankGroups.length }}</div>
              <div class="stat-cap">{{ t('ep.nav.banks') }}</div>
            </div>
          </div>

          <section v-if="dueBankGroups.length" class="panel">
            <div class="panel-head">
              <span class="panel-title">{{ t('ep.review.due_by_bank') }}</span>
              <span class="section-note">{{ t('ep.review.due_count', { count: dueReviews.length }) }}</span>
            </div>
            <div class="list">
              <div v-for="group in dueBankGroups" :key="group.bank_id" class="list-row">
                <span class="list-main">
                  <span class="list-title">{{ group.bank_name }}</span>
                  <span class="list-meta">{{ t('ep.review.due_count', { count: group.items.length }) }}</span>
                </span>
                <span class="list-side">
                  <button type="button" class="btn btn-sm" :disabled="starting" @click="startDueGroup(group)">
                    {{ t('ep.review.start_bank') }}
                  </button>
                </span>
              </div>
            </div>
          </section>

          <section v-if="dueReviews.length" class="panel">
            <div class="panel-head">
              <span class="panel-title">{{ t('ep.practice.index') }}</span>
            </div>
            <div class="list">
              <div v-for="item in dueReviews" :key="item.question_id" class="list-row due-row">
                <span class="qtype mono">{{ typeLabel(item.type) }}</span>
                <span class="list-main">
                  <span class="qrow-stem">{{ item.stem }}</span>
                  <span class="list-meta">
                    <span>{{ bankName(item.bank_id) }}</span>
                    <span v-if="item.is_weak || item.is_weak_flagged" class="tag brand">{{ t('ep.review.weak') }}</span>
                    <span v-if="item.stability != null">{{ t('ep.review.stability') }} · {{ Number(item.stability).toFixed(1) }}</span>
                  </span>
                </span>
                <span class="list-side">
                  <button type="button" class="btn btn-sm btn-quiet" :disabled="starting" @click="startFsrsOne(item)">
                    {{ t('ep.review.review_one') }}
                  </button>
                </span>
              </div>
            </div>
          </section>

          <div v-else class="empty">
            <div class="empty-mark"><LinearIcon name="check" :size="26" /></div>
            <div class="empty-title">{{ t('ep.review.due_empty') }}</div>
            <div class="empty-desc">{{ t('ep.review.due_empty_hint') }}</div>
          </div>
        </div>

        <aside class="review-rail review-hub-rail">
          <div class="rail-block">
            <div class="rail-title">{{ t('ep.review.tab_mistakes') }}</div>
            <p class="rail-note">{{ t('ep.review.mistakes_empty_hint') }}</p>
            <button type="button" class="btn btn-sm btn-block" :disabled="!mistakes.length" @click="startMistakeAll">
              {{ t('ep.review.start_mistakes') }}
            </button>
          </div>
          <div class="rail-block">
            <div class="rail-title">{{ t('ep.review.tab_killed') }}</div>
            <p class="rail-note">{{ t('ep.review.killed_count', { count: killed.length }) }}</p>
            <button type="button" class="btn btn-sm btn-block" :disabled="!killed.length" @click="startKilledAll">
              {{ t('ep.practice.start') }}
            </button>
          </div>
          <div class="rail-block">
            <div class="rail-title">{{ t('ep.review.tab_diagnosis') }}</div>
            <p class="rail-note">{{ t('ep.review.diagnosis_empty_hint') }}</p>
            <button type="button" class="btn btn-sm btn-block" @click="selectTab('diagnosis')">
              {{ t('ep.review.diagnosis_accuracy') }}
            </button>
          </div>
        </aside>
      </div>

      <!-- Mistakes -->
      <section v-else-if="activeTab === 'mistakes'" class="review-single">
        <div class="toolbar review-toolbar">
          <select v-model="mistakeBank" class="select">
            <option value="">{{ t('ep.review.filter_bank') }}</option>
            <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
          <select v-model="mistakeCause" class="select">
            <option value="">{{ t('ep.review.filter_cause') }}</option>
            <option v-for="c in causes" :key="c.key" :value="c.key">{{ c.label }}</option>
          </select>
          <div class="spacer"></div>
          <span class="small dim">{{ t('ep.review.mistakes_count', { count: filteredMistakes.length }) }}</span>
          <button type="button" class="btn btn-primary btn-sm" :disabled="!filteredMistakes.length || starting" @click="startMistakeAll">
            {{ t('ep.review.start_mistakes') }}
          </button>
        </div>

        <div v-if="filteredMistakes.length" class="panel">
          <div class="list">
            <div v-for="item in filteredMistakes" :key="item.question_id" class="list-row mistake-row">
              <span class="qtype mono">{{ typeLabel(item.type) }}</span>
              <span class="list-main">
                <span class="qrow-stem">{{ item.stem }}</span>
                <span class="list-meta">
                  <span>{{ bankName(item.bank_id) }}</span>
                  <span>{{ item.mistake_count }}×</span>
                  <span v-if="item.is_due" class="tag brand">{{ t('ep.review.tab_due') }}</span>
                </span>
              </span>
              <span class="list-side mistake-actions">
                <select class="select cause-select" :value="item.mistake_cause || ''" @change="setCause(item, $event.target.value)">
                  <option value="">{{ t('ep.review.cause_unknown') }}</option>
                  <option v-for="c in causes" :key="c.key" :value="c.key">{{ c.label }}</option>
                </select>
                <button type="button" class="btn btn-sm" :disabled="starting" @click="startMistakeOne(item)">
                  {{ t('ep.review.review_one') }}
                </button>
                <button type="button" class="btn btn-sm btn-quiet" @click="kill(item.question_id)">
                  {{ t('ep.practice.kill') }}
                </button>
              </span>
            </div>
          </div>
        </div>
        <div v-else class="empty">
          <div class="empty-mark"><LinearIcon name="check" :size="26" /></div>
          <div class="empty-title">{{ t('ep.review.mistakes_empty') }}</div>
          <div class="empty-desc">{{ t('ep.review.mistakes_empty_hint') }}</div>
        </div>
      </section>

      <!-- Killed -->
      <section v-else-if="activeTab === 'killed'" class="review-single">
        <div class="toolbar review-toolbar">
          <select v-model="mistakeBank" class="select">
            <option value="">{{ t('ep.review.filter_bank') }}</option>
            <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
          <div class="spacer"></div>
          <span class="small dim">{{ t('ep.review.killed_count', { count: filteredKilled.length }) }}</span>
          <button type="button" class="btn btn-sm" :disabled="!filteredKilled.length || starting" @click="startKilledAll">
            {{ t('ep.practice.start') }}
          </button>
        </div>

        <div v-if="filteredKilled.length" class="panel">
          <div class="list">
            <div v-for="item in filteredKilled" :key="item.question_id" class="list-row">
              <span class="qtype mono">{{ typeLabel(item.type) }}</span>
              <span class="list-main">
                <span class="qrow-stem">{{ item.stem }}</span>
                <span class="list-meta"><span>{{ bankName(item.bank_id) }}</span></span>
              </span>
              <span class="list-side">
                <button type="button" class="btn btn-sm" @click="restore(item.question_id)">
                  {{ t('ep.review.restore') }}
                </button>
              </span>
            </div>
          </div>
        </div>
        <div v-else class="empty">
          <div class="empty-mark"><LinearIcon name="award" :size="26" /></div>
          <div class="empty-title">{{ t('ep.review.killed_empty') }}</div>
          <div class="empty-desc">{{ t('ep.review.killed_empty_hint') }}</div>
        </div>
      </section>

      <!-- All (one queue) -->
      <section v-else-if="activeTab === 'all'" class="review-single review-queue" data-testid="review-queue">
        <div class="toolbar review-toolbar review-queue-toolbar">
          <div class="chip-row review-reason-filter" role="group" :aria-label="t('ep.review.reason_filter')" data-testid="review-reason-filter">
            <button
              v-for="filter in reasonFilters"
              :key="filter.key"
              type="button"
              class="chip review-reason-chip"
              :class="{ 'is-on': reasonFilter === filter.key }"
              :data-reason="filter.key"
              :data-testid="'review-reason-' + filter.key"
              @click="selectReason(filter.key)"
            >
              {{ t(filter.label) }}<span class="count">{{ reasonCount(filter.key) }}</span>
            </button>
          </div>
          <div class="spacer"></div>
          <label class="search-box review-queue-search">
            <LinearIcon name="search" :size="14" />
            <input
              v-model="queueQuery"
              class="input"
              type="search"
              data-testid="review-queue-search"
              :placeholder="t('ep.review.search_placeholder')"
              :aria-label="t('ep.review.search_placeholder')"
            />
          </label>
          <label class="review-scope">
            <span class="small dim">{{ t('ep.review.filter_bank') }}</span>
            <select v-model="queueScope" class="select" data-testid="review-queue-scope">
              <option value="all">{{ t('ep.review.filter_bank') }}</option>
              <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
            </select>
          </label>
          <span class="small dim">{{ t('ep.review.queue_count', { count: visibleQueue.length }) }}</span>
        </div>

        <div v-if="visibleQueue.length" class="panel">
          <div class="list">
            <div v-for="row in visibleQueue" :key="row.key" class="list-row review-queue-row" :data-key="row.key">
              <span class="qtype mono">{{ typeLabel(row.type) }}</span>
              <span class="list-main">
                <span class="qrow-stem">{{ row.stem }}</span>
                <span class="list-meta">
                  <span>{{ bankName(row.bank_id) }}</span>
                  <span v-for="reason in row.reasons" :key="reason" class="tag review-reason-tag" :class="{ brand: reason === 'due' }" :data-reason="reason">
                    {{ t(reviewReasonLabelKey(reason)) }}
                  </span>
                  <span v-if="row.mistake_count">{{ row.mistake_count }}×</span>
                </span>
              </span>
              <span class="list-side">
                <button type="button" class="btn btn-sm btn-quiet review-queue-start" :disabled="starting" @click="startQueueRow(row)">
                  {{ t('ep.review.review_one') }}
                </button>
              </span>
            </div>
          </div>
        </div>
        <div v-else class="empty review-queue-empty">
          <div class="empty-mark"><LinearIcon name="check" :size="26" /></div>
          <div class="empty-title">{{ t(emptyKeys.title) }}</div>
          <div class="empty-desc">{{ t(emptyKeys.hint) }}</div>
        </div>
      </section>

      <!-- Diagnosis -->
      <section v-else class="review-single diagnosis">
        <template v-if="trends">
          <div class="stat-row review-stats">
            <div class="stat">
              <div class="stat-num">{{ trends.recent?.correct_rate ?? 0 }}<span class="unit">%</span></div>
              <div class="stat-cap">{{ t('ep.review.diagnosis_accuracy') }}</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ trends.recent?.attempts ?? 0 }}</div>
              <div class="stat-cap">{{ t('ep.review.diagnosis_volume') }}</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ trends.coverage_percent ?? 0 }}<span class="unit">%</span></div>
              <div class="stat-cap">{{ t('ep.library.title') }} · {{ t('ep.review.diagnosis_trend') }}</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ trends.due_reviews ?? 0 }}</div>
              <div class="stat-cap">{{ t('ep.review.tab_due') }}</div>
            </div>
          </div>

          <div class="diagnosis-grid">
            <section class="panel">
              <div class="panel-head">
                <span class="panel-title">{{ t('ep.review.diagnosis_weak') }}</span>
              </div>
              <div v-if="trends.weak_points?.length" class="list">
                <div v-for="(point, idx) in trends.weak_points" :key="idx" class="list-row">
                  <span class="rank mono">{{ String(idx + 1).padStart(2, '0') }}</span>
                  <span class="list-main">
                    <span class="list-title">{{ point.name }}</span>
                    <span class="list-meta">{{ point.mistakes }} {{ t('ep.review.tab_mistakes') }}</span>
                  </span>
                </div>
              </div>
              <div v-else class="empty" style="padding: 24px 0">
                <div class="empty-desc">{{ t('ep.review.diagnosis_empty') }}</div>
              </div>
            </section>

            <section class="panel">
              <div class="panel-head">
                <span class="panel-title">{{ t('ep.review.diagnosis_plan') }}</span>
                <span class="section-note">{{ plan?.question_count || 0 }} {{ t('ep.practice.index') }}</span>
              </div>
              <div v-if="plan?.days?.length" class="list">
                <div v-for="day in plan.days.slice(0, 7)" :key="day.day_number" class="list-row plan-row">
                  <span class="day-no mono">{{ String(day.day_number).padStart(2, '0') }}</span>
                  <span class="list-main">
                    <span class="list-title">{{ day.title }}</span>
                    <span class="list-meta">
                      <span>{{ t('ep.today.plan_items', { count: day.question_count || 0 }) }}</span>
                      <span>{{ day.estimated_minutes || 0 }} {{ t('ep.common.min') }}</span>
                    </span>
                  </span>
                  <span class="list-side">
                    <button type="button" class="btn btn-sm btn-quiet" :disabled="!day.question_ids?.length || starting" @click="startPlanDay(day)">
                      {{ t('ep.practice.start') }}
                    </button>
                  </span>
                </div>
              </div>
              <div v-else class="empty" style="padding: 24px 0">
                <div class="empty-desc">{{ t('ep.review.diagnosis_empty') }}</div>
              </div>
            </section>
          </div>

          <section class="panel">
            <div class="panel-head">
              <span class="panel-title">{{ t('ep.review.diagnosis_recommend') }}</span>
              <span class="section-note">{{ recommendations.length }} {{ t('ep.practice.index') }}</span>
            </div>
            <div v-if="recommendationGroups.length" class="list">
              <div v-for="group in recommendationGroups" :key="group.bank_id" class="list-row">
                <span class="list-main">
                  <span class="list-title">{{ group.bank_name }}</span>
                  <span class="list-meta">
                    <span>{{ t('ep.banks.questions', { count: group.items.length }) }}</span>
                    <span class="od-truncate">{{ reasonSummary(group) }}</span>
                  </span>
                </span>
                <span class="list-side">
                  <button type="button" class="btn btn-sm" :disabled="starting" @click="startRecommendation(group)">
                    {{ t('ep.practice.start') }}
                  </button>
                </span>
              </div>
            </div>
            <div v-else class="empty" style="padding: 24px 0">
              <div class="empty-desc">{{ t('ep.review.diagnosis_empty_hint') }}</div>
            </div>
          </section>
        </template>

        <div v-else class="empty">
          <div class="empty-mark"><LinearIcon name="chart" :size="26" /></div>
          <div class="empty-title">{{ t('ep.review.diagnosis_empty') }}</div>
          <div class="empty-desc">{{ t('ep.review.diagnosis_empty_hint') }}</div>
        </div>
      </section>
    </template>

    <StartStudyPanel
      :show="showStartPanel"
      :sessions="blockedSessions"
      :busy="starting"
      @continue="continueBlocked"
      @end-and-start="endBlockedAndStart"
      @cancel="closeStartPanel"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import { listBanks } from '../api/banks'
import { listDueMistakes, listMistakes, listWeakMistakes, updateMistakeCause as updateMistakeCauseApi } from '../api/mistakes'
import { listKills, killQuestion, unkillQuestion } from '../api/kills'
import { useStartStudy } from '../composables/useStartStudy.js'
import { getLearningTrends, getStudyPlan, getRecommendations } from '../api/learning'
import StartStudyPanel from '../components/StartStudyPanel.vue'
import { mergeReviewQueue, filterReviewRows, reviewReasonLabelKey } from '../domain/reviewQueue.js'
import { readQueryEnum, readQueryString, replaceQueryState } from '../utils/routeQuery.js'

const props = defineProps({ token: { type: String, required: true } })
const emit = defineEmits(['start-session'])
const route = useRoute()
const router = useRouter()
const { t } = useLocale()

// The first four tabs are a hard contract: the Playwright suites click them by
// index. The unified queue therefore lands as a fifth tab and as the default.
const REVIEW_TAB_KEYS = ['due', 'mistakes', 'killed', 'diagnosis', 'all']
const REVIEW_SOURCE_TABS = { all: 'all', due: 'due', mistakes: 'mistakes', killed: 'killed', weak: 'all' }
const DEFAULT_TAB = 'all'
const reasonFilters = [
  { key: 'all', label: 'ep.review.reason_all' },
  { key: 'due', label: 'ep.review.tab_due' },
  { key: 'mistakes', label: 'ep.review.tab_mistakes' },
  { key: 'weak', label: 'ep.review.weak' },
  { key: 'killed', label: 'ep.review.tab_killed' },
]
const QUEUE_EMPTY = {
  all: { title: 'ep.review.queue_empty', hint: 'ep.review.queue_empty_hint' },
  due: { title: 'ep.review.due_empty', hint: 'ep.review.due_empty_hint' },
  mistakes: { title: 'ep.review.mistakes_empty', hint: 'ep.review.mistakes_empty_hint' },
  weak: { title: 'ep.review.weak_empty', hint: 'ep.review.weak_empty_hint' },
  killed: { title: 'ep.review.killed_empty', hint: 'ep.review.killed_empty_hint' },
}
const activeTab = ref(resolveTab(route.query))
const reasonFilter = ref(resolveReasonFilter(route.query))
const banks = ref([])
const dueReviews = ref([])
const mistakes = ref([])
const killed = ref([])
const weakList = ref([])
const trends = ref(null)
const plan = ref(null)
const recommendations = ref([])
const loading = ref(true)
const loadError = ref(false)
const notice = ref('')
const mistakeBank = ref(readQueryString(route.query?.bank))
const mistakeCause = ref(readQueryString(route.query?.cause))
// The unified queue's own URL state: ?q= is a stem filter and ?scope= narrows
// it to one bank (`all` means every bank). Both survive a reload and a pasted
// link, and neither pushes a history entry per keystroke.
const queueQuery = ref(readQueryString(route.query?.q))
const queueScope = ref(readQueryString(route.query?.scope) || 'all')

// Weak flags come from two places: the due payload tags the ones that have a
// due card, and /mistakes/weak lists every flag (due or not). The queue needs
// both, or a question flagged weak today but reviewed tomorrow is invisible.
const weakReviews = computed(() => {
  const seen = new Set()
  const rows = []
  const push = item => {
    const key = `${item.bank_id || ''}::${item.question_id}`
    if (seen.has(key)) return
    seen.add(key)
    rows.push({ ...item, weak: true })
  }
  for (const item of dueReviews.value) {
    if (item.is_weak || item.is_weak_flagged) push(item)
  }
  for (const item of weakList.value) push(item)
  return rows
})

const reviewQueue = computed(() => mergeReviewQueue({
  due: dueReviews.value,
  mistakes: mistakes.value,
  weak: weakReviews.value,
  killed: killed.value,
}))

const filteredQueue = computed(() => filterReviewRows(reviewQueue.value, reasonFilter.value))
const emptyKeys = computed(() => QUEUE_EMPTY[reasonFilter.value] || QUEUE_EMPTY.all)

// ?scope= names a bank; an unknown or stale id falls back to every bank rather
// than showing a permanently empty list.
const resolvedScope = computed(() => {
  if (queueScope.value === 'all') return 'all'
  return banks.value.some(b => b.id === queueScope.value) ? queueScope.value : 'all'
})

const visibleQueue = computed(() => {
  let list = filteredQueue.value
  if (resolvedScope.value !== 'all') list = list.filter(row => row.bank_id === resolvedScope.value)
  const needle = queueQuery.value.trim().toLowerCase()
  if (needle) list = list.filter(row => String(row.stem || '').toLowerCase().includes(needle))
  return list
})

const tabs = computed(() => [
  { key: 'due', label: 'ep.review.tab_due', count: dueReviews.value.length },
  { key: 'mistakes', label: 'ep.review.tab_mistakes', count: mistakes.value.length },
  { key: 'killed', label: 'ep.review.tab_killed', count: killed.value.length },
  { key: 'diagnosis', label: 'ep.review.tab_diagnosis', count: trends.value ? 2 : 0 },
  { key: 'all', label: 'ep.review.tab_all', count: reviewQueue.value.length },
])

const causes = computed(() => [
  { key: '审题遗漏', label: t('ep.review.cause_oversight') },
  { key: '概念欠缺', label: t('ep.review.cause_concept') },
  { key: '思路不熟', label: t('ep.review.cause_thinking') },
  { key: '陷阱诱导', label: t('ep.review.cause_trap') },
  { key: '计算错误', label: t('ep.review.cause_calculation') },
  { key: '其他手误', label: t('ep.review.cause_typo') },
])

const filteredMistakes = computed(() => {
  let list = mistakes.value
  if (mistakeBank.value) list = list.filter(m => m.bank_id === mistakeBank.value)
  if (mistakeCause.value) list = list.filter(m => m.mistake_cause === mistakeCause.value)
  return list
})

const filteredKilled = computed(() => {
  if (!mistakeBank.value) return killed.value
  return killed.value.filter(k => k.bank_id === mistakeBank.value)
})

const dueBankGroups = computed(() => groupByBank(dueReviews.value))

const recommendationGroups = computed(() => groupByBank(recommendations.value, 'question_id'))

// ?tab= names a tab directly; ?source= is the alias used by the queue links
// (source=weak opens the unified queue with the weak filter already on).
// Unknown values fall through to the unified queue.
function resolveTab(query) {
  const tab = readQueryEnum(query?.tab, REVIEW_TAB_KEYS, '')
  if (tab) return tab
  const source = readQueryEnum(query?.source, Object.keys(REVIEW_SOURCE_TABS), '')
  if (source) return REVIEW_SOURCE_TABS[source]
  return DEFAULT_TAB
}

function resolveReasonFilter(query) {
  return readQueryString(query?.source) === 'weak' ? 'weak' : 'all'
}

function groupByBank(items, idKey = 'question_id') {
  const map = {}
  for (const item of items) {
    const key = item.bank_id || 'unknown'
    if (!map[key]) map[key] = { bank_id: key, bank_name: bankName(key), items: [] }
    map[key].items.push(item)
  }
  return Object.values(map)
}

function bankName(id) {
  return banks.value.find(b => b.id === id)?.name || t('ep.common.none')
}

function typeLabel(type) {
  const key = String(type || '').toLowerCase()
  const map = { single: 'single', multi: 'multi', judge: 'judge', fill: 'fill', essay: 'essay', qa: 'essay', short_answer: 'essay', subjective: 'essay' }
  return t('ep.question_types.' + (map[key] || 'single'))
}

function reasonSummary(group) {
  const reasons = [...new Set(group.items.map(i => i.reason).filter(Boolean))]
  return reasons.slice(0, 2).join(' · ')
}

const REVIEW_QUERY_DEFAULTS = { tab: DEFAULT_TAB }

// Toolbar state lives in the URL so a refresh, a browser Back or a pasted link
// lands on the same list. Defaults stay out of the address.
function syncReviewQuery(patch) {
  replaceQueryState(router, route.query, patch, REVIEW_QUERY_DEFAULTS)
}

function selectTab(key) {
  activeTab.value = key
  if (key !== DEFAULT_TAB) reasonFilter.value = 'all'
  // Drop a stale ?source= alias so a reload follows the tab just clicked.
  syncReviewQuery({ tab: key, source: '' })
}

function selectReason(key) {
  reasonFilter.value = key
}

function reasonCount(key) {
  if (key === 'all') return reviewQueue.value.length
  return reviewQueue.value.filter(row => row.reasons.includes(key)).length
}

watch(() => [route.query?.tab, route.query?.source], () => {
  const next = resolveTab(route.query)
  if (next !== activeTab.value) activeTab.value = next
  if (readQueryString(route.query?.source) === 'weak' && reasonFilter.value !== 'weak') {
    reasonFilter.value = 'weak'
  }
})

watch(() => route.query?.bank, value => {
  const next = readQueryString(value)
  if (next !== mistakeBank.value) mistakeBank.value = next
})

watch(() => route.query?.cause, value => {
  const next = readQueryString(value)
  if (next !== mistakeCause.value) mistakeCause.value = next
})

watch(mistakeBank, value => syncReviewQuery({ bank: value }))

watch(mistakeCause, value => syncReviewQuery({ cause: value }))

// The queue filters write with replace, never push: typing must not create one
// history entry per keystroke, and Back must leave the page rather than undo a
// letter. The search box is debounced; the bank select writes immediately.
let queueQueryTimer = null

function flushQueueQuery() {
  if (queueQueryTimer) {
    clearTimeout(queueQueryTimer)
    queueQueryTimer = null
  }
  syncReviewQuery({ q: queueQuery.value.trim() })
}

watch(queueQuery, () => {
  if (queueQueryTimer) clearTimeout(queueQueryTimer)
  queueQueryTimer = setTimeout(flushQueueQuery, 250)
})

watch(queueScope, value => {
  const next = value === 'all' ? '' : value
  syncReviewQuery({ scope: next })
})

// A pasted link or Back/Forward restores both filters into the inputs.
watch(() => [route.query?.q, route.query?.scope], () => {
  const nextQuery = readQueryString(route.query?.q)
  // Compare against the trimmed value so a trailing space the user is typing
  // is not rewritten back out of the input by the echo of our own replace.
  if (nextQuery !== queueQuery.value.trim()) queueQuery.value = nextQuery
  const nextScope = readQueryString(route.query?.scope) || 'all'
  if (nextScope !== queueScope.value) queueScope.value = nextScope
})

onBeforeUnmount(() => {
  if (queueQueryTimer) clearTimeout(queueQueryTimer)
})

async function load() {
  loading.value = true
  loadError.value = false
  notice.value = ''
  const results = await Promise.allSettled([
    listBanks(props.token),
    listDueMistakes(props.token),
    listMistakes(props.token),
    listKills(props.token),
    listWeakMistakes(props.token),
    getLearningTrends(props.token, { window_days: 14 }),
    getStudyPlan(props.token, { days: 7, minutes_per_day: 30 }),
    getRecommendations(props.token, {}),
  ])
  const [bankRes, dueRes, mistakeRes, killRes, weakRes, trendRes, planRes, recRes] = results
  // Only the lists the page is about may blank it. A supplementary source
  // (weak flags, plan, trends) failing must not hide mistakes that loaded fine.
  loadError.value = [bankRes, dueRes, mistakeRes, killRes].some(result => result.status === 'rejected')
  banks.value = bankRes.status === 'fulfilled' ? (bankRes.value || []) : []
  dueReviews.value = dueRes.status === 'fulfilled' ? (dueRes.value || []) : []
  mistakes.value = mistakeRes.status === 'fulfilled' ? (mistakeRes.value || []) : []
  killed.value = killRes.status === 'fulfilled' ? (killRes.value || []) : []
  weakList.value = weakRes.status === 'fulfilled' ? (weakRes.value || []) : []
  trends.value = trendRes.status === 'fulfilled' ? (trendRes.value || null) : null
  plan.value = planRes.status === 'fulfilled' ? (planRes.value || null) : null
  recommendations.value = recRes.status === 'fulfilled' ? (recRes.value || []) : []
  // A link can name a bank this account can no longer see. Fall back to every
  // bank and repair the address instead of leaving a dead filter in the URL.
  if (queueScope.value !== 'all' && !banks.value.some(b => b.id === queueScope.value)) {
    queueScope.value = 'all'
    syncReviewQuery({ scope: '' })
  }
  loading.value = false
}

// Every start button on this page goes through the shared entry: a second
// session of the same mode is never stacked silently behind an old one.
const {
  start: startStudy,
  continueSession,
  endAndStart,
  pending: startPending,
} = useStartStudy(() => props.token)
const showStartPanel = ref(false)
const blockedSessions = ref([])
let blockedPayload = null

const starting = computed(() => startPending.value)

function navigateToSession(session) {
  emit('start-session', session)
}

async function start(mode, bankId, questionIds, bankIds = null) {
  if (!bankId || !questionIds?.length || starting.value) return
  notice.value = ''
  const payload = {
    bank_id: bankId,
    mode,
    question_ids: questionIds,
  }
  if (Array.isArray(bankIds) && bankIds.length > 1) payload.bank_ids = bankIds
  const result = await startStudy(payload, { navigate: navigateToSession })
  if (result?.blocked?.length) {
    blockedSessions.value = result.blocked
    blockedPayload = payload
    showStartPanel.value = true
  } else if (result?.error) {
    notice.value = result.error?.detail || result.error?.message || ''
  }
}

function closeStartPanel() {
  showStartPanel.value = false
  blockedSessions.value = []
  blockedPayload = null
}

function continueBlocked() {
  const [session] = blockedSessions.value
  closeStartPanel()
  if (session) continueSession(session, navigateToSession)
}

async function endBlockedAndStart() {
  const sessions = blockedSessions.value
  const payload = blockedPayload
  showStartPanel.value = false
  blockedSessions.value = []
  blockedPayload = null
  if (!payload) return
  const result = await endAndStart(sessions, payload, navigateToSession)
  if (result?.error) notice.value = result.error?.detail || result.error?.message || ''
}

function uniqueBankIds(items) {
  return [...new Set((items || []).map(item => item.bank_id).filter(Boolean))]
}

function startAll(mode, items) {
  const list = Array.isArray(items) ? items : []
  const bankIds = uniqueBankIds(list)
  if (!bankIds.length) return
  start(mode, bankIds[0], list.map(item => item.question_id), bankIds)
}

function startDueAll() {
  startAll('FSRS', dueReviews.value)
}

function startDueGroup(group) {
  start('FSRS', group.bank_id, group.items.map(i => i.question_id))
}

function startFsrsOne(item) {
  start('FSRS', item.bank_id, [item.question_id])
}

// The merged row can carry several reasons; the strongest scheduling reason
// decides which session mode the row starts in.
function queueStartMode(row) {
  if (row.reasons.includes('due') || row.reasons.includes('weak')) return 'FSRS'
  if (row.reasons.includes('mistakes')) return 'MISTAKE'
  if (row.reasons.includes('killed')) return 'ELIMINATION'
  return 'FSRS'
}

function startQueueRow(row) {
  start(queueStartMode(row), row.bank_id, [row.question_id])
}

function startMistakeAll() {
  startAll('MISTAKE', filteredMistakes.value)
}

function startMistakeOne(item) {
  start('MISTAKE', item.bank_id, [item.question_id])
}

function startKilledAll() {
  startAll('ELIMINATION', filteredKilled.value)
}

function startPlanDay(day) {
  const tasks = Array.isArray(day.bank_tasks)
    ? day.bank_tasks.filter(task => task?.bank_id && Array.isArray(task.question_ids) && task.question_ids.length)
    : []
  if (tasks.length) {
    const bankIds = [...new Set(tasks.map(task => task.bank_id))]
    const questionIds = [...new Set(tasks.flatMap(task => task.question_ids))]
    start('PRACTICE', bankIds[0], questionIds, bankIds)
    return
  }
  if (day.question_ids?.length) start('PRACTICE', day.bank_id, day.question_ids)
}

function startRecommendation(group) {
  start('PRACTICE', group.bank_id, group.items.map(i => i.question_id))
}

async function setCause(item, cause) {
  const previous = item.mistake_cause || ''
  item.mistake_cause = cause
  try {
    await updateMistakeCauseApi(props.token, item.question_id, cause)
  } catch (err) {
    item.mistake_cause = previous
    notice.value = err.detail || err.message
  }
}

async function kill(questionId) {
  try {
    await killQuestion(props.token, questionId)
    mistakes.value = mistakes.value.filter(m => m.question_id !== questionId)
    dueReviews.value = dueReviews.value.filter(d => d.question_id !== questionId)
    killed.value = await listKills(props.token).catch(() => killed.value)
  } catch (err) {
    notice.value = err.detail || err.message
  }
}

async function restore(questionId) {
  try {
    await unkillQuestion(props.token, questionId)
    killed.value = killed.value.filter(k => k.question_id !== questionId)
  } catch (err) {
    notice.value = err.detail || err.message
  }
}

onMounted(load)
</script>

<style scoped>
.review-page { padding-top: 0; }
.review-workspace { width: 100%; max-width: 100%; min-width: 0; }
.review-hub-main,
.review-hub-rail { min-width: 0; }
.review-page .page-eyebrow,
.review-page .panel-title { font-size: 12px; }
.review-page .tag,
.review-page .rule-label,
.review-page .hint,
.review-page .stat-cap,
.review-page .list-meta,
.review-page .section-note { font-size: 12px; }
.review-notice { margin-top: 16px; }
.review-load-error .btn { margin-left: auto; flex: none; }
.review-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 56px; margin-top: 24px; align-items: start; }
.review-main { min-width: 0; }
.review-single { margin-top: 18px; }
.review-stats { margin-bottom: 20px; }
.review-rail { border-left: 1px solid var(--line); padding: 4px 0 0 22px; }
.rail-block + .rail-block { margin-top: 26px; }
.rail-title { font-size: 12px; font-weight: 600; letter-spacing: .06em; color: var(--ink-2); }
.rail-note { margin: 7px 0 12px; font-size: 12px; line-height: 1.7; color: var(--ink-3); }
.review-toolbar { border-top: 0; margin-top: 0; }
.review-queue-toolbar { flex-wrap: wrap; gap: 12px; }
.review-queue-row { align-items: flex-start; }
.review-reason-tag { margin-left: 2px; }
.review-queue-search { flex: 0 1 220px; min-width: 140px; }
.review-scope { display: inline-flex; align-items: center; gap: 8px; flex: none; }
.review-scope .select { height: 32px; font-size: 12px; }
.review-reason-chip .count { margin-left: 6px; font-family: var(--font-mono); font-size: 12px; color: var(--ink-4); font-weight: 400; }
.due-row, .mistake-row { align-items: flex-start; }
.qtype { font-size: 12px; letter-spacing: .04em; color: var(--ink-3); width: 52px; flex: none; padding-top: 3px; }
.qrow-stem {
  display: block;
  font-family: var(--font-serif);
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--ink);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.mistake-actions { gap: 4px; flex-wrap: wrap; justify-content: flex-end; }
.cause-select { height: 32px; font-size: 12px; width: 112px; }
.diagnosis-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 32px; margin: 4px 0 24px; }
.rank, .day-no { font-size: 12px; color: var(--ink-4); width: 28px; flex: none; }
.plan-row .list-side { margin-left: 12px; }
@media (max-width: 1280px) {
  .review-layout { gap: 40px; }
}
@media (max-width: 1100px) {
  .review-layout { grid-template-columns: minmax(0, 1fr); gap: 28px; }
  .review-rail {
    border-left: 0;
    border-top: 1px solid var(--line-strong);
    padding: 20px 0 0;
  }
}
@media (max-width: 900px) {
  .diagnosis-grid { grid-template-columns: minmax(0, 1fr); gap: 20px; }
  .review-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .mistake-row { flex-wrap: wrap; }
  .mistake-actions { width: 100%; justify-content: flex-start; padding-left: 52px; }
  .cause-select { width: 104px; }
  .review-page .page-actions .btn { width: 100%; }
}
</style>
