<template>
  <main class="mistakes-page">
    <header class="page-header mistakes-header">
      <div class="header-left">
        <button type="button" class="btn-back" @click="$emit('back')">← {{ t('common.back') }}</button>
        <div>
          <h1>{{ currentTab === 'mistakes' ? t('mistakes.title') : t('mistakes.subtitle') }}</h1>
          <p v-if="currentTab === 'mistakes'">
            {{ selectedBankName ? `【${selectedBankName}】` : t('ui.k0717') }}{{ t('ui.k0157') }} {{ filteredMistakes.length }} {{ t('ui.k0473') }} {{ filteredDueReviews.length }} {{ t('ui.k0474') }}
          </p>
          <p v-else>
            {{ selectedBankName ? `【${selectedBankName}】` : t('ui.k0717') }}{{ t('ui.k0157') }} {{ filteredKilled.length }} {{ t('ui.k0475') }}
          </p>
        </div>
      </div>
      <nav class="view-tabs">
        <button type="button" :class="{ active: currentTab === 'mistakes' }" @click="switchTab('mistakes')">{{ t('ui.k0476') }}</button>
        <button type="button" :class="{ active: currentTab === 'kills' }" @click="switchTab('kills')">{{ t('ui.k0477') }}</button>
      </nav>
    </header>

    <!-- 题库范围过滤条 -->
    <div class="mistake-filter-bar">
      <div class="bank-selector">
        <label for="bank-filter">{{ t('mistakes.filter_bank') }}</label>
        <select id="bank-filter" v-model="selectedBankId">
          <option value="">{{ t('common.all') }} ({{ banks.length }})</option>
          <option v-for="b in banks" :key="b.id" :value="b.id">{{ b.name }}</option>
        </select>
      </div>
    </div>

    <!-- 刷题行动发射台 (Practice Launchpad) - 软件以刷题为最高优先级 -->
    <section v-if="!loading && !error" class="practice-launchpad" :class="{ 'single-col': currentTab !== 'mistakes' }">
      <!-- 错题歼灭攻坚卡片 -->
      <template v-if="currentTab === 'mistakes'">
        <article class="launchpad-card attack-card">
          <div class="launchpad-top">
            <div class="launchpad-icon-gem attack-gem">
              <LinearIcon name="target" size="20" />
            </div>
            <div class="launchpad-header-meta">
              <span class="launchpad-tag">{{ t('mistakes.launchpad_attack_tag') }}</span>
              <h2 class="launchpad-title">{{ t('mistakes.launchpad_attack_title') }}</h2>
            </div>
          </div>
          <div class="launchpad-body">
            <div class="launchpad-number-row">
              <span class="launchpad-number font-mono-code">{{ filteredMistakes.length }}</span>
              <span class="launchpad-unit">{{ t('mistakes.launchpad_unit_questions') }}</span>
              <span v-if="selectedBankName" class="launchpad-scope-pill">{{ selectedBankName }}</span>
            </div>
            <p class="launchpad-desc">{{ t('mistakes.launchpad_attack_desc') }}</p>
          </div>
          <button
            type="button"
            class="primary launchpad-hero-btn"
            :disabled="filteredMistakes.length === 0 || startingSession"
            @click="handleTriggerMistakes"
          >
            <LinearIcon name="play" size="16" />
            <span>{{ startingSession ? t('ui.k0718') : t('mistakes.btn_start_attack', { count: filteredMistakes.length }) }}</span>
          </button>
        </article>

        <!-- FSRS 到期复习卡片 -->
        <article class="launchpad-card fsrs-card">
          <div class="launchpad-top">
            <div class="launchpad-icon-gem fsrs-gem">
              <LinearIcon name="clock" size="20" />
            </div>
            <div class="launchpad-header-meta">
              <span class="launchpad-tag">{{ t('mistakes.launchpad_fsrs_tag') }}</span>
              <h2 class="launchpad-title">{{ t('mistakes.launchpad_fsrs_title') }}</h2>
            </div>
          </div>
          <div class="launchpad-body">
            <div class="launchpad-number-row">
              <span class="launchpad-number font-mono-code">{{ filteredDueReviews.length }}</span>
              <span class="launchpad-unit">{{ t('mistakes.launchpad_unit_due') }}</span>
              <span v-if="filteredDueReviews.length === 0" class="launchpad-all-clear">
                <LinearIcon name="check" size="13" /> {{ t('mistakes.fsrs_all_clear') }}
              </span>
            </div>
            <p class="launchpad-desc">{{ t('mistakes.launchpad_fsrs_desc') }}</p>
          </div>
          <button
            type="button"
            class="primary launchpad-hero-btn fsrs-btn"
            :disabled="filteredDueReviews.length === 0 || startingSession"
            @click="handleTriggerDueFsrs"
          >
            <LinearIcon name="zap" size="16" />
            <span>{{ startingSession ? t('ui.k0718') : t('mistakes.btn_start_fsrs', { count: filteredDueReviews.length }) }}</span>
          </button>
        </article>
      </template>

      <!-- 斩杀查漏补缺卡片 -->
      <template v-else>
        <article class="launchpad-card kill-card">
          <div class="launchpad-top">
            <div class="launchpad-icon-gem kill-gem">
              <LinearIcon name="award" size="20" />
            </div>
            <div class="launchpad-header-meta">
              <span class="launchpad-tag">{{ t('mistakes.launchpad_kill_tag') }}</span>
              <h2 class="launchpad-title">{{ t('mistakes.launchpad_kill_title') }}</h2>
            </div>
          </div>
          <div class="launchpad-body">
            <div class="launchpad-number-row">
              <span class="launchpad-number font-mono-code">{{ filteredKilled.length }}</span>
              <span class="launchpad-unit">{{ t('mistakes.launchpad_unit_killed') }}</span>
            </div>
            <p class="launchpad-desc">{{ t('mistakes.launchpad_kill_desc') }}</p>
          </div>
          <button
            type="button"
            class="primary launchpad-hero-btn kill-btn-hero"
            :disabled="filteredKilled.length === 0 || startingSession"
            @click="handleTriggerElimination"
          >
            <LinearIcon name="play" size="16" />
            <span>{{ startingSession ? t('ui.k0718') : t('mistakes.btn_start_kill_review', { count: filteredKilled.length }) }}</span>
          </button>
        </article>
      </template>
    </section>

    <p v-if="loading">{{ t('ui.k0481') }}</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <!-- 次级区域：错题明细清单（支持按需展开查看） -->
    <section v-if="!loading && !error" class="mistake-detail-wrapper">
      <div class="mistake-list-header">
        <div class="list-header-left">
          <h3 class="list-title">
            <LinearIcon name="layers" size="15" />
            <span>{{ currentTab === 'mistakes' ? t('mistakes.detail_list_title') : t('mistakes.killed_list_title') }}</span>
            <span class="list-count font-mono-code">({{ currentTab === 'mistakes' ? filteredMistakes.length : filteredKilled.length }})</span>
          </h3>
          <p class="list-sub">{{ t('mistakes.detail_list_hint') }}</p>
        </div>
        <div class="list-header-right">
          <div v-if="showDetailList" class="view-mode-toggle">
            <button
              type="button"
              class="mode-btn"
              :class="{ active: viewMode === 'table' }"
              @click="setMistakesViewMode('table')"
              :title="t('mistakes.mode_table')"
            >
              <LinearIcon name="list" size="13" />
              <span>{{ t('mistakes.mode_table') }}</span>
            </button>
            <button
              type="button"
              class="mode-btn"
              :class="{ active: viewMode === 'card' }"
              @click="setMistakesViewMode('card')"
              :title="t('mistakes.mode_card')"
            >
              <LinearIcon name="grid" size="13" />
              <span>{{ t('mistakes.mode_card') }}</span>
            </button>
          </div>
          <button type="button" class="btn-toggle-list" @click="showDetailList = !showDetailList">
            <span>{{ showDetailList ? t('mistakes.collapse_list') : t('mistakes.expand_list') }}</span>
            <LinearIcon name="chevron-right" size="13" :style="{ transform: showDetailList ? 'rotate(90deg)' : 'none', transition: 'transform 150ms ease' }" />
          </button>
        </div>
      </div>

      <div v-if="showDetailList" class="detail-list-content">
        <!-- 错题与到期复习列表 -->
        <template v-if="currentTab === 'mistakes'">
          <!-- 紧凑表格模式 -->
          <div v-if="viewMode === 'table'" class="mistakes-table-container">
            <table class="mistakes-table">
              <thead>
                <tr>
                  <th style="width: 75px;">{{ t('mistakes.col_type') }}</th>
                  <th style="width: 140px;">{{ t('mistakes.col_bank') }}</th>
                  <th>{{ t('mistakes.col_stem') }}</th>
                  <th style="width: 150px;">{{ t('mistakes.col_stats') }}</th>
                  <th style="width: 130px;">{{ t('mistakes.col_cause') }}</th>
                  <th style="width: 190px; text-align: right;">{{ t('mistakes.col_actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredMistakes" :key="item.question_id" class="mistake-table-row">
                  <td>
                    <span class="badge font-mono-code">{{ item.type }}</span>
                  </td>
                  <td>
                    <span class="badge-bank truncate-text" :title="getBankName(item.bank_id)">{{ getBankName(item.bank_id) }}</span>
                  </td>
                  <td class="stem-cell">
                    <div class="table-stem-text" :title="item.stem">{{ item.stem }}</div>
                  </td>
                  <td>
                    <div class="table-stats-cell">
                      <span class="stat-tag error-tag">{{ t('ui.k0075') }} {{ item.mistake_count }}</span>
                      <span v-if="item.is_due" class="stat-tag due-tag">{{ t('ui.k0724') }}</span>
                    </div>
                  </td>
                  <td>
                    <select class="table-cause-select" :value="item.mistake_cause || ''" @change="updateMistakeCause(item, $event.target.value)">
                      <option value="">{{ t('ui.k0490') }}</option>
                      <option v-for="c in mistakeCauses" :key="c.key" :value="c.key">{{ c.label }}</option>
                    </select>
                  </td>
                  <td style="text-align: right;">
                    <div class="table-row-actions">
                      <button type="button" class="btn-table-action" @click="startMistakesPractice(item)">{{ t('ui.k0491') }}</button>
                      <button v-if="item.is_due" type="button" class="btn-table-action primary" @click="startSingleFsrs(item)">{{ t('ui.k0412') }}</button>
                      <button type="button" class="btn-table-action kill-btn" @click="handleKill(item.question_id)">{{ t('ui.k0486') }}</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredMistakes.length" class="empty-state-card">
              <span class="empty-icon"><LinearIcon name="check" size="24" /></span>
              <h3>{{ t('ui.k0492') }}</h3>
              <p>{{ t('ui.k0493') }}</p>
              <button type="button" class="primary" @click="$emit('back')">{{ t('ui.k0494') }}</button>
            </div>
          </div>

          <!-- 传统大卡片模式 -->
          <div v-else class="cards-view-wrapper">
            <!-- 到期卡片高亮区（若包含薄弱标记题） -->
            <section v-if="weakOnlyDueReviews.length > 0" class="due-section">
              <h3 class="section-title">
                <LinearIcon name="target" size="14" /> {{ t('ui.k0482') }}{{ weakOnlyDueReviews.length }})
              </h3>
              <div class="bank-grid">
                <article v-for="item in weakOnlyDueReviews" :key="'weak-' + item.question_id" class="bank-card mistake-card due-highlight">
                  <div class="card-meta">
                    <span class="badge">{{ item.type }}</span>
                    <span class="badge-bank">{{ getBankName(item.bank_id) }}</span>
                    <span class="badge-due due">{{ t('ui.k0483') }}</span>
                  </div>
                  <h2>{{ item.stem }}</h2>
                  <div class="mistake-detail">
                    <p>{{ t('ui.k0484') }}</p>
                  </div>
                  <div class="card-actions">
                    <button type="button" class="primary" @click="startSingleFsrs(item)">{{ t('ui.k0485') }}</button>
                    <button type="button" class="kill-btn" @click="handleKill(item.question_id)">{{ t('ui.k0486') }}</button>
                  </div>
                </article>
              </div>
            </section>

            <section class="mistakes-section">
              <h3 v-if="weakOnlyDueReviews.length > 0" class="section-title">
                <LinearIcon name="draft" size="14" /> {{ t('ui.k0487') }}{{ filteredMistakes.length }})
              </h3>
              <div class="bank-grid">
                <article v-for="item in filteredMistakes" :key="item.question_id" class="bank-card mistake-card">
                  <div class="card-meta">
                    <span class="badge">{{ item.type }}</span>
                    <span class="badge-bank">{{ getBankName(item.bank_id) }}</span>
                    <span class="badge-due" :class="{ due: item.is_due }">{{ item.is_due ? t('ui.k0724') : t('ui.k0725') }}</span>
                  </div>
                  <h2>{{ item.stem }}</h2>
                  <div class="mistake-detail">
                    <p>{{ t('ui.k0075') }} {{ item.mistake_count }} {{ t('ui.k0488') }} {{ item.consecutive_correct || 0 }} {{ t('ui.k0394') }}</p>
                    <label class="cause-label">
                      <span>{{ t('ui.k0489') }}</span>
                      <select :value="item.mistake_cause || ''" @change="updateMistakeCause(item, $event.target.value)">
                        <option value="">{{ t('ui.k0490') }}</option>
                        <option v-for="c in mistakeCauses" :key="c.key" :value="c.key">{{ c.label }}</option>
                      </select>
                    </label>
                  </div>
                  <div class="card-actions">
                    <button type="button" @click="startMistakesPractice(item)">{{ t('ui.k0491') }}</button>
                    <button v-if="item.is_due" type="button" class="primary" @click="startSingleFsrs(item)">{{ t('ui.k0412') }}</button>
                    <button type="button" class="kill-btn" @click="handleKill(item.question_id)">{{ t('ui.k0486') }}</button>
                  </div>
                </article>
              </div>
              <div v-if="!filteredMistakes.length && !weakOnlyDueReviews.length" class="empty-state-card">
                <span class="empty-icon">
                  <LinearIcon name="check" size="24" />
                </span>
                <h3>{{ t('ui.k0492') }}</h3>
                <p>{{ t('ui.k0493') }}</p>
                <button type="button" class="primary" @click="$emit('back')">{{ t('ui.k0494') }}</button>
              </div>
            </section>
          </div>
        </template>

        <!-- 斩杀题库列表 -->
        <template v-else>
          <!-- 斩杀表格模式 -->
          <div v-if="viewMode === 'table'" class="mistakes-table-container">
            <table class="mistakes-table">
              <thead>
                <tr>
                  <th style="width: 75px;">{{ t('mistakes.col_type') }}</th>
                  <th style="width: 140px;">{{ t('mistakes.col_bank') }}</th>
                  <th>{{ t('mistakes.col_stem') }}</th>
                  <th style="width: 140px;">{{ t('common.status') }}</th>
                  <th style="width: 180px; text-align: right;">{{ t('mistakes.col_actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredKilled" :key="item.question_id" class="mistake-table-row">
                  <td><span class="badge font-mono-code">{{ item.type }}</span></td>
                  <td><span class="badge-bank truncate-text" :title="getBankName(item.bank_id)">{{ getBankName(item.bank_id) }}</span></td>
                  <td class="stem-cell"><div class="table-stem-text" :title="item.stem">{{ item.stem }}</div></td>
                  <td><small class="muted font-mono-code">{{ item.killed_at ? item.killed_at.slice(0, 10) : t('ui.k0727') }}</small></td>
                  <td style="text-align: right;">
                    <div class="table-row-actions">
                      <button type="button" class="btn-table-action" @click="startEliminationPractice(item)">{{ t('ui.k0495') }}</button>
                      <button type="button" class="btn-table-action" @click="handleUnkill(item.question_id)">{{ t('ui.k0496') }}</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredKilled.length" class="empty-state-card">
              <span class="empty-icon"><LinearIcon name="zap" size="28" /></span>
              <h3>{{ t('ui.k0497') }}</h3>
              <p>{{ t('ui.k0498') }}</p>
              <button type="button" class="primary" @click="$emit('back')">{{ t('ui.k0499') }}</button>
            </div>
          </div>

          <!-- 斩杀卡片模式 -->
          <section v-else class="bank-grid">
            <article v-for="item in filteredKilled" :key="item.question_id" class="bank-card killed-card">
              <div class="card-meta">
                <span class="badge">{{ item.type }}</span>
                <span class="badge-bank">{{ getBankName(item.bank_id) }}</span>
                <small class="muted">{{ item.killed_at ? `${t('ui.k0726')} ${item.killed_at.slice(0, 10)}` : t('ui.k0727') }}</small>
              </div>
              <h2>{{ item.stem }}</h2>
              <div class="card-actions">
                <button type="button" @click="startEliminationPractice(item)">{{ t('ui.k0495') }}</button>
                <button type="button" @click="handleUnkill(item.question_id)">{{ t('ui.k0496') }}</button>
              </div>
            </article>
            <div v-if="!filteredKilled.length" class="empty-state-card">
              <span class="empty-icon"><LinearIcon name="zap" size="28" /></span>
              <h3>{{ t('ui.k0497') }}</h3>
              <p>{{ t('ui.k0498') }}</p>
              <button type="button" class="primary" @click="$emit('back')">{{ t('ui.k0499') }}</button>
            </div>
          </section>
        </template>
      </div>
    </section>

    <!-- 跨题库选择弹窗 -->
    <div v-if="showBankPicker" class="exam-setup-backdrop" @click.self="showBankPicker = false">
      <div class="exam-setup-dialog" style="width: min(100%, 28rem);">
        <h2>{{ t('mistakes.select_bank_title') }}</h2>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem;">
          {{ t('mistakes.select_bank_desc') }}
        </p>
        <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 50vh; overflow-y: auto;">
          <button
            v-for="g in currentPickerGroups"
            :key="g.bank_id"
            type="button"
            class="secondary-btn"
            style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.85rem; text-align: left;"
            @click="handleSelectBankPicker(g)"
          >
            <strong style="color: var(--text-main);">{{ g.bank_name }}</strong>
            <span class="badge" style="font-family: var(--linear-mono);">{{ t('mistakes.questions_unit', { count: g.items.length }) }}</span>
          </button>
        </div>
        <div class="bank-actions" style="margin-top: 1rem;">
          <button type="button" @click="showBankPicker = false">{{ t('common.cancel') }}</button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import { listDueMistakes, listMistakes, updateMistakeCause as updateMistakeCauseApi } from '../api/mistakes'
import { listKills, killQuestion, unkillQuestion } from '../api/kills'
import { listBanks } from '../api/banks'
import { startSession } from '../api/practice'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

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
const showDetailList = ref(true)
const viewMode = ref('card')
try {
  const saved = localStorage.getItem('easyexam_mistakes_view_mode')
  if (saved === 'card' || saved === 'table') viewMode.value = saved
} catch (_) {}

function setMistakesViewMode(mode) {
  viewMode.value = mode
  try {
    localStorage.setItem('easyexam_mistakes_view_mode', mode)
  } catch (_) {}
}

const mistakeCauses = computed(() => [
  { key: '审题遗漏', label: t('mistakes.cause_oversight') },
  { key: '概念欠缺', label: t('mistakes.cause_concept') },
  { key: '思路不熟', label: t('mistakes.cause_thinking') },
  { key: '陷阱诱导', label: t('mistakes.cause_trap') },
  { key: '计算错误', label: t('mistakes.cause_calculation') },
  { key: '其他手误', label: t('mistakes.cause_typo') },
])

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

const showBankPicker = ref(false)
const pickerMode = ref('FSRS')

const currentPickerGroups = computed(() => {
  if (pickerMode.value === 'FSRS') return dueReviewsByBank.value
  if (pickerMode.value === 'MISTAKE') return mistakesByBank.value
  return killedByBank.value
})

function handleTriggerDueFsrs() {
  if (selectedBankId.value || dueReviewsByBank.value.length <= 1) {
    void startDueFsrs()
  } else {
    pickerMode.value = 'FSRS'
    showBankPicker.value = true
  }
}

function handleTriggerMistakes() {
  if (selectedBankId.value || mistakesByBank.value.length <= 1) {
    void startMistakesPractice()
  } else {
    pickerMode.value = 'MISTAKE'
    showBankPicker.value = true
  }
}

function handleTriggerElimination() {
  if (selectedBankId.value || killedByBank.value.length <= 1) {
    void startEliminationPractice()
  } else {
    pickerMode.value = 'ELIMINATION'
    showBankPicker.value = true
  }
}

function handleSelectBankPicker(group) {
  showBankPicker.value = false
  if (pickerMode.value === 'FSRS') {
    void startDueFsrs(group)
  } else if (pickerMode.value === 'MISTAKE') {
    void startMistakesPractice(null, group)
  } else if (pickerMode.value === 'ELIMINATION') {
    void startEliminationPractice(null, group)
  }
}

function getBankName(bankId) {
  const b = banks.value.find(item => item.id === bankId)
  return b ? b.name : t('ui.k0453')
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
    alert(`${t('ui.k0506')}${err.detail || err.message}`)
  }
}

async function handleUnkill(questionId) {
  try {
    await unkillQuestion(props.token, questionId)
    killedList.value = killedList.value.filter(k => k.question_id !== questionId)
    void loadData()
  } catch (err) {
    alert(`${t('ui.k0507')}${err.detail || err.message}`)
  }
}

async function updateMistakeCause(item, cause) {
  item.mistake_cause = cause
  try {
    await updateMistakeCauseApi(props.token, item.question_id, cause)
  } catch (err) {
    error.value = `${t('ui.k0508')}${err.detail || err.message}`
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
    error.value = t('ui.k0509')
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
  display: inline-flex;
  background: var(--bg-muted);
  padding: 0.25rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  gap: 0.25rem;
}

.view-tabs button {
  padding: 0.4rem 0.95rem;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-weight: 500;
  font-size: 0.875rem;
  transition: all 0.15s ease;
}

.view-tabs button.active {
  background: var(--bg-card);
  color: var(--primary);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.empty-state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1.5rem;
  background: var(--bg-card);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-xl);
  text-align: center;
  margin-top: 1rem;
}

.empty-state-box .empty-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.empty-state-box h3 {
  font-size: 1.15rem;
  color: var(--text-main);
  margin-bottom: 0.35rem;
}

.empty-state-box p {
  font-size: 0.875rem;
  color: var(--text-muted);
  max-width: 24rem;
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
  background: var(--bg-subtle);
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

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.empty-state-card {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3.5rem 1.5rem;
  background: var(--bg-card);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-xl);
  text-align: center;
  gap: 0.75rem;
  max-width: 32rem;
  margin: 2rem auto;
}

.empty-state-card .empty-icon {
  font-size: 2.75rem;
}

.empty-state-card h3 {
  font-size: 1.25rem;
  color: var(--text-main);
  margin: 0;
}

.empty-state-card p {
  font-size: 0.9rem;
  color: var(--text-muted);
  max-width: 24rem;
  line-height: 1.5;
  margin: 0 0 0.5rem 0;
}

/* ==========================================================================
   Practice Launchpad (刷题行动发射台)
   ========================================================================== */
.mistake-filter-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 1rem;
}

.mistake-filter-bar .bank-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-card);
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}

.mistake-filter-bar .bank-selector label {
  font-size: 0.8rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.mistake-filter-bar .bank-selector select {
  border: none;
  background: transparent;
  color: var(--text-main);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  outline: none;
}

.practice-launchpad {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.practice-launchpad.single-col {
  grid-template-columns: 1fr;
  max-width: 48rem;
}

.launchpad-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 1.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 16px -4px rgba(0, 0, 0, 0.08);
  transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
  position: relative;
  overflow: hidden;
}

.launchpad-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.12);
  border-color: var(--primary-border);
}

.launchpad-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}

.attack-card::before {
  background: linear-gradient(90deg, #f97316, #ef4444);
}

.fsrs-card::before {
  background: linear-gradient(90deg, #3b82f6, #06b6d4);
}

.kill-card::before {
  background: linear-gradient(90deg, #8b5cf6, #ec4899);
}

.launchpad-top {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-bottom: 1.25rem;
}

.launchpad-icon-gem {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.attack-gem {
  background: rgba(249, 115, 22, 0.12);
  color: #f97316;
  border: 1px solid rgba(249, 115, 22, 0.25);
}

.fsrs-gem {
  background: rgba(6, 182, 212, 0.12);
  color: #06b6d4;
  border: 1px solid rgba(6, 182, 212, 0.25);
}

.kill-gem {
  background: rgba(139, 92, 246, 0.12);
  color: #8b5cf6;
  border: 1px solid rgba(139, 92, 246, 0.25);
}

.launchpad-header-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.launchpad-tag {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
}

.launchpad-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-main);
  margin: 0;
  letter-spacing: -0.01em;
}

.launchpad-body {
  margin-bottom: 1.5rem;
}

.launchpad-number-row {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.launchpad-number {
  font-size: 2.25rem;
  font-weight: 800;
  line-height: 1;
  color: var(--text-main);
  letter-spacing: -0.03em;
}

.launchpad-unit {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-muted);
}

.launchpad-scope-pill {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  color: var(--text-muted);
  max-width: 14rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.launchpad-all-clear {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--success-light);
  color: var(--success);
  font-weight: 600;
}

.launchpad-desc {
  font-size: 0.825rem;
  color: var(--text-muted);
  line-height: 1.45;
  margin: 0;
}

.launchpad-hero-btn {
  width: 100%;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 120ms ease;
}

.launchpad-hero-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.16);
}

.fsrs-btn {
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
  border-color: transparent;
}

.fsrs-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #0284c7, #0891b2);
}

.kill-btn-hero {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
  border-color: transparent;
}

/* ==========================================================================
   次级区域：错题明细清单
   ========================================================================== */
.mistake-detail-wrapper {
  margin-top: 1rem;
  border-top: 1px dashed var(--border-strong);
  padding-top: 1.25rem;
}

.mistake-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  gap: 1rem;
}

.list-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.list-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-main);
  margin: 0;
}

.list-count {
  font-size: 0.85rem;
  color: var(--text-tertiary);
  font-weight: normal;
}

.list-sub {
  font-size: 0.78rem;
  color: var(--text-tertiary);
  margin: 0;
}

.btn-toggle-list {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.85rem;
  font-size: 0.8rem;
  font-weight: 500;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 120ms ease;
}

.btn-toggle-list:hover {
  background: var(--bg-subtle);
  color: var(--text-main);
  border-color: var(--border-strong);
}

.list-header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.view-mode-toggle {
  display: flex;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 2px;
  gap: 2px;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.65rem;
  font-size: 0.75rem;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 120ms ease;
}

.mode-btn:hover {
  color: var(--text-main);
}

.mode-btn.active {
  background: var(--bg-card);
  color: var(--primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* 紧凑表格视图样式 */
.mistakes-table-container {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow-x: auto;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

.mistakes-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.mistakes-table th {
  padding: 0.65rem 0.85rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.mistakes-table td {
  padding: 0.55rem 0.85rem;
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
  font-size: 0.85rem;
}

.mistake-table-row:hover td {
  background: var(--bg-hover, rgba(0, 0, 0, 0.02));
}

.table-stem-text {
  max-width: 32rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
  font-weight: 500;
  line-height: 1.4;
}

.table-stats-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.stat-tag {
  font-size: 0.72rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-family: var(--linear-mono);
}

.stat-tag.error-tag {
  background: var(--danger-light);
  color: var(--danger);
  border: 1px solid var(--danger-border);
}

.stat-tag.due-tag {
  background: var(--warning-light);
  color: var(--warning);
  border: 1px solid var(--warning-border);
}

.table-cause-select {
  font-size: 0.78rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-page);
  color: var(--text-main);
  max-width: 120px;
}

.table-row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.4rem;
}

.btn-table-action {
  padding: 0.28rem 0.6rem;
  font-size: 0.78rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-main);
  cursor: pointer;
  white-space: nowrap;
  transition: all 120ms ease;
}

.btn-table-action:hover {
  background: var(--bg-subtle);
  border-color: var(--border-strong);
}

.btn-table-action.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.btn-table-action.primary:hover {
  background: var(--primary-hover);
}

.btn-table-action.kill-btn {
  background: var(--danger-light);
  border-color: var(--danger-border);
  color: var(--danger);
}

.btn-table-action.kill-btn:hover {
  background: var(--danger);
  color: #fff;
}

/* ==========================================================================
   半屏与竖长窄屏自适应响应式断点 (Half-screen Split Responsive)
   ========================================================================== */
@media (max-width: 1024px) {
  .practice-launchpad {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
}

@media (max-width: 768px) {
  .mistakes-page {
    width: 100%;
    padding: 0.75rem;
  }
  .mistake-list-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }
  .btn-toggle-list {
    width: 100%;
    justify-content: center;
  }
  .launchpad-card {
    padding: 1.25rem 1rem;
  }
  .launchpad-number {
    font-size: 1.85rem;
  }
}
</style>
