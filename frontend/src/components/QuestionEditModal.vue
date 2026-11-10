<template>
  <div
    v-if="show"
    class="modal-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="question-edit-title"
    @click.self="handleClose"
    @keydown.esc="handleClose"
  >
    <div class="modal-dialog question-edit-dialog">
      <header class="modal-header">
        <div class="modal-title-wrap">
          <div class="rule-label">{{ t('ep.manage.tab_questions') }}</div>
          <h2 id="question-edit-title">
            {{ readOnly ? t('bank_manage.view_question') : t('bank_manage.edit_question') }}
          </h2>
        </div>
        <div class="modal-head-right">
          <button type="button" class="btn btn-sm btn-quiet" @click="toggleVersionHistory">
            {{ t('bank_manage.version_history') }}
          </button>
          <span v-if="question" class="version-tag mono">
            {{ t('bank_manage.version_badge', { ver: baseVersion }) }}
          </span>
          <button type="button" class="icon-btn" :aria-label="t('common.close')" @click="handleClose">
            <LinearIcon name="x" size="16" />
          </button>
        </div>
      </header>

      <form class="modal-body-form" @submit.prevent="handleSave">
        <section v-if="showVersionHistory" class="version-history" aria-live="polite">
          <div class="version-history-head">
            <span class="rule-label">{{ t('bank_manage.version_history') }}</span>
            <button type="button" class="icon-btn" :aria-label="t('common.close')" @click="showVersionHistory = false">
              <LinearIcon name="x" size="14" />
            </button>
          </div>
          <p v-if="versionError" class="hint bad-text">{{ versionError }}</p>
          <p v-else-if="versionsLoading" class="hint">{{ t('common.loading') }}</p>
          <p v-else-if="!versions.length" class="hint">{{ t('bank_manage.version_history_empty') }}</p>
          <div v-else class="version-list">
            <button
              v-for="ver in versions"
              :key="ver.id"
              type="button"
              class="version-row"
              :class="{ 'is-current': ver.version_number === baseVersion }"
              @click="versionPreview = ver"
            >
              <span class="mono">v{{ ver.version_number }}</span>
              <span class="version-meta">
                <span v-if="ver.version_number === baseVersion" class="tag ok">{{ t('bank_manage.version_current') }}</span>
                <span class="dim">{{ t('bank_manage.version_created', { date: formatVersionDate(ver.created_at) }) }}</span>
              </span>
              <span class="version-view">{{ t('bank_manage.version_view') }}</span>
            </button>
          </div>

          <div v-if="versionPreview" class="version-preview">
            <div class="version-preview-head">
              <span class="mono">v{{ versionPreview.version_number }}</span>
              <button type="button" class="btn btn-sm btn-quiet" @click="versionPreview = null">
                {{ t('bank_manage.version_back') }}
              </button>
            </div>
            <p class="hint">{{ t('bank_manage.version_preview_hint') }}</p>
            <div class="version-stem">{{ versionPreview.stem }}</div>
            <div v-if="versionPreview.options?.length" class="version-options">
              <div v-for="opt in versionPreview.options" :key="opt.key" class="version-option">
                <span class="mono">{{ opt.key }}</span>
                <span>{{ opt.content ?? opt.text }}</span>
              </div>
            </div>
            <div class="version-answer">
              <span class="label">{{ t('bank_manage.answer_label') }}</span>
              <span>{{ versionPreview.answer || t('ep.common.none') }}</span>
            </div>
            <div v-if="versionPreview.explanation" class="version-explanation">{{ versionPreview.explanation }}</div>
          </div>
        </section>

        <div v-if="errorMsg" class="notice bad" role="alert">
          <span>{{ errorMsg }}</span>
          <div v-if="isConflict" class="conflict-actions">
            <p class="hint">{{ t('bank_manage.conflict_draft_kept') }}</p>
            <div class="conflict-buttons">
              <button type="button" class="btn btn-sm" :disabled="saving" @click="saveAsBranch">
                {{ t('bank_manage.save_as_branch') }}
              </button>
              <button type="button" class="btn btn-sm btn-quiet" :disabled="saving" @click="handleReloadLatest">
                {{ t('bank_manage.discard_and_reload') }}
              </button>
            </div>
          </div>
        </div>

        <label class="field" for="edit-stem">
          <span class="label">{{ t('bank_manage.stem_label') }} <span class="required">*</span></span>
          <textarea
            id="edit-stem"
            v-model.trim="stem"
            rows="3"
            class="textarea"
            :disabled="readOnly || saving"
            required
          ></textarea>
        </label>

        <div class="qe-grid">
          <label class="field" for="edit-type">
            <span class="label">{{ t('bank_manage.type_label') }}</span>
            <select id="edit-type" v-model="type" class="select" :disabled="readOnly || saving">
              <option value="SINGLE">{{ t('bank_manage.type_single') }}</option>
              <option value="MULTI">{{ t('bank_manage.type_multi') }}</option>
              <option value="JUDGE">{{ t('bank_manage.type_judge') }}</option>
              <option value="ESSAY">{{ t('bank_manage.type_essay') }}</option>
            </select>
          </label>

          <label class="field" for="edit-diff">
            <span class="label">{{ t('bank_manage.difficulty_label') }}</span>
            <select id="edit-diff" v-model.number="difficulty" class="select" :disabled="readOnly || saving">
              <option :value="1">{{ t('bank_manage.diff_1') }}</option>
              <option :value="2">{{ t('bank_manage.diff_2') }}</option>
              <option :value="3">{{ t('bank_manage.diff_3') }}</option>
              <option :value="4">{{ t('bank_manage.diff_4') }}</option>
              <option :value="5">{{ t('bank_manage.diff_5') }}</option>
            </select>
          </label>

          <label class="field" for="edit-chap">
            <span class="label">{{ t('bank_manage.chapter_label') }}</span>
            <select id="edit-chap" v-model="chapterId" class="select" :disabled="readOnly || saving">
              <option value="">{{ t('bank_manage.no_chapter') }}</option>
              <option v-for="c in chapters" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </label>
        </div>

        <div v-if="isChoiceType" class="field options-group">
          <div class="options-header-row">
            <span class="label">{{ t('bank_manage.options_label') }}</span>
            <button
              v-if="!readOnly && type !== 'JUDGE'"
              type="button"
              class="btn btn-sm btn-quiet"
              :disabled="saving"
              @click="addOption"
            >
              {{ t('bank_manage.add_option') }}
            </button>
          </div>
          <div class="options-list">
            <div v-for="(opt, idx) in options" :key="idx" class="option-row">
              <input
                v-model.trim="opt.key"
                type="text"
                class="input opt-key-field mono"
                :placeholder="t('bank_manage.option_key_placeholder')"
                :disabled="readOnly || saving || type === 'JUDGE'"
                required
              />
              <input
                v-model="opt.content"
                type="text"
                class="input opt-content-field"
                :placeholder="t('bank_manage.option_content_placeholder')"
                :disabled="readOnly || saving"
                required
              />
              <button
                v-if="!readOnly && type !== 'JUDGE'"
                type="button"
                class="icon-btn btn-del-sm"
                :disabled="saving || options.length <= 2"
                :title="t('bank_manage.remove_option')"
                :aria-label="t('bank_manage.remove_option')"
                @click="removeOption(idx)"
              >
                <LinearIcon name="trash" size="13" />
              </button>
            </div>
          </div>
        </div>

        <label class="field" for="edit-answer">
          <span class="label">{{ t('bank_manage.answer_label') }}</span>
          <input id="edit-answer" v-model.trim="answer" type="text" class="input" :disabled="readOnly || saving" />
        </label>

        <div v-if="regradeAvailable" class="regrade-choice notice">
          <div class="regrade-head">{{ t('bank_manage.regrade_title') }}</div>
          <label class="check-row">
            <input v-model="regradeHistory" type="checkbox" :disabled="readOnly || saving" />
            <span>{{ t('bank_manage.regrade_offer') }}</span>
          </label>
          <p class="hint">{{ regradeHistory ? t('bank_manage.regrade_warning') : t('bank_manage.regrade_hint') }}</p>
          <label v-if="regradeHistory" class="check-row">
            <input v-model="regradeFsrs" type="checkbox" :disabled="readOnly || saving" />
            <span>{{ t('bank_manage.regrade_fsrs') }}</span>
          </label>
        </div>

        <label class="field" for="edit-explanation">
          <span class="label">{{ t('bank_manage.explanation_label') }}</span>
          <textarea id="edit-explanation" v-model.trim="explanation" rows="3" class="textarea" :disabled="readOnly || saving"></textarea>
        </label>

        <label class="field" for="edit-tags">
          <span class="label">{{ t('bank_manage.tags_label') }}</span>
          <input id="edit-tags" v-model="tagsInput" type="text" class="input" :disabled="readOnly || saving" />
        </label>

        <footer class="modal-footer">
          <button type="button" class="btn" :disabled="saving" @click="handleClose">{{ t('common.cancel') }}</button>
          <button v-if="!readOnly" type="submit" class="btn btn-primary btn-submit-edit" :disabled="saving">
            {{ saving ? t('common.loading') : t('common.save') }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { updateQuestion, getQuestion, getQuestionConflict, listQuestionVersions } from '../api/questions'
import { useLocale } from '../composables/useLocale'
import {
  validateQuestionEdit,
  sanitizeAnswerOnOptionRemove,
  adaptAnswerOnTypeChange,
  shouldOfferRegrade,
} from '../domain/bankManage'

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  question: {
    type: Object,
    default: null,
  },
  chapters: {
    type: Array,
    default: () => [],
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
  token: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['close', 'saved', 'conflict', 'reloaded'])

const { t } = useLocale()

const stem = ref('')
const type = ref('SINGLE')
const difficulty = ref(3)
const chapterId = ref('')
const options = ref([])
const answer = ref('')
const explanation = ref('')
const tagsInput = ref('')
const saving = ref(false)
const errorMsg = ref('')
const isConflict = ref(false)
const baseVersion = ref(1)
const original = ref({ type: 'SINGLE', answer: '' })
const regradeHistory = ref(false)
const regradeFsrs = ref(true)
const showVersionHistory = ref(false)
const versions = ref([])
const versionsLoading = ref(false)
const versionError = ref('')
const versionPreview = ref(null)

const isChoiceType = computed(() => {
  return ['SINGLE', 'MULTI', 'JUDGE'].includes(type.value)
})

const regradeAvailable = computed(() => {
  if (props.readOnly) return false
  return shouldOfferRegrade(original.value, { type: type.value, answer: answer.value })
})

watch(
  () => props.question,
  (q) => {
    if (q) {
      stem.value = q.stem || ''
      type.value = q.type || 'SINGLE'
      difficulty.value = q.difficulty !== undefined && q.difficulty !== null ? Number(q.difficulty) : 3
      chapterId.value = q.chapter_id || ''
      answer.value = q.answer || ''
      explanation.value = q.explanation || ''
      if (Array.isArray(q.options) && q.options.length > 0) {
        options.value = q.options.map(opt => ({
          key: opt.key || '',
          content: opt.content !== undefined ? opt.content : (opt.text || ''),
        }))
      } else if (['SINGLE', 'MULTI'].includes(type.value)) {
        options.value = [
          { key: 'A', content: '' },
          { key: 'B', content: '' },
          { key: 'C', content: '' },
          { key: 'D', content: '' },
        ]
      } else if (type.value === 'JUDGE') {
        options.value = [
          { key: 'T', content: t('bank_manage.judge_true') },
          { key: 'F', content: t('bank_manage.judge_false') },
        ]
      } else {
        options.value = []
      }
      tagsInput.value = Array.isArray(q.tags) ? q.tags.join(', ') : ''
      baseVersion.value = q.version_number || 1
      original.value = { type: q.type || 'SINGLE', answer: q.answer || '' }
      regradeHistory.value = false
      regradeFsrs.value = true
      showVersionHistory.value = false
      versions.value = []
      versionPreview.value = null
      versionError.value = ''
      errorMsg.value = ''
      isConflict.value = false
    }
  },
  { immediate: true }
)

// Type switching logic
watch(type, (newType, oldType) => {
  if (props.readOnly) return
  if (!oldType || newType === oldType) return

  if (newType === 'JUDGE') {
    options.value = [
      { key: 'T', content: t('bank_manage.judge_true') },
      { key: 'F', content: t('bank_manage.judge_false') },
    ]
  } else if (['SINGLE', 'MULTI'].includes(newType)) {
    const isFromJudge = oldType === 'JUDGE' || options.value.some(o => ['T', 'F'].includes(String(o?.key || '').toUpperCase()))
    if (isFromJudge || !options.value.length || options.value.length < 2) {
      options.value = [
        { key: 'A', content: '' },
        { key: 'B', content: '' },
        { key: 'C', content: '' },
        { key: 'D', content: '' },
      ]
    }
  } else if (newType === 'ESSAY') {
    options.value = []
  }

  const prevAnswer = answer.value
  const adapted = adaptAnswerOnTypeChange(newType, prevAnswer, options.value)
  answer.value = adapted
  if (prevAnswer && prevAnswer.trim() && !adapted) {
    errorMsg.value = t('bank_manage.answer_reset_prompt')
  }
})

function addOption() {
  const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  const nextKey = letters[options.value.length] || `Option${options.value.length + 1}`
  options.value.push({ key: nextKey, content: '' })
}

function removeOption(idx) {
  if (options.value.length > 2) {
    const removedKey = options.value[idx]?.key
    options.value.splice(idx, 1)
    answer.value = sanitizeAnswerOnOptionRemove(type.value, answer.value, removedKey)
  }
}

function handleClose() {
  if (!saving.value) {
    emit('close')
  }
}

async function handleReloadLatest() {
  if (!props.question) return
  saving.value = true
  errorMsg.value = ''
  try {
    const latestQ = await getQuestion(props.token, props.question.id)
    if (latestQ) {
      baseVersion.value = latestQ.version_number || baseVersion.value
      stem.value = latestQ.stem || ''
      type.value = latestQ.type || 'SINGLE'
      difficulty.value = latestQ.difficulty !== undefined && latestQ.difficulty !== null ? Number(latestQ.difficulty) : 3
      chapterId.value = latestQ.chapter_id || ''
      answer.value = latestQ.answer || ''
      explanation.value = latestQ.explanation || ''
      if (Array.isArray(latestQ.options) && latestQ.options.length > 0) {
        options.value = latestQ.options.map(opt => ({
          key: opt.key || '',
          content: opt.content !== undefined ? opt.content : (opt.text || ''),
        }))
      } else {
        options.value = []
      }
      tagsInput.value = Array.isArray(latestQ.tags) ? latestQ.tags.join(', ') : ''
      original.value = { type: latestQ.type || 'SINGLE', answer: latestQ.answer || '' }
      regradeHistory.value = false
      versions.value = []
      versionPreview.value = null
      isConflict.value = false
      errorMsg.value = ''
      emit('reloaded', latestQ)
    }
  } catch (err) {
    errorMsg.value = err?.detail?.message || err?.detail || err?.message || t('bank_manage.version_load_failed')
  } finally {
    saving.value = false
  }
}

async function toggleVersionHistory() {
  if (showVersionHistory.value) {
    showVersionHistory.value = false
    return
  }
  showVersionHistory.value = true
  versionPreview.value = null
  if (versions.value.length || !props.question) return
  versionsLoading.value = true
  versionError.value = ''
  try {
    const res = await listQuestionVersions(props.token, props.question.id)
    versions.value = Array.isArray(res) ? res.slice().sort((a, b) => (b.version_number || 0) - (a.version_number || 0)) : []
  } catch (err) {
    versionError.value = err?.detail?.message || err?.detail || err?.message || t('bank_manage.version_load_failed')
  } finally {
    versionsLoading.value = false
  }
}

function formatVersionDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString()
}

function buildPayload({ allowStaleBranch = false, rejectStale = true } = {}) {
  const parsedTags = tagsInput.value
    ? tagsInput.value.split(/[,\s]+/).map(tag => tag.trim()).filter(Boolean)
    : []
  const regrade = regradeAvailable.value && regradeHistory.value
  return {
    stem: stem.value.trim(),
    type: type.value,
    options: isChoiceType.value ? options.value : [],
    answer: answer.value.trim(),
    explanation: explanation.value.trim(),
    difficulty: Number(difficulty.value),
    tags: parsedTags,
    chapter_id: chapterId.value ? chapterId.value : null,
    base_version_number: baseVersion.value,
    regrade_history: regrade,
    apply_fsrs: regrade ? regradeFsrs.value : true,
    allow_stale_branch: allowStaleBranch,
    reject_stale: rejectStale,
  }
}

async function submitPayload(options = {}) {
  saving.value = true
  errorMsg.value = ''
  try {
    const updated = await updateQuestion(props.token, props.question.id, buildPayload(options))
    let conflictInfo = null
    try {
      const confRes = await getQuestionConflict(props.token, props.question.id)
      if (confRes?.has_conflict) {
        conflictInfo = confRes.conflict
      }
    } catch {
      // Non-blocking conflict lookup
    }
    emit('saved', conflictInfo ? { ...updated, conflict: conflictInfo } : updated)
    emit('close')
  } catch (err) {
    if (err?.status === 409 || err?.detail?.error === 'version_conflict') {
      isConflict.value = true
      errorMsg.value = t('bank_manage.conflict_detected')
      emit('conflict', { questionId: props.question.id, error: err })
    } else {
      errorMsg.value = err?.detail?.message || err?.detail || err?.message || t('bank_manage.save_error', { error: 'Request failed' })
    }
  } finally {
    saving.value = false
  }
}

async function handleSave() {
  if (props.readOnly || !props.question) return
  if (!stem.value.trim()) return

  // Strict answer validation per question type
  const validation = validateQuestionEdit(type.value, options.value, answer.value)
  if (!validation.valid) {
    errorMsg.value = t('bank_manage.invalid_answer')
    return
  }
  if (type.value === 'JUDGE') {
    answer.value = answer.value.trim().toUpperCase()
  }
  await submitPayload()
}

async function saveAsBranch() {
  if (props.readOnly || !props.question || !stem.value.trim()) return
  const validation = validateQuestionEdit(type.value, options.value, answer.value)
  if (!validation.valid) {
    errorMsg.value = t('bank_manage.invalid_answer')
    return
  }
  if (type.value === 'JUDGE') {
    answer.value = answer.value.trim().toUpperCase()
  }
  // The draft is submitted unchanged as a new branch; the server keeps both
  // versions and records the unresolved conflict for later review.
  isConflict.value = false
  await submitPayload({ allowStaleBranch: true, rejectStale: false })
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: color-mix(in srgb, var(--ink) 38%, transparent);
  backdrop-filter: blur(2px);
}
.question-edit-dialog {
  width: min(100%, 680px);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-2);
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--line);
}
.modal-title-wrap h2 {
  margin: 4px 0 0;
  font-family: var(--font-serif);
  font-size: 21px;
  font-weight: 600;
  letter-spacing: .01em;
}
.modal-head-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.version-tag { font-size: 10.5px; color: var(--ink-4); letter-spacing: .04em; }
.version-history {
  border: 1px solid var(--line);
  background: var(--surface-2);
  padding: 12px 14px;
}
.version-history-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.version-list { display: flex; flex-direction: column; gap: 2px; margin-top: 8px; }
.version-row {
  display: flex; align-items: center; gap: 10px;
  width: 100%; min-height: 34px; padding: 4px 6px;
  border: 0; background: none; color: var(--ink-2);
  font-size: 12px; text-align: left; cursor: pointer;
}
.version-row:hover { background: var(--surface); color: var(--ink); }
.version-row.is-current { color: var(--ink); }
.version-meta { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; flex-wrap: wrap; }
.version-view { color: var(--brand); font-size: 11.5px; }
.version-preview { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--line); overflow-wrap: anywhere; }
.version-preview-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.version-stem { margin-top: 8px; font-family: var(--font-serif); font-size: 14px; line-height: 1.65; white-space: pre-wrap; }
.version-options { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; font-size: 12.5px; }
.version-option { display: flex; gap: 8px; }
.version-answer { display: flex; gap: 8px; margin-top: 8px; font-size: 12.5px; }
.version-explanation { margin-top: 8px; font-size: 12px; color: var(--ink-3); white-space: pre-wrap; }
.regrade-choice { display: flex; flex-direction: column; gap: 6px; }
.regrade-head { font-size: 12.5px; font-weight: 600; color: var(--ink); }
.check-row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-2); }
.conflict-actions { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.conflict-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
.bad-text { color: var(--bad); }
.modal-body-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 22px 0;
  overflow-y: auto;
}
.qe-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.options-group { gap: 8px; }
.options-header-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.options-list { display: flex; flex-direction: column; gap: 6px; }
.option-row { display: grid; grid-template-columns: 58px minmax(0, 1fr) 30px; gap: 7px; align-items: center; }
.opt-key-field { text-align: center; }
.btn-del-sm { color: var(--bad); }
.required { color: var(--bad); }
.modal-footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin: 4px -22px 0;
  padding: 14px 22px;
  border-top: 1px solid var(--line);
  background: var(--surface);
}
@media (max-width: 600px) {
  .modal-backdrop { padding: 10px; }
  .qe-grid { grid-template-columns: 1fr 1fr; }
  .modal-body-form { padding: 14px 16px 0; }
  .modal-header { padding: 15px 16px 12px; }
  .modal-footer { margin-left: -16px; margin-right: -16px; padding: 12px 16px; }
  .modal-head-right { gap: 6px; }
  .version-row { flex-wrap: wrap; }
  .version-view { margin-left: auto; }
}
@media (max-width: 400px) {
  .qe-grid { grid-template-columns: 1fr; }
  .option-row { grid-template-columns: 46px minmax(0, 1fr) 28px; }
  .conflict-buttons .btn { flex: 1 1 100%; justify-content: center; }
}
</style>
