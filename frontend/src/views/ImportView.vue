<template>
  <main class="import-page">
    <header class="page-header import-header">
      <div class="header-left">
        <button type="button" class="btn-back" @click="$emit('back')">← {{ t('common.back') }}</button>
        <h1>{{ t('imports.title') }}</h1>
      </div>
    </header>
    <form class="bank-card import-form" @submit.prevent="submit">
      <label>{{ t('ui.k0322') }}
        <select v-model="bankId" required>
          <option value="" disabled>{{ t('ui.k0323') }}</option>
          <option v-for="bank in banks" :key="bank.id" :value="bank.id">{{ bank.name }}</option>
        </select>
      </label>
      <div
        class="file-upload-card"
        :class="{ 'drag-over': isDragging, 'has-file': Boolean(file) }"
        @dragenter.prevent="isDragging = true"
        @dragover.prevent="isDragging = true"
        @dragleave="onDragLeave"
        @drop.prevent="onDropFile"
      >
        <template v-if="isDragging">
          <div class="drag-active-notice">
            <LinearIcon name="upload-cloud" size="32" />
            <strong>{{ t('imports.drag_drop_release') }}</strong>
          </div>
        </template>
        <template v-else-if="file">
          <div class="file-card-inner file-selected-row">
            <span class="file-upload-icon active-icon">
              <LinearIcon name="file" size="24" />
            </span>
            <div class="file-card-text">
              <span style="font-size: 0.8rem; color: var(--text-muted);">{{ t('imports.file_selected') }}</span>
              <strong class="selected-file-name">{{ file.name }}</strong>
              <small class="selected-file-size font-mono-code">{{ (file.size / 1024).toFixed(1) }} KB</small>
            </div>
            <button type="button" class="btn-change-file" @click="triggerFileInput">
              {{ t('imports.change_file') }}
            </button>
          </div>
        </template>
        <template v-else>
          <div class="file-card-inner">
            <span class="file-upload-icon">
              <LinearIcon name="inbox" size="24" />
            </span>
            <div class="file-card-text">
              <strong>{{ t('imports.drag_drop_prompt') }}</strong>
              <small>{{ t('ui.k0325') }}</small>
            </div>
          </div>
        </template>
        <input
          ref="fileInputRef"
          type="file"
          accept=".xlsx,.csv,.json,.txt,.md,.markdown,.pdf"
          :required="!file"
          @change="selectFile"
          class="file-styled-input"
        />
        <div class="file-format-tags">
          <span class="format-tag">.xlsx</span>
          <span class="format-tag">.csv</span>
          <span class="format-tag">.json</span>
          <span class="format-tag">.md / .txt</span>
          <span class="format-tag">.pdf</span>
        </div>
      </div>

      <div v-if="isSpreadsheet && !spreadsheetPreview" class="preview-actions">
        <button type="button" class="preview-btn" :disabled="loading || !bankId || !file" @click="inspectSpreadsheet">
          {{ loading ? t('ui.k0689') : t('ui.k0690') }}
        </button>
      </div>

      <div v-if="isPdf && !pdfPreview" class="preview-actions">
        <button type="button" class="preview-btn" :disabled="loading || !bankId || !file" @click="inspectPdf">
          {{ loading ? t('ui.k0691') : t('ui.k0692') }}
        </button>
      </div>

      <!-- Exameow-style Column Mapping Preview Panel -->
      <section v-if="spreadsheetPreview" class="column-mapping-panel">
        <h3>{{ t('ui.k0326') }}</h3>
        <p class="mapping-hint">{{ t('ui.k0327') }}</p>
        <div class="mapping-grid">
          <label>{{ t('ui.k0328') }}
            <select id="select-stem" v-model.number="currentMapping.stem">
              <option :value="null">{{ t('ui.k0329') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0330') }}
            <select id="select-answer" v-model.number="currentMapping.answer">
              <option :value="null">{{ t('ui.k0329') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0331') }}
            <select id="select-type" v-model.number="currentMapping.type">
              <option :value="null">{{ t('ui.k0332') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0333') }}
            <select id="select-explanation" v-model.number="currentMapping.explanation">
              <option :value="null">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0335') }}
            <select id="select-difficulty" v-model.number="currentMapping.difficulty">
              <option :value="null">{{ t('ui.k0336') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0337') }}
            <select id="select-tags" v-model.number="currentMapping.tags">
              <option :value="null">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0338') }}
            <select id="select-combined-options" v-model.number="currentMapping.combined_options">
              <option :value="null">{{ t('ui.k0339') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label v-if="currentMapping.combined_options !== null">{{ t('ui.k0340') }}
            <select id="select-options-delimiter" v-model="currentMapping.options_delimiter">
              <option value="">{{ t('ui.k0341') }}</option>
              <option value="prefix">{{ t('ui.k0342') }}</option>
              <option value=";">{{ t('ui.k0343') }}</option>
              <option value="；">{{ t('ui.k0344') }}</option>
              <option value="\n">{{ t('ui.k0345') }}</option>
              <option value="|">{{ t('ui.k0346') }}</option>
              <option value="、">{{ t('ui.k0347') }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0348') }}
            <select id="select-opt-a" :value="getOptionCol(0)" @change="setOptionCol(0, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0349') }}
            <select id="select-opt-b" :value="getOptionCol(1)" @change="setOptionCol(1, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0350') }}
            <select id="select-opt-c" :value="getOptionCol(2)" @change="setOptionCol(2, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0351') }}
            <select id="select-opt-d" :value="getOptionCol(3)" @change="setOptionCol(3, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0352') }}
            <select id="select-opt-e" :value="getOptionCol(4)" @change="setOptionCol(4, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0353') }}
            <select id="select-opt-f" :value="getOptionCol(5)" @change="setOptionCol(5, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0354') }}
            <select id="select-opt-g" :value="getOptionCol(6)" @change="setOptionCol(6, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0355') }}
            <select id="select-opt-h" :value="getOptionCol(7)" @change="setOptionCol(7, $event.target.value)">
              <option value="">{{ t('ui.k0334') }}</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
        </div>

        <div v-if="spreadsheetPreview.missing?.length" class="error missing-warning">
          {{ t('ui.k0356') }}{{ spreadsheetPreview.missing.join(', ') }}{{ t('ui.k0357') }}
        </div>

        <div v-if="spreadsheetPreview.preview_rows?.length" class="sample-table-container">
          <h4>{{ t('ui.k0358') }} {{ spreadsheetPreview.preview_rows.length }} {{ t('ui.k0359') }}</h4>
          <table class="sample-table">
            <thead>
              <tr>
                <th v-for="(h, idx) in spreadsheetPreview.headers" :key="idx">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rIdx) in spreadsheetPreview.preview_rows" :key="rIdx">
                <td v-for="(cell, cIdx) in row" :key="cIdx">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- EE-021: PDF 人工校正草稿面板 -->
      <section v-if="pdfPreview" class="column-mapping-panel pdf-correction-panel" style="margin-top: 1rem; border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <h3 style="color: var(--text-main);">{{ t('ui.k0360') }}</h3>
          <span :style="{ fontSize: '0.8rem', padding: '0.25rem 0.6rem', borderRadius: '4px', fontWeight: 'bold', background: pdfPreview.confidence === 'HIGH' ? 'var(--success-light)' : 'var(--warning-light)', color: pdfPreview.confidence === 'HIGH' ? 'var(--success)' : 'var(--warning)' }">
            {{ pdfPreview.confidence === 'HIGH' ? t('ui.k0693') : t('ui.k0694') }}
          </span>
        </div>
        <p class="mapping-hint" style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">
          {{ t('ui.k0361') }} {{ pdfCandidates.length }} {{ t('ui.k0362') }}
        </p>

        <div style="display: flex; flex-direction: column; gap: 1rem;">
          <div v-for="(cand, cIdx) in pdfCandidates" :key="cIdx" style="border: 1px solid var(--border); border-radius: 8px; padding: 1rem; background: var(--bg-subtle);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <span style="font-weight: 600; font-size: 0.9rem; color: var(--text-main);">{{ t('ui.k0082') }} {{ cIdx + 1 }} {{ t('ui.k0101') }}</span>
              <div style="display: flex; gap: 0.5rem;">
                <button v-if="cIdx > 0" type="button" class="action-link-btn" style="font-size: 0.75rem;" @click="mergeWithPrev(cIdx)">{{ t('ui.k0363') }}</button>
                <button type="button" class="action-link-btn" style="font-size: 0.75rem;" @click="splitCandidate(cIdx)">{{ t('ui.k0364') }}</button>
                <button type="button" class="action-link-btn" style="font-size: 0.75rem; color: var(--danger);" @click="removeCandidate(cIdx)">{{ t('ui.k0256') }}</button>
              </div>
            </div>

            <div v-if="cand.is_uncertain" style="padding: 0.4rem 0.6rem; background: var(--warning-light); border: 1px solid var(--warning-border); border-radius: 4px; font-size: 0.8rem; color: var(--warning); margin-bottom: 0.5rem;">
              {{ t('ui.k0365') }}{{ cand.uncertain_reason }}
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.5rem;">
              <label style="font-size: 0.8rem;">{{ t('ui.k0366') }}
                <select v-model="cand.type" style="width: 100%; margin-top: 0.2rem;">
                  <option value="SINGLE">{{ t('ui.k0050') }}</option>
                  <option value="MULTI">{{ t('ui.k0051') }}</option>
                  <option value="JUDGE">{{ t('ui.k0052') }}</option>
                  <option value="QA">{{ t('ui.k0367') }}</option>
                </select>
              </label>
              <label style="font-size: 0.8rem;">{{ t('ui.k0368') }}
                <input v-model="cand.answer" :placeholder="t('ui.k0369')" style="width: 100%; margin-top: 0.2rem;" />
              </label>
            </div>

            <label style="font-size: 0.8rem; display: block; margin-bottom: 0.5rem;">{{ t('ui.k0211') }}
              <textarea v-model="cand.stem" rows="2" style="width: 100%; margin-top: 0.2rem;"></textarea>
            </label>

            <div v-if="cand.type === 'SINGLE' || cand.type === 'MULTI'" style="margin-bottom: 0.5rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.8rem; font-weight: 500;">{{ t('ui.k0370') }}</span>
                <button type="button" class="action-link-btn" style="font-size: 0.75rem;" @click="addCandidateOption(cand)">{{ t('ui.k0371') }}</button>
              </div>
              <div v-for="(opt, optIdx) in cand.options" :key="optIdx" style="display: flex; gap: 0.4rem; margin-top: 0.25rem;">
                <input v-model="opt.key" style="width: 3rem;" placeholder="A" />
                <input v-model="opt.content" style="flex: 1;" :placeholder="t('ui.k0177')" />
                <button type="button" style="color: var(--danger); border: none; background: none; cursor: pointer;" @click="cand.options.splice(optIdx, 1)">×</button>
              </div>
            </div>

            <label style="font-size: 0.8rem; display: block;">{{ t('ui.k0372') }}
              <input v-model="cand.explanation" :placeholder="t('ui.k0373')" style="width: 100%; margin-top: 0.2rem;" />
            </label>
          </div>
        </div>

        <div class="preview-actions" style="margin-top: 1rem; display: flex; gap: 0.75rem;">
          <button type="button" class="primary" :disabled="loading || !pdfCandidates.length" @click="confirmPdfImportAction">
            {{ loading ? t('ui.k0678') : t('ui.k0695') }}
          </button>
          <button type="button" @click="pdfPreview = null">{{ t('ui.k0374') }}</button>
        </div>
      </section>

      <p v-if="duplicatePreview" class="warning">{{ t('ui.k0375') }} {{ duplicatePreview.duplicates?.length || 0 }} {{ t('ui.k0376') }}</p>
      <label v-if="duplicatePreview">{{ t('ui.k0377') }}
        <select v-model="duplicateStrategy">
          <option value="skip">{{ t('ui.k0378') }}</option>
          <option value="new">{{ t('ui.k0379') }}</option>
          <option value="merge">{{ t('ui.k0380') }}</option>
        </select>
      </label>

      <p v-if="error" class="error">{{ errorText }}</p>
      <p v-if="result" class="success">{{ t('ui.k0381') }} {{ result.imported_count }} {{ t('ui.k0382') }} {{ result.job_id }}</p>

      <button type="submit" class="primary btn-submit-import" :disabled="loading || !bankId || !file">
        {{ loading ? t('ui.k0696') : duplicatePreview ? t('ui.k0697') : spreadsheetPreview ? t('ui.k0698') : t('ui.k0699') }}
      </button>
    </form>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import { listBanks } from '../api/banks'
import { previewFileImport, uploadImport, previewPdfImport, confirmPdfImport } from '../api/imports'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({ token: { type: String, required: true } })
defineEmits(['back'])
const banks = ref([])
const bankId = ref('')
const file = ref(null)
const isDragging = ref(false)
const fileInputRef = ref(null)
const loading = ref(false)
const error = ref(null)
const errorText = computed(() => {
  if (error.value instanceof Error) return error.value.message
  return typeof error.value === 'string' ? error.value : ''
})
const result = ref(null)
const duplicatePreview = ref(null)
const duplicateStrategy = ref('skip')
const spreadsheetPreview = ref(null)
const pdfPreview = ref(null)
const pdfCandidates = ref([])
const currentMapping = ref({
  stem: null,
  answer: null,
  type: null,
  explanation: null,
  difficulty: null,
  tags: null,
  combined_options: null,
  options_delimiter: '',
  options: [],
})

const isSpreadsheet = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.xlsx') || name.endsWith('.csv')
})

const isPdf = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.pdf')
})

const optionSlots = ref(Array(8).fill(''))

function syncOptionsFromSlots() {
  const slots = optionSlots.value.map(v => (v !== '' && v !== null && v !== undefined ? Number(v) : null))
  let lastIdx = -1
  for (let i = slots.length - 1; i >= 0; i--) {
    if (slots[i] !== null) {
      lastIdx = i
      break
    }
  }
  currentMapping.value.options = lastIdx >= 0 ? slots.slice(0, lastIdx + 1) : []
}

function getOptionCol(index) {
  return optionSlots.value[index] || ''
}

function setOptionCol(index, rawVal) {
  optionSlots.value[index] = rawVal !== undefined && rawVal !== null ? String(rawVal) : ''
  syncOptionsFromSlots()
}

function handleSelectedFile(selected) {
  file.value = selected || null
  result.value = null
  duplicatePreview.value = null
  spreadsheetPreview.value = null
  pdfPreview.value = null
  pdfCandidates.value = []
  optionSlots.value = Array(8).fill('')
  error.value = ''
}

function selectFile(event) {
  handleSelectedFile(event.target.files?.[0] || null)
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onDropFile(event) {
  isDragging.value = false
  const dropped = event.dataTransfer?.files?.[0]
  if (!dropped) return
  const validExts = ['.xlsx', '.csv', '.json', '.txt', '.md', '.markdown', '.pdf']
  const lower = dropped.name.toLowerCase()
  if (!validExts.some(ext => lower.endsWith(ext))) {
    error.value = t('imports.supported_formats')
    return
  }
  handleSelectedFile(dropped)
}

function onDragLeave(event) {
  if (event.currentTarget && event.relatedTarget && event.currentTarget.contains(event.relatedTarget)) return
  isDragging.value = false
}

onMounted(async () => {
  try {
    banks.value = await listBanks(props.token)
  } catch (err) {
    error.value = err instanceof Error ? err : new Error(t('ui.k0472'))
  }
})

async function inspectSpreadsheet() {
  if (!file.value || !bankId.value) return
  loading.value = true
  error.value = ''
  try {
    const prev = await previewFileImport(props.token, bankId.value, file.value)
    spreadsheetPreview.value = prev
    if (prev.mapping) {
      currentMapping.value = { ...currentMapping.value, ...prev.mapping }
      optionSlots.value = Array(8).fill('')
      if (Array.isArray(prev.mapping.options)) {
        prev.mapping.options.slice(0, 8).forEach((colIdx, slotIdx) => {
          optionSlots.value[slotIdx] = colIdx !== null && colIdx !== undefined ? String(colIdx) : ''
        })
      }
      syncOptionsFromSlots()
    }
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}

async function inspectPdf() {
  if (!file.value || !bankId.value) return
  loading.value = true
  error.value = ''
  try {
    const prev = await previewPdfImport(props.token, bankId.value, file.value)
    pdfPreview.value = prev
    pdfCandidates.value = JSON.parse(JSON.stringify(prev.candidates || []))
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}

function mergeWithPrev(idx) {
  if (idx <= 0) return
  const current = pdfCandidates.value[idx]
  const prev = pdfCandidates.value[idx - 1]
  prev.stem += '\n' + current.stem
  if (current.options && current.options.length) {
    prev.options = [...(prev.options || []), ...current.options]
  }
  if (!prev.answer && current.answer) {
    prev.answer = current.answer
  }
  if (current.explanation) {
    prev.explanation = (prev.explanation ? prev.explanation + '\n' : '') + current.explanation
  }
  pdfCandidates.value.splice(idx, 1)
}

function splitCandidate(idx) {
  const item = pdfCandidates.value[idx]
  const half = Math.floor(item.stem.length / 2)
  const newStem = item.stem.slice(half).trim() || t('ui.k0383')
  item.stem = item.stem.slice(0, half).trim()
  pdfCandidates.value.splice(idx + 1, 0, {
    candidate_id: pdfCandidates.value.length + 1,
    type: item.type,
    stem: newStem,
    options: [],
    answer: '',
    explanation: '',
    difficulty: item.difficulty || 3,
    tags: item.tags || [],
    is_uncertain: true,
    uncertain_reason: t('ui.k0384'),
  })
}

function removeCandidate(idx) {
  pdfCandidates.value.splice(idx, 1)
}

function addCandidateOption(cand) {
  if (!cand.options) cand.options = []
  const nextKey = String.fromCharCode(65 + cand.options.length)
  cand.options.push({ key: nextKey, content: '' })
}

async function confirmPdfImportAction() {
  if (!pdfPreview.value || !pdfCandidates.value.length) return
  loading.value = true
  error.value = ''
  try {
    result.value = await confirmPdfImport(props.token, bankId.value, {
      draft_id: pdfPreview.value.draft_id,
      questions: pdfCandidates.value,
      duplicate_strategy: 'skip',
    })
    pdfPreview.value = null
    pdfCandidates.value = []
  } catch (err) {
    error.value = err
  } finally {
    loading.value = false
  }
}

async function submit() {
  // If user selected spreadsheet and hasn't previewed it yet, preview first
  if (isSpreadsheet.value && !spreadsheetPreview.value && !duplicatePreview.value) {
    await inspectSpreadsheet()
    return
  }

  loading.value = true
  error.value = ''
  result.value = null
  try {
    if (spreadsheetPreview.value) {
      syncOptionsFromSlots()
    }
    const mappingToSend = spreadsheetPreview.value ? currentMapping.value : null
    result.value = await uploadImport(
      props.token,
      bankId.value,
      file.value,
      duplicatePreview.value ? duplicateStrategy.value : 'prompt',
      mappingToSend,
    )
    duplicatePreview.value = null
    spreadsheetPreview.value = null
  } catch (err) {
    if (err.status === 409 && err.detail && typeof err.detail === 'object') {
      duplicatePreview.value = err.detail
    } else {
      error.value = err
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.import-page {
  width: min(100% - 2rem, 74rem);
  margin: 1.5rem auto;
}

.import-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
}

.import-header .header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.import-form {
  display: grid;
  gap: 1.25rem;
  max-width: 48rem;
  background: var(--bg-card);
  padding: 2rem;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  margin: 0 auto;
}

.file-upload-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.5rem;
  border: 2px dashed var(--primary-border);
  background: var(--primary-light);
  border-radius: var(--radius-lg);
  transition: all 0.2s ease;
  position: relative;
}

.file-upload-card.drag-over {
  border-color: var(--primary);
  background: var(--bg-hover, rgba(37, 99, 235, 0.08));
  transform: scale(1.01);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
}

.file-upload-card.has-file {
  border-style: solid;
  border-color: var(--border-strong);
  background: var(--bg-card);
}

.drag-active-notice {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  gap: 0.5rem;
  color: var(--primary);
  pointer-events: none;
}

.file-selected-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.selected-file-name {
  font-size: 0.95rem;
  color: var(--text-main);
  word-break: break-all;
}

.selected-file-size {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.btn-change-file {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-main);
  cursor: pointer;
  white-space: nowrap;
}

.btn-change-file:hover {
  background: var(--bg-subtle);
  border-color: var(--border-strong);
}

.file-card-inner {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.file-upload-icon {
  font-size: 2rem;
}

.file-card-text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.file-card-text strong {
  font-size: 0.95rem;
  color: var(--text-main);
}

.file-card-text small {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.file-styled-input {
  width: 100%;
  padding: 0.45rem;
  background: var(--bg-card);
  color: var(--text-main);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  cursor: pointer;
}

.file-format-tags {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.format-tag {
  font-size: 0.725rem;
  padding: 0.15rem 0.45rem;
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 600;
  border-radius: 4px;
}

.import-form label {
  display: grid;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-main);
}

.import-form select {
  width: 100%;
}

.btn-submit-import {
  padding: 0.75rem 1.5rem;
  font-size: 0.95rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  margin-top: 0.5rem;
}

.preview-actions {
  margin: 0.5rem 0;
}

.preview-btn {
  background: var(--bg-muted);
  color: var(--text-main);
  border: 1px solid var(--border-strong);
}

.preview-btn:hover:not(:disabled) {
  background: var(--bg-subtle);
}

.column-mapping-panel {
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  margin: 0.5rem 0;
}

.column-mapping-panel h3 {
  font-size: 1.05rem;
  margin-bottom: 0.35rem;
}

.mapping-hint {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.mapping-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0.85rem;
  margin-bottom: 1rem;
}

.missing-warning {
  margin-bottom: 0.75rem;
}

.sample-table-container {
  overflow-x: auto;
  max-height: 15rem;
  margin-top: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.sample-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.sample-table th,
.sample-table td {
  border: 1px solid var(--border);
  padding: 0.45rem 0.75rem;
  text-align: left;
  white-space: nowrap;
}

.sample-table th {
  background: var(--bg-muted);
  font-weight: 600;
}

@media (max-width: 640px) {
  .import-page {
    width: min(100% - 1rem, 74rem);
    margin: 0.75rem auto;
  }
  .import-form {
    padding: 1.25rem;
  }
}
</style>
