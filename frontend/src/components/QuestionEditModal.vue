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
          <span v-if="question" class="version-tag mono">
            {{ t('bank_manage.version_badge', { ver: question.version_number }) }}
          </span>
          <button type="button" class="icon-btn" :aria-label="t('common.close')" @click="handleClose">
            <LinearIcon name="x" size="16" />
          </button>
        </div>
      </header>

      <form class="modal-body-form" @submit.prevent="handleSave">
        <div v-if="errorMsg" class="notice bad" role="alert">
          <span>{{ errorMsg }}</span>
          <button
            v-if="isConflict"
            type="button"
            class="btn btn-sm btn-quiet"
            :disabled="saving"
            @click="handleReloadLatest"
          >
            {{ t('bank_manage.reload_latest') }}
          </button>
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
import { updateQuestion, getQuestion, getQuestionConflict } from '../api/questions'
import { useLocale } from '../composables/useLocale'
import { validateQuestionEdit, sanitizeAnswerOnOptionRemove, adaptAnswerOnTypeChange } from '../domain/bankManage'

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

const emit = defineEmits(['close', 'saved', 'conflict'])

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

const isChoiceType = computed(() => {
  return ['SINGLE', 'MULTI', 'JUDGE'].includes(type.value)
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
      props.question.version_number = latestQ.version_number
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
      isConflict.value = false
      errorMsg.value = ''
    }
  } catch (err) {
    errorMsg.value = err?.message || 'Failed to reload latest question'
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

  saving.value = true
  errorMsg.value = ''

  const parsedTags = tagsInput.value
    ? tagsInput.value.split(/[,\s]+/).map(t => t.trim()).filter(Boolean)
    : []

  const payload = {
    stem: stem.value.trim(),
    type: type.value,
    options: isChoiceType.value ? options.value : [],
    answer: answer.value.trim(),
    explanation: explanation.value.trim(),
    difficulty: Number(difficulty.value),
    tags: parsedTags,
    chapter_id: chapterId.value ? chapterId.value : null,
    base_version_number: props.question.version_number,
    regrade_history: false,
    allow_stale_branch: false,
    reject_stale: true,
  }

  try {
    const updated = await updateQuestion(props.token, props.question.id, payload)
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
.modal-head-right { display: flex; align-items: center; gap: 10px; }
.version-tag { font-size: 10.5px; color: var(--ink-4); letter-spacing: .04em; }
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
}
@media (max-width: 400px) {
  .qe-grid { grid-template-columns: 1fr; }
}
</style>
