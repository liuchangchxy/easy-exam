<template>
  <main class="bank-manage-page">
    <!-- 头部信息 -->
    <header class="bank-manage-header">
      <div class="header-nav-row">
        <button
          type="button"
          class="btn-back-home secondary-btn"
          @click="router.push('/')"
        >
          <LinearIcon name="chevron-left" size="14" />
          <span>{{ t('bank_manage.back_home') }}</span>
        </button>
      </div>

      <div class="header-title-row">
        <div class="title-details">
          <div class="title-badge-group">
            <span class="bank-icon-wrap">
              <LinearIcon name="layers" size="18" />
            </span>
            <h1 class="bank-title-text">{{ bank?.name || t('bank_manage.title') }}</h1>
            <span v-if="bank?.category" class="category-pill">{{ bank.category }}</span>
          </div>
          <p v-if="bank?.description" class="bank-desc-text">{{ bank.description }}</p>
        </div>

        <div class="meta-badges">
          <span class="count-pill">
            <LinearIcon name="list" size="12" />
            {{ t('home.questions_count', { count: questions.length }) }}
          </span>
          <span
            class="role-pill"
            :class="{
              'role-admin': bank?.role === 'ADMIN',
              'role-editor': bank?.role === 'EDITOR',
              'role-member': bank?.role === 'MEMBER',
            }"
          >
            {{ formatRole(bank?.role) }}
          </span>
        </div>
      </div>
    </header>

    <!-- 模考进行中只读保护横幅 (Active Exam Safety Banner) -->
    <section v-if="hasActiveExam" class="active-exam-alert" data-testid="active-exam-alert">
      <div class="alert-icon">
        <LinearIcon name="award" size="18" />
      </div>
      <div class="alert-content">
        <strong>{{ t('bank_manage.exam_readonly_tip') }}</strong>
        <p>{{ t('bank_manage.active_exam_warning') }}</p>
      </div>
    </section>

    <!-- 成功提示消息 -->
    <div v-if="successToast" class="toast-success-banner" role="status">
      <LinearIcon name="check" size="14" />
      <span>{{ successToast }}</span>
    </div>

    <!-- 冲突警告消息 -->
    <div v-if="conflictAlert" class="conflict-alert-banner" role="alert" data-testid="conflict-alert-banner">
      <div class="alert-content">
        <LinearIcon name="award" size="16" />
        <span>{{ conflictAlert }}</span>
        <button type="button" class="btn-conflict-reload" @click="loadData">
          {{ t('bank_manage.reload_latest') }}
        </button>
      </div>
      <button type="button" class="btn-close-toast" @click="conflictAlert = ''">
        <LinearIcon name="x" size="12" />
      </button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="alert-error-banner" role="alert">
      {{ error }}
    </div>

    <!-- 搜索与筛选工具栏 -->
    <section class="filter-toolbar-section">
      <div class="search-input-wrap">
        <span class="search-icon">
          <LinearIcon name="search" size="14" />
        </span>
        <input
          v-model.trim="filters.keyword"
          type="text"
          class="search-input"
          :placeholder="t('bank_manage.search_placeholder')"
        />
        <button
          v-if="filters.keyword"
          type="button"
          class="btn-clear-search"
          @click="filters.keyword = ''"
        >
          <LinearIcon name="x" size="12" />
        </button>
      </div>

      <div class="filter-selects-wrap">
        <!-- 题型筛选 -->
        <select v-model="filters.type" class="filter-select">
          <option value="">{{ t('bank_manage.filter_type') }}</option>
          <option value="SINGLE">{{ t('bank_manage.type_single') }}</option>
          <option value="MULTI">{{ t('bank_manage.type_multi') }}</option>
          <option value="JUDGE">{{ t('bank_manage.type_judge') }}</option>
          <option value="ESSAY">{{ t('bank_manage.type_essay') }}</option>
        </select>

        <!-- 难度筛选 -->
        <select v-model="filters.difficulty" class="filter-select">
          <option value="">{{ t('bank_manage.filter_difficulty') }}</option>
          <option :value="1">{{ t('bank_manage.diff_1') }}</option>
          <option :value="2">{{ t('bank_manage.diff_2') }}</option>
          <option :value="3">{{ t('bank_manage.diff_3') }}</option>
          <option :value="4">{{ t('bank_manage.diff_4') }}</option>
          <option :value="5">{{ t('bank_manage.diff_5') }}</option>
        </select>

        <!-- 章节筛选 -->
        <select v-if="chapters.length > 0" v-model="filters.chapterId" class="filter-select">
          <option value="">{{ t('bank_manage.filter_chapter') }}</option>
          <option v-for="c in chapters" :key="c.id" :value="c.id">
            {{ c.name }}
          </option>
        </select>

        <!-- 标签筛选 -->
        <select v-if="allTags.length > 0" v-model="filters.tag" class="filter-select">
          <option value="">{{ t('bank_manage.filter_tag') }}</option>
          <option v-for="tg in allTags" :key="tg" :value="tg">
            {{ tg }}
          </option>
        </select>

        <!-- 重置筛选按钮 -->
        <button
          v-if="hasActiveFilters"
          type="button"
          class="btn-reset-filters secondary-btn"
          @click="resetFilters"
        >
          {{ t('bank_manage.reset_filters') }}
        </button>
      </div>
    </section>

    <!-- 筛选结果统计计数 -->
    <div class="filter-summary-row">
      <span class="filtered-count-text">
        {{ t('bank_manage.filtered_count', { count: filteredQuestions.length, total: questions.length }) }}
      </span>
    </div>

    <!-- 加载中状态 -->
    <div v-if="loading" class="loading-state-container">
      <p class="muted font-mono">{{ t('common.loading') }}</p>
    </div>

    <!-- 题目列表内容 -->
    <section v-else class="questions-list-section">
      <!-- 结果为空状态 -->
      <div v-if="filteredQuestions.length === 0" class="empty-questions-state">
        <p class="empty-state-text">
          {{ questions.length === 0 ? t('bank_manage.empty_bank') : t('bank_manage.no_matching_questions') }}
        </p>
        <button
          v-if="hasActiveFilters"
          type="button"
          class="primary btn-clear-filters"
          @click="resetFilters"
        >
          {{ t('bank_manage.reset_filters') }}
        </button>
      </div>

      <!-- 题目卡片列表 (自适应桌面高密度/移动端堆叠卡片) -->
      <div v-else class="questions-table-grid">
        <article
          v-for="(q, idx) in filteredQuestions"
          :key="q.id"
          class="question-manage-card"
          :data-testid="`question-card-${q.id}`"
        >
          <div class="card-left-col">
            <span class="question-seq-num">#{{ idx + 1 }}</span>
          </div>

          <div class="card-main-col">
            <div class="card-header-line">
              <span class="type-badge" :class="`badge-type-${(q.type || 'single').toLowerCase()}`">
                {{ formatTypeName(q.type) }}
              </span>
              <span class="difficulty-indicator">
                {{ formatDifficulty(q.difficulty) }}
              </span>
              <span v-if="q.chapter_id" class="chapter-badge">
                {{ getChapterName(q.chapter_id) }}
              </span>
              <span class="version-badge">
                {{ t('bank_manage.version_badge', { ver: q.version_number || 1 }) }}
              </span>
            </div>

            <div class="card-stem-text">
              <p>{{ q.stem }}</p>
            </div>

            <div v-if="q.tags && q.tags.length > 0" class="card-tags-row">
              <span v-for="tag in q.tags" :key="tag" class="tag-pill">
                #{{ tag }}
              </span>
            </div>
          </div>

          <div class="card-actions-col">
            <button
              v-if="canEdit"
              type="button"
              class="primary btn-action-edit"
              :data-testid="`edit-btn-${q.id}`"
              @click="openEditModal(q)"
            >
              <LinearIcon name="edit" size="13" />
              <span>{{ t('bank_manage.edit_question') }}</span>
            </button>
            <button
              v-else
              type="button"
              class="secondary-btn btn-action-view"
              :data-testid="`view-btn-${q.id}`"
              @click="openViewModal(q)"
            >
              <span>{{ t('bank_manage.view_question') }}</span>
            </button>
          </div>
        </article>
      </div>
    </section>

    <!-- 题目编辑/查看弹窗 -->
    <QuestionEditModal
      :show="Boolean(activeModalQuestion)"
      :question="activeModalQuestion"
      :chapters="chapters"
      :read-only="isModalReadOnly"
      :token="token"
      @close="activeModalQuestion = null"
      @saved="handleQuestionSaved"
      @conflict="handleConflictDetected"
    />
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import QuestionEditModal from '../components/QuestionEditModal.vue'
import { getBank, listBankQuestionsContent, listChapters } from '../api/banks'
import { listActiveSessions } from '../api/practice'
import { useLocale } from '../composables/useLocale'
import {
  createEmptyBankFilters,
  isFilterActive,
  canEditBankContent,
  canEditQuestionInBank,
  filterBankQuestions,
} from '../domain/bankManage'

const props = defineProps({
  token: {
    type: String,
    required: true,
  },
  user: {
    type: Object,
    default: null,
  },
})

const route = useRoute()
const router = useRouter()
const { t } = useLocale()

const bankId = computed(() => route.params.bankId)

const bank = ref(null)
const questions = ref([])
const chapters = ref([])
const hasActiveExam = ref(false)
const loading = ref(true)
const error = ref('')
const successToast = ref('')
const conflictAlert = ref('')

const filters = ref(createEmptyBankFilters())
const activeModalQuestion = ref(null)
const isModalReadOnly = ref(false)

const hasActiveFilters = computed(() => isFilterActive(filters.value))

const allTags = computed(() => {
  const set = new Set()
  for (const q of questions.value) {
    if (Array.isArray(q.tags)) {
      for (const tag of q.tags) {
        if (tag) set.add(tag)
      }
    }
  }
  return Array.from(set).sort()
})

const filteredQuestions = computed(() => {
  return filterBankQuestions(questions.value, filters.value)
})

const canEdit = computed(() => {
  return canEditQuestionInBank({
    role: bank.value?.role,
    hasActiveExam: hasActiveExam.value,
  })
})

function formatRole(role) {
  if (!role) return ''
  const upper = String(role).toUpperCase()
  if (upper === 'ADMIN') return t('bank_manage.role_admin')
  if (upper === 'EDITOR') return t('bank_manage.role_editor')
  return t('bank_manage.role_member')
}

function formatTypeName(tp) {
  const upper = String(tp || '').toUpperCase()
  if (upper === 'SINGLE') return t('bank_manage.type_single')
  if (upper === 'MULTI') return t('bank_manage.type_multi')
  if (upper === 'JUDGE') return t('bank_manage.type_judge')
  if (upper === 'ESSAY') return t('bank_manage.type_essay')
  return upper || t('bank_manage.type_single')
}

function formatDifficulty(diff) {
  const n = Number(diff) || 1
  return '★'.repeat(Math.max(1, Math.min(5, n)))
}

function getChapterName(chapId) {
  if (!chapId) return ''
  const c = chapters.value.find(item => item.id === chapId)
  return c ? c.name : ''
}

function resetFilters() {
  filters.value = createEmptyBankFilters()
}

function openEditModal(q) {
  isModalReadOnly.value = false
  activeModalQuestion.value = q
}

function openViewModal(q) {
  isModalReadOnly.value = true
  activeModalQuestion.value = q
}

function handleQuestionSaved(updatedQ) {
  if (!updatedQ) return
  const idx = questions.value.findIndex(item => item.id === updatedQ.id)
  if (idx !== -1) {
    questions.value[idx] = updatedQ
  } else {
    questions.value.unshift(updatedQ)
  }
  if (updatedQ.conflict) {
    conflictAlert.value = t('bank_manage.conflict_detected')
    successToast.value = ''
  } else {
    conflictAlert.value = ''
    successToast.value = t('bank_manage.save_success')
    setTimeout(() => {
      successToast.value = ''
    }, 4000)
  }
}

function handleConflictDetected() {
  conflictAlert.value = t('bank_manage.conflict_detected')
  successToast.value = ''
}

async function loadData() {
  if (!bankId.value) return
  loading.value = true
  error.value = ''

  try {
    const [bankRes, questionsRes, chaptersRes] = await Promise.all([
      getBank(props.token, bankId.value),
      listBankQuestionsContent(props.token, bankId.value),
      listChapters(props.token, bankId.value).catch(() => []),
    ])

    bank.value = bankRes
    questions.value = Array.isArray(questionsRes) ? questionsRes : []
    chapters.value = Array.isArray(chaptersRes) ? chaptersRes : []

    // 服务端下发的锁定状态为单一权威事实源 (O-7 治理)
    hasActiveExam.value = Boolean(bankRes?.locked_by_active_exam || bankRes?.has_active_exam || questions.value.some(q => q.locked_by_active_exam))
  } catch (err) {
    error.value = err.message || t('common.error')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.bank-manage-page {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 1.5rem;
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}

.bank-manage-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
}

.btn-back-home {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8125rem;
  min-height: 42px;
}

.header-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.title-badge-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.bank-icon-wrap {
  width: 2rem;
  height: 2rem;
  border-radius: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
}

.bank-title-text {
  font-size: 1.35rem;
  font-weight: 700;
  margin: 0;
  color: var(--fg-default);
}

.category-pill {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: 9999px;
  color: var(--fg-muted);
}

.bank-desc-text {
  margin: 0.375rem 0 0 0;
  font-size: 0.875rem;
  color: var(--fg-muted);
}

.meta-badges {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.count-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
  padding: 0.3rem 0.625rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--fg-default);
  font-family: var(--linear-mono, monospace);
}

.role-pill {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.3rem 0.625rem;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
}

.role-admin {
  background: rgba(37, 99, 235, 0.12);
  color: var(--primary);
  border-color: rgba(37, 99, 235, 0.3);
}

.role-editor {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
  border-color: rgba(16, 185, 129, 0.3);
}

.role-member {
  background: var(--bg-subtle);
  color: var(--fg-muted);
}

/* Active exam warning alert */
.active-exam-alert {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 8px;
  color: #d97706;
}

.alert-icon {
  margin-top: 0.1rem;
  flex-shrink: 0;
}

.alert-content strong {
  display: block;
  font-size: 0.875rem;
  margin-bottom: 0.2rem;
}

.alert-content p {
  margin: 0;
  font-size: 0.8125rem;
}

.toast-success-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1rem;
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 6px;
  color: #10b981;
  font-size: 0.875rem;
}

.conflict-alert-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 8px;
  color: var(--warning-fg, #b45309);
  font-size: 0.875rem;
}

.conflict-alert-banner .alert-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-conflict-reload {
  margin-left: 0.5rem;
  padding: 0.25rem 0.6rem;
  background: var(--warning, #f59e0b);
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.btn-conflict-reload:hover {
  opacity: 0.9;
}


.conflict-alert-banner .btn-close-toast {
  background: transparent;
  border: none;
  cursor: pointer;
  color: inherit;
  padding: 0.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.alert-error-banner {
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #ef4444;
  font-size: 0.875rem;
}

/* 过滤工具栏 */
.filter-toolbar-section {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.search-input-wrap {
  position: relative;
  flex: 1;
  min-width: 240px;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--fg-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.55rem 2rem 0.55rem 2.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--fg-default);
  font-size: 0.875rem;
  min-height: 42px;
}

.search-input:focus {
  outline: none;
  border-color: var(--primary);
}

.btn-clear-search {
  position: absolute;
  right: 0.6rem;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  color: var(--fg-muted);
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.filter-selects-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.filter-select {
  padding: 0.45rem 0.75rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--fg-default);
  font-size: 0.8125rem;
  min-height: 42px;
}

.btn-reset-filters {
  padding: 0.45rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8125rem;
  min-height: 42px;
}

.filter-summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filtered-count-text {
  font-size: 0.8125rem;
  color: var(--fg-muted);
  font-family: var(--linear-mono, monospace);
}

/* 列表展示 */
.loading-state-container {
  padding: 3rem;
  text-align: center;
}

.empty-questions-state {
  padding: 3.5rem 1rem;
  text-align: center;
  background: var(--bg-card);
  border: 1px dashed var(--border-subtle);
  border-radius: 8px;
}

.empty-state-text {
  font-size: 0.9375rem;
  color: var(--fg-muted);
  margin-bottom: 1rem;
}

.btn-clear-filters {
  min-height: 42px;
  padding: 0.5rem 1rem;
}

.questions-table-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.question-manage-card {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.question-manage-card:hover {
  border-color: var(--border-default, rgba(255, 255, 255, 0.15));
}

.card-left-col {
  padding-top: 0.2rem;
}

.question-seq-num {
  font-size: 0.75rem;
  font-family: var(--linear-mono, monospace);
  color: var(--fg-muted);
  background: var(--bg-subtle);
  padding: 0.15rem 0.35rem;
  border-radius: 4px;
}

.card-main-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.card-header-line {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.type-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  text-transform: uppercase;
}

.badge-type-single {
  background: rgba(37, 99, 235, 0.12);
  color: var(--primary);
}

.badge-type-multi {
  background: rgba(147, 51, 234, 0.12);
  color: #9333ea;
}

.badge-type-judge {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.badge-type-essay {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
}

.difficulty-indicator {
  font-size: 0.6875rem;
  color: #f59e0b;
}

.chapter-badge {
  font-size: 0.6875rem;
  padding: 0.15rem 0.45rem;
  background: var(--bg-subtle);
  border-radius: 4px;
  color: var(--fg-muted);
}

.version-badge {
  font-size: 0.6875rem;
  font-family: var(--linear-mono, monospace);
  padding: 0.1rem 0.35rem;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: var(--fg-muted);
}

.card-stem-text p {
  margin: 0;
  font-size: 0.9375rem;
  color: var(--fg-default);
  line-height: 1.45;
  word-break: break-word;
}

.card-tags-row {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-wrap: wrap;
}

.tag-pill {
  font-size: 0.6875rem;
  padding: 0.1rem 0.4rem;
  background: var(--bg-subtle);
  border-radius: 9999px;
  color: var(--fg-muted);
}

.card-actions-col {
  display: flex;
  align-items: center;
  align-self: center;
}

.btn-action-edit,
.btn-action-view {
  min-height: 42px;
  padding: 0.4rem 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
  border-radius: 6px;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .bank-manage-page {
    padding: 1rem;
    gap: 1rem;
  }
  .filter-toolbar-section {
    flex-direction: column;
    align-items: stretch;
  }
  .search-input-wrap {
    min-width: 100%;
  }
  .filter-selects-wrap {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }
  .question-manage-card {
    flex-direction: column;
    gap: 0.75rem;
  }
  .card-actions-col {
    width: 100%;
    justify-content: flex-end;
  }
  .btn-action-edit,
  .btn-action-view {
    width: 100%;
    justify-content: center;
  }
}
</style>
