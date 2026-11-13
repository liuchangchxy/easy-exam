<template>
  <AccessDeniedState v-if="accessError" :kind="accessError" @back="backToBanks" />
  <div v-else class="question-page">
    <p v-if="loading" class="hint question-loading">{{ t('ep.common.loading') }}</p>

    <div v-else-if="loadFailed" class="empty question-missing" role="alert">
      <div class="empty-title">{{ t('ep.common.load_failed') }}</div>
      <div class="empty-desc">{{ loadError }}</div>
      <div class="empty-actions">
        <button type="button" class="btn" @click="load">{{ t('ep.common.retry') }}</button>
      </div>
    </div>

    <template v-else-if="question">
      <div class="page-head">
        <div class="page-head-main">
          <p class="page-eyebrow">{{ bank?.name || t('ep.nav.banks') }}</p>
          <h1 class="page-title">{{ t('ep.questions.crumb_one', { code: questionCode(question.id) }) }}</h1>
          <p class="page-sub">
            <span>{{ typeLabel(displayQuestion.type) }}</span>
            <span v-if="displayQuestion.chapter_id">{{ chapterName(displayQuestion.chapter_id) }}</span>
            <span>{{ difficultyLabel(displayQuestion.difficulty) }}</span>
            <span class="mono">v{{ displayQuestion.version_number }}</span>
            <span v-if="isArchived" class="tag bad">{{ t('ep.manage.archived_badge') }}</span>
            <span v-if="previewVersion" class="tag">{{ t('ep.banks.version_history') }}</span>
          </p>
          <div v-if="bankError" class="notice bad" role="alert">
            <LinearIcon name="alert" :size="15" />
            <span>{{ t('ep.common.load_failed') }}</span>
            <button type="button" class="btn btn-sm" @click="loadBank">{{ t('ep.common.retry') }}</button>
          </div>
          <div v-if="actionError" class="notice bad" role="alert">
            <LinearIcon name="alert" :size="15" /><span>{{ actionError }}</span>
          </div>
          <div v-else-if="actionNotice" class="notice ok" role="status">
            <LinearIcon name="check" :size="15" /><span>{{ actionNotice }}</span>
          </div>
        </div>
        <div class="page-actions">
          <button
            v-if="!previewVersion"
            type="button"
            class="btn btn-primary practice-one-btn"
            :disabled="starting || isArchived"
            @click="practiceOne"
          >
            <LinearIcon name="play" :size="14" />{{ starting ? t('ep.common.starting') : t('ep.banks.practice_one') }}
          </button>
          <button
            v-if="canEdit && !previewVersion"
            type="button"
            class="btn"
            data-testid="question-edit"
            :disabled="Boolean(editBlockedReason)"
            :title="editBlockedReason || undefined"
            @click="editing = true"
          >
            <LinearIcon name="edit" :size="14" />{{ t('ep.common.edit') }}
          </button>
          <button
            v-if="canEdit && !previewVersion"
            type="button"
            class="btn"
            data-testid="question-archive"
            :disabled="lockedByExam"
            :title="lockedByExam ? t('ep.manage.locked_desc') : undefined"
            @click="toggleArchive"
          >
            <LinearIcon :name="isArchived ? 'rotate-ccw' : 'archive'" :size="14" />{{ isArchived ? t('ep.manage.restore') : t('ep.manage.archive') }}
          </button>
        </div>
      </div>

      <div class="question-layout">
        <section class="panel question-sheet reading-page">
          <div class="kv question-kv">
            <div><span class="k">{{ t('ep.banks.type') }}</span><span class="v">{{ typeLabel(displayQuestion.type) }}</span></div>
            <div><span class="k">{{ t('ep.banks.chapter') }}</span><span class="v">{{ chapterName(displayQuestion.chapter_id) }}</span></div>
            <div><span class="k">{{ t('ep.banks.difficulty') }}</span><span class="v">{{ difficultyLabel(displayQuestion.difficulty) }}</span></div>
            <div><span class="k">{{ t('ep.banks.version') }}</span><span class="v mono">v{{ displayQuestion.version_number }}</span></div>
          </div>

          <div class="qp-stem">{{ displayQuestion.stem }}</div>

          <div v-if="displayQuestion.options?.length" class="opt-list">
            <div
              v-for="opt in displayQuestion.options"
              :key="opt.key"
              class="opt"
              :class="{ 'is-correct': isCorrectOption(displayQuestion, opt.key) }"
            >
              <span class="opt-key">{{ opt.key }}</span>
              <span class="opt-text">{{ opt.text || opt.content }}</span>
              <span v-if="isCorrectOption(displayQuestion, opt.key)" class="opt-mark"><LinearIcon name="check" :size="14" /></span>
            </div>
          </div>

          <div v-if="lockedNote" class="notice warn" role="note">
            <LinearIcon name="lock" :size="15" />
            <span>{{ t('ep.banks.question_locked_note') }}</span>
          </div>
          <template v-else>
            <div class="answer-line">
              <LinearIcon name="check" :size="15" />
              <span>{{ t('ep.banks.answer') }}</span>
              <span class="ans">{{ displayQuestion.answer || t('ep.banks.answer_none') }}</span>
            </div>
            <div class="explain-body">{{ displayQuestion.explanation || t('ep.exam.no_analysis') }}</div>
          </template>

          <p v-if="displayQuestion.tags?.length" class="qp-tags">
            <span v-for="tag in displayQuestion.tags" :key="tag" class="tag">{{ tag }}</span>
          </p>
        </section>

        <aside class="question-rail">
          <section class="panel qp-rail-panel" data-testid="question-versions">
            <div class="qp-rail-head">
              <span class="rule-label">{{ t('ep.banks.version_history') }}</span>
              <span class="small dim">{{ t('ep.banks.version_current') }} v{{ question.version_number }}</span>
            </div>
            <div v-if="versionError" class="notice bad" role="alert">
              <LinearIcon name="alert" :size="15" />
              <span class="hint bad-text">{{ versionError }}</span>
              <button type="button" class="btn btn-sm" @click="loadVersions">{{ t('ep.common.retry') }}</button>
            </div>
            <p v-else-if="versionsLoading" class="hint">{{ t('ep.common.loading') }}</p>
            <p v-else-if="!versions.length" class="hint">{{ t('ep.banks.version_history_empty') }}</p>
            <div v-else class="qp-version-list">
              <button
                v-for="ver in versions"
                :key="ver.id"
                type="button"
                class="qp-version-item version-item"
                :class="{ 'is-active': previewVersion?.id === ver.id, 'is-current': ver.version_number === question.version_number }"
                :aria-current="previewVersion?.id === ver.id ? 'true' : undefined"
                @click="setPreviewVersion(ver)"
              >
                <span class="mono">v{{ ver.version_number }}</span>
                <span class="od-truncate">{{ stripHtml(ver.stem) }}</span>
                <span v-if="ver.version_number === question.version_number" class="tag ok">{{ t('ep.banks.version_current') }}</span>
              </button>
            </div>
            <div v-if="previewVersion" class="qp-preview-note">
              <span class="hint">{{ t('ep.banks.version_preview_note') }}</span>
              <button type="button" class="btn btn-sm btn-quiet" @click="setPreviewVersion(null)">{{ t('ep.banks.version_back') }}</button>
            </div>
          </section>

          <section v-if="(copyTargets.length || banksError) && !isArchived && !previewVersion" class="panel qp-rail-panel">
            <span class="rule-label">{{ t('ep.banks.copy_to') }}</span>
            <div v-if="banksError" class="notice bad" role="alert">
              <span>{{ t('ep.common.load_failed') }}</span>
              <button type="button" class="btn btn-sm" @click="loadBanks">{{ t('ep.common.retry') }}</button>
            </div>
            <div v-else-if="copyTargets.length" class="copy-form">
              <select v-model="copyTargetId" class="select copy-select" :aria-label="t('ep.banks.copy_to')">
                <option value="" disabled>{{ t('ep.banks.copy_target_placeholder') }}</option>
                <option v-for="target in copyTargets" :key="target.id" :value="target.id">{{ target.name }}</option>
              </select>
              <button type="button" class="btn btn-sm" :disabled="copyBusy || !copyTargetId" @click="copyQuestion">
                {{ copyBusy ? t('ep.common.loading') : t('ep.banks.copy_action') }}
              </button>
            </div>
            <p v-else class="hint">{{ t('ep.banks.no_copy_target') }}</p>
            <p v-if="copyNotice" class="small copy-notice" :class="{ 'bad-text': copyNoticeError }" role="alert">{{ copyNotice }}</p>
            <p class="hint qp-copy-hint">{{ t('ep.questions.copy_hint') }}</p>
          </section>
        </aside>
      </div>

      <QuestionEditModal
        v-if="canEdit && question && !editBlockedReason"
        :show="editing"
        :question="question"
        :chapters="chapters"
        :token="token"
        @close="editing = false"
        @saved="handleSaved"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AccessDeniedState from '../components/AccessDeniedState.vue'
import LinearIcon from '../components/LinearIcon.vue'
import QuestionEditModal from '../components/QuestionEditModal.vue'
import { useLocale } from '../composables/useLocale.js'
import { canEditBankContent, questionCode } from '../domain/bankManage.js'
import { getBank, listBanks, listChapters, copyQuestionToBank, batchBankQuestions } from '../api/banks'
import { getQuestion, listQuestionVersions } from '../api/questions'
import { startSession } from '../api/practice'
import { readQueryString, replaceQueryState } from '../utils/routeQuery.js'

const props = defineProps({
  token: { type: String, required: true },
  bankId: { type: String, default: '' },
  questionId: { type: String, default: '' },
})

const route = useRoute()
const router = useRouter()
const { t } = useLocale()

const bankId = computed(() => String(props.bankId || route.params?.bankId || ''))
const questionId = computed(() => String(props.questionId || route.params?.questionId || ''))

const bank = ref(null)
const question = ref(null)
const chapters = ref([])
const banks = ref([])
const loading = ref(true)
const accessError = ref('')
const loadFailed = ref(false)
const loadError = ref('')
const banksError = ref(false)
const bankError = ref('')

const versions = ref([])
const versionsLoading = ref(false)
const versionError = ref('')
const previewVersion = ref(null)

const starting = ref(false)
const editing = ref(false)
const actionError = ref('')
const actionNotice = ref('')

const copyTargetId = ref('')
const copyBusy = ref(false)
const copyNotice = ref('')
const copyNoticeError = ref(false)

let loadSeq = 0
let versionSeq = 0

const canEdit = computed(() => canEditBankContent(bank.value?.role))
const isArchived = computed(() => Boolean(question.value?.archived))
const lockedByExam = computed(() => Boolean(question.value?.locked_by_active_exam))
const displayQuestion = computed(() => previewVersion.value || question.value || {})

// Why edit is unavailable even though the user may edit the bank: the backend
// answers 400 for archived questions and 403 while an exam locks them.
const editBlockedReason = computed(() => {
  if (isArchived.value) return t('ep.manage.archived_note')
  if (lockedByExam.value) return t('ep.manage.locked_desc')
  return ''
})

const lockedNote = computed(() => {
  if (previewVersion.value) return false
  const q = question.value
  if (!q?.locked_by_active_exam) return false
  return !String(q.answer || '').trim() && !String(q.explanation || '').trim()
})

const copyTargets = computed(() => banks.value.filter(item => {
  if (item.id === bankId.value) return false
  return ['ADMIN', 'EDITOR'].includes(String(item.role || '').toUpperCase())
}))

function stripHtml(html) {
  return String(html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

function typeLabel(type) {
  const key = String(type || '').toLowerCase()
  const map = { single: 'single', multi: 'multi', judge: 'judge', fill: 'fill', essay: 'essay', qa: 'essay', short_answer: 'essay', subjective: 'essay' }
  return t('ep.question_types.' + (map[key] || 'single'))
}

function difficultyLabel(value) {
  const n = Number(value)
  if (!n) return t('ep.difficulty.unrated')
  return t('ep.difficulty.' + Math.max(1, Math.min(5, n)))
}

function chapterName(id) {
  return chapters.value.find(c => c.id === id)?.name || t('ep.common.none')
}

function isCorrectOption(q, key) {
  return String(q.answer || '').toUpperCase().includes(String(key).toUpperCase())
}

function accessKind(error) {
  const status = Number(error?.status)
  if (status === 403) return 'forbidden'
  if (status === 404) return 'missing'
  return ''
}

function messageOf(error) {
  return error?.detail || error?.message || t('ep.common.load_failed')
}

function applyPreviewFromQuery() {
  const wanted = readQueryString(route.query?.v)
  const current = String(question.value?.version_number ?? '')
  if (!wanted || wanted === current) {
    previewVersion.value = null
    return
  }
  previewVersion.value = versions.value.find(ver => String(ver.version_number) === wanted) || null
}

function setPreviewVersion(version) {
  if (!version || version.version_number === question.value?.version_number) {
    previewVersion.value = null
    replaceQueryState(router, route.query, { v: '' })
    return
  }
  previewVersion.value = version
  replaceQueryState(router, route.query, { v: version.version_number })
}

async function load() {
  const requestId = ++loadSeq
  versionSeq += 1
  loading.value = true
  accessError.value = ''
  loadFailed.value = false
  loadError.value = ''
  bankError.value = ''
  actionError.value = ''
  bank.value = null
  question.value = null
  versions.value = []
  previewVersion.value = null
  if (!bankId.value || !questionId.value) {
    loading.value = false
    accessError.value = 'missing'
    return
  }
  const [bankRes, questionRes, chaptersRes, banksRes] = await Promise.allSettled([
    getBank(props.token, bankId.value),
    getQuestion(props.token, questionId.value),
    listChapters(props.token, bankId.value),
    listBanks(props.token),
  ])
  if (requestId !== loadSeq) return
  const denied = [bankRes, questionRes].find(r => r.status === 'rejected' && accessKind(r.reason))
  if (denied) {
    accessError.value = accessKind(denied.reason)
    loading.value = false
    return
  }
  bank.value = bankRes.status === 'fulfilled' ? bankRes.value : null
  bankError.value = bankRes.status === 'rejected' ? messageOf(bankRes.reason) : ''
  chapters.value = chaptersRes.status === 'fulfilled' && Array.isArray(chaptersRes.value) ? chaptersRes.value : []
  banks.value = banksRes.status === 'fulfilled' && Array.isArray(banksRes.value) ? banksRes.value : []
  banksError.value = banksRes.status === 'rejected'
  if (questionRes.status !== 'fulfilled' || !questionRes.value) {
    loadFailed.value = true
    loadError.value = questionRes.status === 'rejected' ? messageOf(questionRes.reason) : t('ep.common.load_failed')
    loading.value = false
    return
  }
  const resolved = questionRes.value
  const resolvedBankId = String(resolved.bank_id || '')
  loading.value = false
  // A global question URL can point at the wrong bank; send the reader to the
  // bank the question really belongs to instead of showing it under this one.
  if (resolvedBankId && resolvedBankId !== bankId.value) {
    if (String(route.params?.bankId || '') !== resolvedBankId) {
      router.replace({
        name: 'question',
        params: { bankId: resolvedBankId, questionId: resolved.id || questionId.value },
      })
    }
    return
  }
  question.value = resolved
  loadVersions()
}

async function loadVersions() {
  const target = question.value
  if (!target) return
  const requestId = ++versionSeq
  const targetId = target.id
  versionError.value = ''
  versionsLoading.value = true
  try {
    const res = await listQuestionVersions(props.token, targetId)
    if (requestId !== versionSeq || question.value?.id !== targetId) return
    versions.value = Array.isArray(res)
      ? res.slice().sort((a, b) => (b.version_number || 0) - (a.version_number || 0))
      : []
    applyPreviewFromQuery()
  } catch (err) {
    if (requestId !== versionSeq || question.value?.id !== targetId) return
    versionError.value = err?.detail || err?.message || t('ep.common.load_failed')
  } finally {
    if (requestId === versionSeq) versionsLoading.value = false
  }
}

async function loadBank() {
  if (!bankId.value) return
  bankError.value = ''
  try {
    bank.value = await getBank(props.token, bankId.value)
  } catch (err) {
    const kind = accessKind(err)
    if (kind) {
      accessError.value = kind
      return
    }
    bankError.value = messageOf(err)
  }
}

async function loadBanks() {
  banksError.value = false
  try {
    const res = await listBanks(props.token)
    banks.value = Array.isArray(res) ? res : []
  } catch (_) {
    banksError.value = true
  }
}

async function practiceOne() {
  if (!question.value || starting.value) return
  starting.value = true
  actionError.value = ''
  try {
    const session = await startSession(props.token, {
      bank_id: bankId.value,
      mode: 'PRACTICE',
      question_ids: [question.value.id],
      total_questions: 1,
    })
    router.push(`/practice/${session.id}`)
  } catch (err) {
    actionError.value = err?.detail || err?.message || t('ep.common.load_failed')
  } finally {
    starting.value = false
  }
}

async function toggleArchive() {
  if (!question.value || lockedByExam.value) return
  const nextArchived = !isArchived.value
  actionError.value = ''
  actionNotice.value = ''
  const result = await batchBankQuestions(props.token, bankId.value, {
    operation: nextArchived ? 'archive' : 'restore',
    question_ids: [question.value.id],
  }).catch(err => err)
  if (result instanceof Error) {
    actionError.value = result.detail || result.message || t('ep.common.load_failed')
    return
  }
  question.value = { ...question.value, archived: nextArchived }
  actionNotice.value = nextArchived ? t('ep.manage.archive_done') : t('ep.manage.restore_done')
}

async function copyQuestion() {
  if (!copyTargetId.value || copyBusy.value) return
  copyBusy.value = true
  copyNotice.value = ''
  copyNoticeError.value = false
  try {
    await copyQuestionToBank(props.token, bankId.value, question.value.id, copyTargetId.value)
    const target = banks.value.find(b => b.id === copyTargetId.value)
    copyNotice.value = t('ep.banks.copy_done', { name: target?.name || '' })
    copyTargetId.value = ''
  } catch (err) {
    copyNoticeError.value = true
    copyNotice.value = err?.detail || err?.message || t('ep.common.load_failed')
  } finally {
    copyBusy.value = false
  }
}

function handleSaved() {
  editing.value = false
  load()
}

function backToBanks() {
  // The bank-detail route is denied too when the denial came from that bank,
  // so every access state exits to the list instead of looping.
  router.push({ name: 'banks' })
}

watch([bankId, questionId], () => load(), { immediate: true })
</script>

<style scoped>
.question-page { padding-top: 26px; }
.question-loading { padding: 24px 0; }

.question-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 24px;
  align-items: start;
  margin-top: 8px;
}

.question-sheet {
  padding: 26px 28px 30px;
  min-width: 0;
}

.question-kv {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-bottom: 18px;
}

.qp-stem {
  font-size: 16px;
  line-height: 1.7;
  margin-bottom: 20px;
}

.qp-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 18px 0 0;
}

.question-rail {
  display: grid;
  gap: 16px;
  position: sticky;
  top: 16px;
}

.qp-rail-panel {
  padding: 16px;
  display: grid;
  gap: 10px;
}

.qp-rail-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.qp-version-list {
  display: grid;
  gap: 4px;
  max-height: 320px;
  overflow: auto;
}

.qp-version-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  background: none;
  color: var(--ink-2);
  text-align: left;
  cursor: pointer;
}

.qp-version-item:hover { background: var(--surface-2); }
.qp-version-item.is-active { border-color: var(--line-strong); background: var(--surface-2); }
.qp-version-item.is-current { color: var(--ink); }

.qp-preview-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-top: 1px solid var(--line);
  padding-top: 10px;
}

.qp-copy-hint { margin: 0; }

.copy-form {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}

.copy-select {
  flex: 1 1 130px;
  min-width: 0;
  max-width: 180px;
  height: 30px;
  font-size: 12px;
}

.copy-notice { margin: 0; color: var(--ink-3); overflow-wrap: anywhere; }
.copy-notice.bad-text { color: var(--bad); }
.bad-text { color: var(--bad); }

.question-missing { margin-top: 12vh; }

@media (max-width: 900px) {
  .question-layout { grid-template-columns: minmax(0, 1fr); }
  .question-rail { position: static; }
  .copy-select { max-width: none; }
}
</style>
