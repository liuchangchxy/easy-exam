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
          <h2 id="question-edit-title">
            {{ readOnly ? t('bank_manage.view_question') : t('bank_manage.edit_question') }}
          </h2>
          <span v-if="question" class="version-pill">
            {{ t('bank_manage.version_badge', { ver: question.version_number }) }}
          </span>
        </div>
        <button
          type="button"
          class="btn-close-modal"
          :aria-label="t('common.close')"
          @click="handleClose"
        >
          <LinearIcon name="x" size="14" />
        </button>
      </header>

      <form class="modal-body-form" @submit.prevent="handleSave">
        <div v-if="errorMsg" class="form-alert-error" role="alert">
          {{ errorMsg }}
        </div>

        <!-- 题干 -->
        <div class="form-group">
          <label for="edit-stem" class="form-label">
            {{ t('bank_manage.stem_label') }} <span class="required">*</span>
          </label>
          <textarea
            id="edit-stem"
            v-model.trim="stem"
            rows="3"
            class="form-textarea"
            :disabled="readOnly || saving"
            required
          ></textarea>
        </div>

        <!-- 题型与难度与所属章节 -->
        <div class="form-row-grid">
          <div class="form-group">
            <label for="edit-type" class="form-label">{{ t('bank_manage.type_label') }}</label>
            <select
              id="edit-type"
              v-model="type"
              class="form-select"
              :disabled="readOnly || saving"
            >
              <option value="SINGLE">{{ t('bank_manage.type_single') }}</option>
              <option value="MULTI">{{ t('bank_manage.type_multi') }}</option>
              <option value="JUDGE">{{ t('bank_manage.type_judge') }}</option>
              <option value="ESSAY">{{ t('bank_manage.type_essay') }}</option>
            </select>
          </div>

          <div class="form-group">
            <label for="edit-diff" class="form-label">{{ t('bank_manage.difficulty_label') }}</label>
            <select
              id="edit-diff"
              v-model.number="difficulty"
              class="form-select"
              :disabled="readOnly || saving"
            >
              <option :value="1">{{ t('bank_manage.diff_1') }}</option>
              <option :value="2">{{ t('bank_manage.diff_2') }}</option>
              <option :value="3">{{ t('bank_manage.diff_3') }}</option>
              <option :value="4">{{ t('bank_manage.diff_4') }}</option>
              <option :value="5">{{ t('bank_manage.diff_5') }}</option>
            </select>
          </div>

          <div class="form-group">
            <label for="edit-chap" class="form-label">{{ t('bank_manage.chapter_label') }}</label>
            <select
              id="edit-chap"
              v-model="chapterId"
              class="form-select"
              :disabled="readOnly || saving"
            >
              <option value="">{{ t('bank_manage.no_chapter') }}</option>
              <option v-for="c in chapters" :key="c.id" :value="c.id">
                {{ c.name }}
              </option>
            </select>
          </div>
        </div>

        <!-- 选项编辑 (针对单选、多选与判断) -->
        <div v-if="isChoiceType" class="form-group options-group">
          <div class="options-header-row">
            <label class="form-label">{{ t('bank_manage.options_label') }}</label>
            <button
              v-if="!readOnly && type !== 'JUDGE'"
              type="button"
              class="btn-util-sm"
              :disabled="saving"
              @click="addOption"
            >
              {{ t('bank_manage.add_option') }}
            </button>
          </div>

          <div class="options-list">
            <div
              v-for="(opt, idx) in options"
              :key="idx"
              class="option-row"
            >
              <input
                v-model.trim="opt.key"
                type="text"
                class="form-input opt-key-field"
                :placeholder="t('bank_manage.option_key_placeholder')"
                :disabled="readOnly || saving || type === 'JUDGE'"
                required
              />
              <input
                v-model="opt.content"
                type="text"
                class="form-input opt-content-field"
                :placeholder="t('bank_manage.option_content_placeholder')"
                :disabled="readOnly || saving"
                required
              />
              <button
                v-if="!readOnly && type !== 'JUDGE'"
                type="button"
                class="btn-del-sm"
                :disabled="saving || options.length <= 2"
                :title="t('bank_manage.remove_option')"
                @click="removeOption(idx)"
              >
                <LinearIcon name="trash" size="13" />
              </button>
            </div>
          </div>
        </div>

        <!-- 标准答案 -->
        <div class="form-group">
          <label for="edit-answer" class="form-label">
            {{ t('bank_manage.answer_label') }}
          </label>
          <input
            id="edit-answer"
            v-model.trim="answer"
            type="text"
            class="form-input"
            :disabled="readOnly || saving"
          />
        </div>

        <!-- 解析说明 -->
        <div class="form-group">
          <label for="edit-explanation" class="form-label">
            {{ t('bank_manage.explanation_label') }}
          </label>
          <textarea
            id="edit-explanation"
            v-model.trim="explanation"
            rows="3"
            class="form-textarea"
            :disabled="readOnly || saving"
          ></textarea>
        </div>

        <!-- 知识标签 -->
        <div class="form-group">
          <label for="edit-tags" class="form-label">
            {{ t('bank_manage.tags_label') }}
          </label>
          <input
            id="edit-tags"
            v-model="tagsInput"
            type="text"
            class="form-input"
            :disabled="readOnly || saving"
          />
        </div>

        <footer class="modal-footer">
          <button
            type="button"
            class="secondary-btn"
            :disabled="saving"
            @click="handleClose"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            v-if="!readOnly"
            type="submit"
            class="primary btn-submit-edit"
            :disabled="saving"
          >
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
import { updateQuestion, getQuestionConflict } from '../api/questions'
import { useLocale } from '../composables/useLocale'
import { validateQuestionEdit, sanitizeAnswerOnOptionRemove } from '../domain/bankManage'

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

const emit = defineEmits(['close', 'saved'])

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
    if (answer.value && answer.value.trim()) {
      const upper = answer.value.trim().toUpperCase()
      answer.value = (upper === 'T' || upper === 'F') ? upper : 'T'
    }
  } else if (newType === 'SINGLE') {
    if (!options.value.length || options.value.length < 2) {
      options.value = [
        { key: 'A', content: '' },
        { key: 'B', content: '' },
        { key: 'C', content: '' },
        { key: 'D', content: '' },
      ]
    }
    if (answer.value && answer.value.trim()) {
      const validKeys = options.value.map(o => o.key.trim()).filter(Boolean)
      if (!validKeys.includes(answer.value.trim())) {
        answer.value = validKeys[0] || 'A'
      }
    }
  } else if (newType === 'MULTI') {
    if (!options.value.length || options.value.length < 2) {
      options.value = [
        { key: 'A', content: '' },
        { key: 'B', content: '' },
        { key: 'C', content: '' },
        { key: 'D', content: '' },
      ]
    }
    if (answer.value && answer.value.trim()) {
      const validKeys = new Set(options.value.map(o => o.key.trim()).filter(Boolean))
      const parts = answer.value.split(/[,;\s]+/).map(k => k.trim()).filter(Boolean)
      const validParts = parts.filter(k => validKeys.has(k))
      answer.value = validParts.length ? validParts.join(',') : (options.value[0]?.key || 'A')
    }
  } else if (newType === 'ESSAY') {
    options.value = []
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
    errorMsg.value = err?.detail || err?.message || t('bank_manage.save_error', { error: 'Request failed' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
  backdrop-filter: blur(4px);
}

.question-edit-dialog {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg, 12px);
  width: 100%;
  max-width: 680px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
}

.modal-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.modal-title-wrap h2 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
  color: var(--fg-default);
}

.version-pill {
  font-size: 0.75rem;
  font-family: var(--linear-mono, monospace);
  padding: 0.15rem 0.5rem;
  background: var(--bg-subtle, rgba(255, 255, 255, 0.06));
  border: 1px solid var(--border-subtle);
  border-radius: 9999px;
  color: var(--primary);
  font-weight: 600;
}

.btn-close-modal {
  background: transparent;
  border: none;
  color: var(--fg-muted);
  cursor: pointer;
  padding: 0.4rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close-modal:hover {
  background: var(--bg-subtle);
  color: var(--fg-default);
}

.modal-body-form {
  padding: 1.25rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-alert-error {
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #ef4444;
  font-size: 0.875rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--fg-muted);
}

.form-label .required {
  color: #ef4444;
}

.form-input,
.form-textarea,
.form-select {
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: var(--bg-input, var(--bg-page));
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--fg-default);
  font-size: 0.875rem;
  font-family: inherit;
  transition: border-color 0.15s ease;
}

.form-input:focus,
.form-textarea:focus,
.form-select:focus {
  outline: none;
  border-color: var(--primary);
}

.form-input:disabled,
.form-textarea:disabled,
.form-select:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.form-row-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.options-group {
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 0.75rem;
  background: var(--bg-subtle, rgba(0, 0, 0, 0.02));
}

.options-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.btn-util-sm {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  color: var(--primary);
  cursor: pointer;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.opt-key-field {
  width: 5rem;
  text-align: center;
  font-weight: 600;
}

.opt-content-field {
  flex: 1;
}

.btn-del-sm {
  background: transparent;
  border: none;
  color: var(--fg-muted);
  cursor: pointer;
  padding: 0.4rem;
  border-radius: 4px;
}

.btn-del-sm:hover:not(:disabled) {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}

.btn-del-sm:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.modal-footer {
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.625rem;
}

@media (max-width: 600px) {
  .question-edit-dialog {
    max-height: 95vh;
  }
  .form-row-grid {
    grid-template-columns: 1fr;
  }
  .opt-key-field {
    width: 3.5rem;
  }
}
</style>
