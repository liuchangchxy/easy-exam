<template>
  <div class="import-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">
          <button type="button" class="link-btn" @click="$router.push('/banks')">{{ t('ep.banks.title') }}</button>
          <span aria-hidden="true">/</span>
        </div>
        <h1 class="page-title">{{ t('ep.imports.title') }}</h1>
        <p class="page-sub">{{ t('ep.imports.sub') }}</p>
      </div>
    </div>

    <ol class="import-steps" :aria-label="importCopy.stepsLabel">
      <li
        v-for="(step, idx) in steps"
        :key="step.key"
        class="import-step"
        :class="{ 'is-active': stepNo === idx + 1, 'is-done': stepNo > idx + 1 }"
        :data-step-state="stepState(idx + 1)"
        :aria-current="stepNo === idx + 1 ? 'step' : undefined"
      >
        <span class="step-idx mono">{{ String(idx + 1).padStart(2, '0') }}</span>
        <span class="step-label">{{ step.label }}</span>
        <span class="step-state">{{ stepStateLabel(idx + 1) }}</span>
      </li>
    </ol>
    <div
      class="import-progress"
      role="progressbar"
      :aria-label="importCopy.stepsLabel"
      :aria-valuemin="1"
      :aria-valuemax="4"
      :aria-valuenow="stepNo"
    >
      <i :style="{ width: `${stepPercent}%` }"></i>
    </div>

    <section v-if="previewing || precheckPanel" class="import-precheck-panel" aria-live="polite">
      <div class="import-precheck-panel-head">
        <span class="rule-label">{{ importCopy.precheckTitle }}</span>
        <span class="tag" :class="precheckPanel && precheckPanel.accepted ? 'ok' : 'warn'">
          {{ previewing && !precheckPanel ? importCopy.prechecking : precheckPanel?.status }}
        </span>
      </div>
      <div v-if="precheckPanel" class="import-precheck-grid">
        <div class="import-precheck-cell">
          <b>{{ precheckPanel.count }}</b>
          <span>{{ importCopy.parsed }}</span>
        </div>
        <div class="import-precheck-cell">
          <b :class="{ 'is-warn': precheckPanel.duplicates > 0 }">{{ precheckPanel.duplicates }}</b>
          <span>{{ importCopy.duplicates }}</span>
        </div>
        <div class="import-precheck-cell">
          <b :class="{ 'is-warn': precheckPanel.attention > 0 }">{{ precheckPanel.attention }}</b>
          <span>{{ importCopy.needsAttention }}</span>
        </div>
      </div>
      <p v-else class="import-precheck-loading">{{ importCopy.prechecking }}</p>
    </section>

    <div class="import-layout">
      <div class="import-main">
        <form class="import-form" @submit.prevent="submit">
          <section class="step-block">
            <div class="step-head">
              <span class="step-no mono">01</span>
              <div>
                <div class="step-title">{{ t('ep.imports.step_source') }}</div>
                <div class="step-sub">{{ t('ep.imports.preview_hint') }}</div>
              </div>
            </div>

            <div class="field" style="margin-bottom: 18px">
              <label class="label" for="import-bank">{{ t('ep.imports.bank') }}</label>
              <select id="import-bank" v-model="bankId" class="select" required>
                <option value="" disabled>{{ t('ep.imports.bank_placeholder') }}</option>
                <option v-for="bank in banks" :key="bank.id" :value="bank.id">{{ bank.name }} · {{ t('ep.banks.questions', { count: bank.question_count || 0 }) }}</option>
              </select>
            </div>

            <div v-if="bankId && !canImport" class="notice warn" style="margin-bottom: 16px">
              <LinearIcon name="lock" :size="15" />
              <span>{{ t('ep.imports.readonly_bank') }}</span>
            </div>

            <div
              class="file-drop"
              :class="{ 'is-dragging': isDragging, 'has-file': Boolean(file) }"
              @dragenter.prevent="isDragging = true"
              @dragover.prevent="isDragging = true"
              @dragleave="onDragLeave"
              @drop.prevent="onDropFile"
            >
              <template v-if="isDragging">
                <LinearIcon name="upload" :size="22" />
                <strong>{{ t('ep.imports.release') }}</strong>
              </template>
              <template v-else-if="file">
                <span class="file-icon"><LinearIcon name="file" :size="20" /></span>
                <span class="file-main">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-meta">{{ t('ep.imports.size', { size: (file.size / 1024).toFixed(1) }) }}</span>
                </span>
                <button type="button" class="btn btn-sm" @click="triggerFileInput">{{ t('ep.imports.change') }}</button>
              </template>
              <template v-else>
                <span class="file-icon"><LinearIcon name="inbox" :size="20" /></span>
                <span class="file-main">
                  <span class="file-name">{{ t('ep.imports.drop') }}</span>
                  <span class="file-meta">{{ t('ep.imports.drop_hint') }}</span>
                </span>
                <button type="button" class="btn btn-sm" @click="triggerFileInput">{{ t('ep.imports.choose') }}</button>
              </template>
              <input
                ref="fileInputRef"
                type="file"
                accept=".xlsx,.csv,.json,.txt,.md,.markdown,.pdf"
                :required="!file"
                class="file-input-hidden"
                @change="selectFile"
              />
            </div>

            <div class="file-formats">
              <span class="tag mono">.xlsx</span>
              <span class="tag mono">.csv</span>
              <span class="tag mono">.json</span>
              <span class="tag mono">.md / .txt</span>
              <span class="tag mono">.pdf</span>
            </div>

            <div v-if="!spreadsheetPreview && !pdfPreview && !textPreview && !duplicatePreview && !result" class="import-actions">
              <button v-if="isSpreadsheet" type="button" class="btn btn-primary" :disabled="loading || previewing || !bankId || !file || !canImport" @click="inspectSpreadsheet">
                {{ loading ? t('ep.imports.uploading') : t('ep.imports.inspect_sheet') }}
              </button>
              <button v-else-if="isPdf" type="button" class="btn btn-primary" :disabled="loading || previewing || !bankId || !file || !canImport" @click="inspectPdf">
                {{ loading ? t('ep.imports.uploading') : t('ep.imports.inspect_pdf') }}
              </button>
              <button v-else type="button" class="btn btn-primary" :disabled="loading || previewing || !bankId || !file || !canImport" @click="inspectText">
                {{ loading || previewing ? t('ep.imports.uploading') : t('ep.imports.submit_preview') }}
              </button>
            </div>
          </section>

          <!-- Spreadsheet field mapping -->
          <section v-if="spreadsheetPreview" class="step-block">
            <div class="step-head">
              <span class="step-no mono">03</span>
              <div>
                <div class="step-title">{{ t('ep.imports.fields_title') }}</div>
                <div class="step-sub">{{ t('ep.imports.fields_hint') }}</div>
              </div>
            </div>

            <div class="mapping-grid">
              <label class="field">
                <span class="label">{{ t('ep.imports.col_stem') }}</span>
                <select v-model.number="currentMapping.stem" class="select">
                  <option :value="null">{{ t('ep.imports.none') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.imports.col_answer') }}</span>
                <select v-model.number="currentMapping.answer" class="select">
                  <option :value="null">{{ t('ep.imports.none') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.imports.col_type') }}</span>
                <select v-model.number="currentMapping.type" class="select">
                  <option :value="null">{{ t('ep.imports.auto') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.imports.col_explanation') }}</span>
                <select v-model.number="currentMapping.explanation" class="select">
                  <option :value="null">{{ t('ep.imports.none') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.imports.col_difficulty') }}</span>
                <select v-model.number="currentMapping.difficulty" class="select">
                  <option :value="null">{{ t('ep.imports.none') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.imports.col_tags') }}</span>
                <select v-model.number="currentMapping.tags" class="select">
                  <option :value="null">{{ t('ep.imports.none') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.imports.col_options') }}</span>
                <select v-model.number="currentMapping.combined_options" class="select">
                  <option :value="null">{{ t('ep.imports.none') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
              <label v-if="currentMapping.combined_options !== null" class="field">
                <span class="label">{{ t('ep.imports.delimiter') }}</span>
                <select v-model="currentMapping.options_delimiter" class="select">
                  <option value="">{{ t('ep.imports.auto') }}</option>
                  <option value="prefix">{{ t('ep.imports.delimiter_prefix') }}</option>
                  <option value=";">{{ t('ep.imports.delimiter_semicolon') }}</option>
                  <option value="；">{{ t('ep.imports.delimiter_cn_semicolon') }}</option>
                  <option value="\n">{{ t('ep.imports.delimiter_newline') }}</option>
                  <option value="|">{{ t('ep.imports.delimiter_pipe') }}</option>
                  <option value="、">{{ t('ep.imports.delimiter_dunhao') }}</option>
                </select>
              </label>
              <label v-for="(letter, slotIdx) in optionLetters" :key="letter" class="field">
                <span class="label">{{ t('ep.imports.col_option', { letter }) }}</span>
                <select :value="getOptionCol(slotIdx)" class="select" @change="setOptionCol(slotIdx, $event.target.value)">
                  <option value="">{{ t('ep.imports.none') }}</option>
                  <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
                </select>
              </label>
            </div>

            <div v-if="spreadsheetPreview.missing?.length" class="notice warn" style="margin-top: 14px">
              <LinearIcon name="alert" :size="15" />
              <span>{{ t('ep.imports.missing_fields') }}{{ spreadsheetPreview.missing.join(', ') }}</span>
            </div>

            <div v-if="spreadsheetPreview.preview_rows?.length" class="sample-block">
              <div class="rule-label">{{ t('ep.imports.sample') }} · {{ t('ep.imports.rows', { count: spreadsheetPreview.preview_rows.length }) }}</div>
              <div class="sample-scroll">
                <table class="sample-table">
                  <thead>
                    <tr><th v-for="(h, idx) in spreadsheetPreview.headers" :key="idx">{{ h }}</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, rIdx) in spreadsheetPreview.preview_rows" :key="rIdx">
                      <td v-for="(cell, cIdx) in row" :key="cIdx">{{ cell }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="import-actions">
              <button type="submit" class="btn btn-primary" :disabled="loading || !bankId || !file || !canImport">
                {{ loading ? t('ep.imports.uploading') : t('ep.imports.submit_import') }}
              </button>
              <button type="button" class="btn btn-quiet" @click="spreadsheetPreview = null">{{ t('ep.imports.cancel_preview') }}</button>
            </div>
          </section>

          <!-- PDF correction draft -->
          <section v-if="pdfPreview" class="step-block">
            <div class="step-head">
              <span class="step-no mono">03</span>
              <div>
                <div class="step-title">{{ t('ep.imports.pdf_title') }}</div>
                <div class="step-sub">{{ t('ep.imports.pdf_hint') }}</div>
              </div>
              <span class="tag" :class="pdfPreview.confidence === 'HIGH' ? 'ok' : 'warn'">
                {{ pdfPreview.confidence === 'HIGH' ? t('ep.imports.pdf_high') : t('ep.imports.pdf_low') }}
              </span>
            </div>

            <div v-if="pdfCandidates.length" class="pdf-list">
              <article v-for="(cand, cIdx) in pdfCandidates" :key="cIdx" class="pdf-card">
                <div class="pdf-card-head">
                  <span class="mono small">{{ t('ep.imports.candidate_no', { index: cIdx + 1 }) }}</span>
                  <span class="pdf-card-actions">
                    <button v-if="cIdx > 0" type="button" class="btn btn-sm btn-quiet" @click="mergeWithPrev(cIdx)">{{ t('ep.imports.merge_prev') }}</button>
                    <button type="button" class="btn btn-sm btn-quiet" @click="splitCandidate(cIdx)">{{ t('ep.imports.split') }}</button>
                    <button type="button" class="btn btn-sm btn-quiet" @click="removeCandidate(cIdx)">{{ t('ep.imports.remove') }}</button>
                  </span>
                </div>

                <div v-if="cand.is_uncertain" class="notice warn" style="margin-bottom: 12px">
                  <LinearIcon name="alert" :size="14" />
                  <span>{{ t('ep.imports.uncertain', { reason: cand.uncertain_reason }) }}</span>
                </div>

                <div class="pdf-grid">
                  <label class="field">
                    <span class="label">{{ t('ep.imports.type') }}</span>
                    <select v-model="cand.type" class="select">
                      <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
                      <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
                      <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
                      <option value="QA">{{ t('ep.question_types.essay') }}</option>
                    </select>
                  </label>
                  <label class="field">
                    <span class="label">{{ t('ep.imports.answer') }}</span>
                    <input v-model="cand.answer" class="input" :placeholder="t('ep.imports.answer_placeholder')" />
                  </label>
                </div>

                <label class="field" style="margin-top: 12px">
                  <span class="label">{{ t('ep.imports.stem') }}</span>
                  <textarea v-model="cand.stem" class="textarea" rows="3"></textarea>
                </label>

                <div v-if="cand.type === 'SINGLE' || cand.type === 'MULTI'" class="pdf-options">
                  <div class="pdf-options-head">
                    <span class="label">{{ t('ep.imports.options') }}</span>
                    <button type="button" class="btn btn-sm btn-quiet" @click="addCandidateOption(cand)">{{ t('ep.imports.add_option') }}</button>
                  </div>
                  <div v-for="(opt, optIdx) in cand.options" :key="optIdx" class="pdf-option-row">
                    <input v-model="opt.key" class="input opt-key" placeholder="A" />
                    <input v-model="opt.content" class="input" :placeholder="t('ep.imports.option_text')" />
                    <button type="button" class="icon-btn" :aria-label="t('ep.imports.remove')" @click="cand.options.splice(optIdx, 1)">
                      <LinearIcon name="x" :size="14" />
                    </button>
                  </div>
                </div>

                <label class="field" style="margin-top: 12px">
                  <span class="label">{{ t('ep.imports.explanation') }}</span>
                  <input v-model="cand.explanation" class="input" :placeholder="t('ep.imports.explanation_placeholder')" />
                </label>
              </article>
            </div>
            <div v-else class="empty" style="padding: 24px 0">
              <div class="empty-desc">{{ t('ep.imports.no_candidates') }}</div>
            </div>

            <div v-if="pdfPreview.duplicates?.length" class="pdf-duplicates">
              <div class="notice warn">
                <LinearIcon name="alert" :size="15" />
                <span>{{ t('ep.imports.dup_hint', { count: pdfPreview.duplicates.length }) }}</span>
              </div>
              <div v-if="pdfPreview.duplicates.length" class="list dup-list">
                <div v-for="(dup, idx) in pdfPreview.duplicates.slice(0, 8)" :key="idx" class="list-row">
                  <span class="mono small dim">{{ String(idx + 1).padStart(2, '0') }}</span>
                  <span class="list-main">
                    <span class="qrow-stem">{{ dup.stem || dup.question_stem || dup.id }}</span>
                  </span>
                </div>
              </div>
              <div class="field" style="margin-top: 12px; max-width: 320px">
                <span class="label">{{ t('ep.imports.strategy') }}</span>
                <select v-model="pdfDuplicateStrategy" class="select">
                  <option value="" disabled>{{ t('ep.imports.strategy_choose') }}</option>
                  <option value="skip">{{ t('ep.imports.strategy_skip') }}</option>
                  <option value="new">{{ t('ep.imports.strategy_new') }}</option>
                  <option value="merge">{{ t('ep.imports.strategy_merge') }}</option>
                </select>
              </div>
            </div>

            <div class="import-actions">
              <button type="button" class="btn btn-primary" :disabled="loading || !pdfCandidates.length || !canImport || pdfStrategyMissing" @click="confirmPdfImportAction">
                {{ loading ? t('ep.imports.uploading') : t('ep.imports.confirm_pdf') }}
              </button>
              <button type="button" class="btn btn-quiet" @click="resetPdfPreview">{{ t('ep.imports.cancel_preview') }}</button>
            </div>
          </section>

          <!-- Text precheck and correction -->
          <section v-if="textPreview" class="step-block import-text-section">
            <div class="step-head">
              <span class="step-no mono">03</span>
              <div>
                <div class="step-title">{{ importCopy.correctionTitle }}</div>
                <div class="step-sub">{{ importCopy.textHint }}</div>
              </div>
            </div>

            <div v-if="textPreview.duplicates?.length" class="pdf-duplicates import-text-duplicates">
              <div class="notice warn">
                <LinearIcon name="alert" :size="15" />
                <span>{{ t('ep.imports.dup_hint', { count: textPreview.duplicates.length }) }}</span>
              </div>
              <div class="list dup-list">
                <div v-for="(dup, idx) in textPreview.duplicates.slice(0, 8)" :key="idx" class="list-row">
                  <span class="mono small dim">{{ String(idx + 1).padStart(2, '0') }}</span>
                  <span class="list-main">
                    <span class="qrow-stem">{{ dup.stem || dup.question_stem || dup.id }}</span>
                  </span>
                </div>
              </div>
              <div class="field" style="margin-top: 12px; max-width: 320px">
                <span class="label">{{ t('ep.imports.strategy') }}</span>
                <select v-model="duplicateStrategy" class="select">
                  <option value="" disabled>{{ t('ep.imports.strategy_choose') }}</option>
                  <option value="skip">{{ t('ep.imports.strategy_skip') }}</option>
                  <option value="new">{{ t('ep.imports.strategy_new') }}</option>
                  <option value="merge">{{ t('ep.imports.strategy_merge') }}</option>
                </select>
              </div>
            </div>

            <div class="import-actions">
              <button type="button" class="btn btn-primary" :disabled="loading || !canImport || textStrategyMissing" @click="submitText">
                {{ loading ? t('ep.imports.uploading') : t('ep.imports.submit_confirm') }}
              </button>
              <button type="button" class="btn btn-quiet" @click="resetTextPreview">{{ t('ep.imports.cancel_preview') }}</button>
            </div>
          </section>

          <!-- Duplicate strategy -->
          <section v-if="duplicatePreview" class="step-block">
            <div class="step-head">
              <span class="step-no mono">03</span>
              <div>
                <div class="step-title">{{ t('ep.imports.dup_title') }}</div>
                <div class="step-sub">{{ t('ep.imports.dup_hint', { count: duplicatePreview.duplicates?.length || 0 }) }}</div>
              </div>
            </div>

            <div v-if="duplicatePreview.duplicates?.length" class="list dup-list">
              <div v-for="(dup, idx) in duplicatePreview.duplicates.slice(0, 8)" :key="idx" class="list-row">
                <span class="mono small dim">{{ String(idx + 1).padStart(2, '0') }}</span>
                <span class="list-main">
                  <span class="qrow-stem">{{ dup.stem || dup.question_stem || dup.id }}</span>
                </span>
              </div>
            </div>

            <div class="field" style="margin-top: 16px; max-width: 320px">
              <span class="label">{{ t('ep.imports.strategy') }}</span>
              <select v-model="duplicateStrategy" class="select">
                <option value="skip">{{ t('ep.imports.strategy_skip') }}</option>
                <option value="new">{{ t('ep.imports.strategy_new') }}</option>
                <option value="merge">{{ t('ep.imports.strategy_merge') }}</option>
              </select>
            </div>

            <div class="import-actions">
              <button type="submit" class="btn btn-primary" :disabled="loading || !bankId || !file || !canImport">
                {{ loading ? t('ep.imports.uploading') : t('ep.imports.submit_confirm') }}
              </button>
            </div>
          </section>

          <!-- Result -->
          <section v-if="result" class="step-block result-block">
            <div class="step-head">
              <span class="step-no mono">04</span>
              <div>
                <div class="step-title">{{ t('ep.imports.result_title') }}</div>
                <div class="step-sub">{{ t('ep.imports.result_desc', { count: result.imported_count }) }}</div>
              </div>
            </div>
            <div class="kv">
              <div class="kv-row"><span class="kv-key">{{ t('ep.imports.job') }}</span><span class="kv-val mono">{{ result.job_id }}</span></div>
              <div class="kv-row"><span class="kv-key">{{ t('ep.imports.bank') }}</span><span class="kv-val">{{ banks.find(b => b.id === bankId)?.name || t('ep.common.none') }}</span></div>
            </div>
            <div class="import-actions">
              <button type="button" class="btn btn-primary" @click="goBank">{{ t('ep.imports.view_bank') }}</button>
              <button type="button" class="btn" @click="resetImport">{{ t('ep.imports.again') }}</button>
            </div>
          </section>

          <div v-if="error" class="notice bad" style="margin-top: 16px">
            <LinearIcon name="alert" :size="15" /><span>{{ errorText }}</span>
          </div>
        </form>
      </div>

      <aside class="import-rail">
        <div class="rail-title">{{ t('ep.imports.rules_title') }}</div>
        <ul class="rules-list">
          <li>{{ t('ep.imports.rules_formats') }}</li>
          <li>{{ t('ep.imports.rules_dup') }}</li>
          <li>{{ t('ep.imports.rules_pdf') }}</li>
          <li>{{ t('ep.imports.rules_version') }}</li>
        </ul>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import { listBanks } from '../api/banks'
import { previewImport, previewFileImport, uploadImport, previewPdfImport, confirmPdfImport } from '../api/imports'
import { useLocale } from '../composables/useLocale.js'

const { t, locale } = useLocale()

const props = defineProps({ token: { type: String, required: true } })
defineEmits(['back'])
const router = useRouter()
const route = useRoute()
const banks = ref([])
const bankId = ref('')
const file = ref(null)
const isDragging = ref(false)
const fileInputRef = ref(null)
const loading = ref(false)
const previewing = ref(false)
const error = ref(null)
const errorText = computed(() => {
  if (error.value instanceof Error) return error.value.message
  return typeof error.value === 'string' ? error.value : ''
})
const result = ref(null)
const duplicatePreview = ref(null)
const duplicateStrategy = ref('skip')
const spreadsheetPreview = ref(null)
const textPreview = ref(null)
const pdfPreview = ref(null)
const pdfCandidates = ref([])
const pdfDuplicateStrategy = ref('')
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

const optionLetters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

const importCopy = computed(() => locale.value === 'en-US'
  ? {
      stepsLabel: 'Import progress',
      precheckStep: 'Precheck',
      correctStep: 'Correct',
      precheckTitle: 'File precheck',
      parsed: 'Rows parsed',
      duplicates: 'Possible duplicates',
      needsAttention: 'Need correction',
      prechecking: 'Checking file…',
      duplicatesFound: 'Duplicates found',
      needsCorrection: 'Needs confirmation',
      ready: 'Precheck passed',
      correctionTitle: 'Review and correct',
      textHint: 'The text file is parsed. Confirm duplicate handling before writing.',
      done: 'Done',
      active: 'In progress',
      pending: 'Pending',
    }
  : {
      stepsLabel: '导入进度',
      precheckStep: '预检',
      correctStep: '纠错',
      precheckTitle: '文件预检',
      parsed: '解析出题目',
      duplicates: '疑似重复',
      needsAttention: '待纠错',
      prechecking: '正在预检…',
      duplicatesFound: '发现重复题目',
      needsCorrection: '需要人工确认',
      ready: '预检通过',
      correctionTitle: '人工纠错',
      textHint: '文本已解析完成；确认重复处理后再写入题库。',
      done: '已完成',
      active: '进行中',
      pending: '待处理',
    })

const steps = computed(() => [
  { key: 'source', label: t('ep.imports.step_source') },
  { key: 'precheck', label: importCopy.value.precheckStep },
  { key: 'correct', label: importCopy.value.correctStep },
  { key: 'result', label: t('ep.imports.step_result') },
])

const stepNo = computed(() => {
  if (result.value) return 4
  if (duplicatePreview.value || spreadsheetPreview.value || pdfPreview.value || textPreview.value) return 3
  if (previewing.value) return 2
  return 1
})

const stepPercent = computed(() => ((stepNo.value - 1) / 3) * 100)

function stepState(index) {
  if (stepNo.value > index) return 'done'
  if (stepNo.value === index) return 'active'
  return 'pending'
}

function stepStateLabel(index) {
  const state = stepState(index)
  return importCopy.value[state]
}

const precheckPanel = computed(() => {
  const source = spreadsheetPreview.value || pdfPreview.value || textPreview.value || duplicatePreview.value
  if (!source) return null
  const duplicates = Array.isArray(source.duplicates) ? source.duplicates.length : 0
  let count = Number(source.question_count || 0)
  let attention = Array.isArray(source.missing) ? source.missing.length : 0
  let accepted = Boolean(source.accepted)
  let status = source.reason || ''

  if (source === pdfPreview.value) {
    count = Number(source.question_count || pdfCandidates.value.length || 0)
    attention = pdfCandidates.value.filter(candidate => candidate.is_uncertain).length
    accepted = duplicates === 0 && attention === 0
    status = duplicates ? importCopy.value.duplicatesFound : attention ? importCopy.value.needsCorrection : importCopy.value.ready
  } else {
    accepted = duplicates === 0 && attention === 0 && source.accepted !== false
    status = duplicates
      ? importCopy.value.duplicatesFound
      : attention
        ? importCopy.value.needsCorrection
        : accepted
          ? importCopy.value.ready
          : (status || importCopy.value.needsCorrection)
  }

  return { count, duplicates, attention, accepted, status }
})

const isSpreadsheet = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.xlsx') || name.endsWith('.csv')
})

const isPdf = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.pdf')
})

const isTextFile = computed(() => {
  const name = file.value?.name?.toLowerCase() || ''
  return name.endsWith('.json') || name.endsWith('.md') || name.endsWith('.markdown') || name.endsWith('.txt')
})

const selectedBank = computed(() => banks.value.find(b => b.id === bankId.value) || null)

// Import writes questions, so member-level access must be rejected before the
// user spends time mapping columns or correcting a PDF draft.
const canImport = computed(() => {
  const role = String(selectedBank.value?.role || '').toUpperCase()
  return role === 'ADMIN' || role === 'EDITOR'
})

const pdfStrategyMissing = computed(() => Boolean(pdfPreview.value?.duplicates?.length) && !pdfDuplicateStrategy.value)
const textStrategyMissing = computed(() => Boolean(textPreview.value?.duplicates?.length) && !duplicateStrategy.value)

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
  textPreview.value = null
  pdfPreview.value = null
  pdfCandidates.value = []
  pdfDuplicateStrategy.value = ''
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
    error.value = t('ep.imports.supported')
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
    const preset = String(route.query.bankId || '')
    if (preset && banks.value.some(b => b.id === preset)) bankId.value = preset
  } catch (err) {
    error.value = err instanceof Error ? err : new Error(t('ep.imports.error_fallback'))
  }
})

async function inspectSpreadsheet() {
  if (!file.value || !bankId.value) return
  previewing.value = true
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
    previewing.value = false
    loading.value = false
  }
}

async function inspectPdf() {
  if (!file.value || !bankId.value) return
  previewing.value = true
  loading.value = true
  error.value = ''
  try {
    const prev = await previewPdfImport(props.token, bankId.value, file.value)
    pdfPreview.value = prev
    pdfCandidates.value = JSON.parse(JSON.stringify(prev.candidates || []))
    pdfDuplicateStrategy.value = prev.duplicates?.length ? '' : 'skip'
  } catch (err) {
    error.value = err
  } finally {
    previewing.value = false
    loading.value = false
  }
}

async function inspectText() {
  if (!file.value || !bankId.value || !isTextFile.value) return
  previewing.value = true
  loading.value = true
  error.value = ''
  try {
    const text = await file.value.text()
    const format = file.value.name.toLowerCase().endsWith('.json') ? 'json' : 'markdown'
    textPreview.value = await previewImport(props.token, bankId.value, { format, content: text })
    duplicateStrategy.value = textPreview.value?.duplicates?.length ? '' : 'skip'
  } catch (err) {
    error.value = err
  } finally {
    previewing.value = false
    loading.value = false
  }
}

function resetTextPreview() {
  textPreview.value = null
  duplicateStrategy.value = 'skip'
}

async function submitText() {
  if (!textPreview.value || !canImport.value || textStrategyMissing.value) return
  loading.value = true
  error.value = ''
  try {
    const strategy = textPreview.value.duplicates?.length ? duplicateStrategy.value : 'skip'
    result.value = await uploadImport(props.token, bankId.value, file.value, strategy, null)
    textPreview.value = null
    duplicatePreview.value = null
  } catch (err) {
    if (err.status === 409 && err.detail && typeof err.detail === 'object') {
      duplicatePreview.value = err.detail
      textPreview.value = null
    } else {
      error.value = err
    }
  } finally {
    loading.value = false
  }
}

function resetPdfPreview() {
  pdfPreview.value = null
  pdfCandidates.value = []
  pdfDuplicateStrategy.value = ''
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
  const stem = item.stem || ''

  let splitIndex = -1
  const newlineMatch = stem.search(/\n(?=[0-9]+[.\s、\)])/)
  if (newlineMatch > 0) {
    splitIndex = newlineMatch + 1
  } else {
    const anyNewline = stem.indexOf('\n')
    if (anyNewline > 0) {
      splitIndex = anyNewline + 1
    } else {
      const mid = Math.floor(stem.length / 2)
      const terminators = ['。', '？', '！', '?', '!', '；', ';', '. ']
      let bestDist = Infinity
      for (const t of terminators) {
        let pos = stem.indexOf(t)
        while (pos !== -1) {
          const cutPos = pos + t.length
          const dist = Math.abs(cutPos - mid)
          if (dist < bestDist && cutPos < stem.length) {
            bestDist = dist
            splitIndex = cutPos
          }
          pos = stem.indexOf(t, pos + 1)
        }
      }
    }
  }

  if (splitIndex <= 0 || splitIndex >= stem.length) {
    splitIndex = Math.floor(stem.length / 2)
  }

  const firstStem = stem.slice(0, splitIndex).trim()
  const secondStem = stem.slice(splitIndex).trim() || t('ep.imports.split_continuation')

  item.stem = firstStem
  pdfCandidates.value.splice(idx + 1, 0, {
    candidate_id: pdfCandidates.value.length + 1,
    type: item.type,
    stem: secondStem,
    options: [],
    answer: '',
    explanation: '',
    difficulty: item.difficulty || 3,
    tags: item.tags ? [...item.tags] : [],
    is_uncertain: true,
    uncertain_reason: t('ep.imports.split_uncertain'),
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
  if (!pdfPreview.value || !pdfCandidates.value.length || !canImport.value) return
  if (pdfStrategyMissing.value) return
  loading.value = true
  error.value = ''
  try {
    result.value = await confirmPdfImport(props.token, bankId.value, {
      draft_id: pdfPreview.value.draft_id,
      questions: pdfCandidates.value,
      duplicate_strategy: pdfDuplicateStrategy.value || 'skip',
    })
    resetPdfPreview()
  } catch (err) {
    if (err.status === 409 && err.detail && typeof err.detail === 'object') {
      // Duplicates appeared after the preview (another editor changed the bank).
      // Keep the corrected PDF draft and let the user choose a strategy here.
      if (pdfPreview.value) {
        pdfPreview.value = { ...pdfPreview.value, duplicates: err.detail.duplicates || [] }
      }
      pdfDuplicateStrategy.value = ''
    } else {
      error.value = err
    }
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (isSpreadsheet.value && !spreadsheetPreview.value && !duplicatePreview.value) {
    await inspectSpreadsheet()
    return
  }
  if (isTextFile.value && !textPreview.value && !duplicatePreview.value) {
    await inspectText()
    return
  }
  if (isTextFile.value && textPreview.value) {
    await submitText()
    return
  }
  if (isPdf.value && pdfPreview.value) return

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

function goBank() {
  if (bankId.value) router.push(`/banks/${bankId.value}`)
}

function resetImport() {
  result.value = null
  duplicatePreview.value = null
  spreadsheetPreview.value = null
  textPreview.value = null
  pdfPreview.value = null
  pdfCandidates.value = []
  pdfDuplicateStrategy.value = ''
  optionSlots.value = Array(8).fill('')
  file.value = null
  error.value = ''
}
</script>

<style scoped>
.import-page { padding-top: 26px; }
.link-btn { border: 0; background: none; padding: 0; color: var(--ink-3); font: inherit; cursor: pointer; }
.link-btn:hover { color: var(--brand); }

.import-steps { display: flex; gap: 18px; margin: 22px 0 0; padding: 12px 0; list-style: none; border-top: 1px solid var(--line); flex-wrap: wrap; }
.import-step { display: flex; align-items: baseline; gap: 7px; flex: 1 1 150px; min-width: 0; color: var(--ink-4); }
.import-step.is-active { color: var(--ink); }
.import-step.is-done { color: var(--ink-3); }
.step-idx { font-size: 12px; letter-spacing: .04em; }
.step-label { font-size: 12px; }
.step-state { margin-left: auto; font-size: 12px; color: var(--ink-4); white-space: nowrap; }
.import-step[data-step-state="active"] .step-state { color: var(--brand); }
.import-step[data-step-state="done"] .step-state { color: var(--ok); }
.import-step.is-active .step-label { font-weight: 600; }
.import-progress { height: 2px; margin: 0 0 18px; background: var(--line); overflow: hidden; }
.import-progress i { display: block; height: 100%; background: var(--brand); transition: width .2s var(--ease); }

.import-precheck-panel { margin-bottom: 18px; padding: 14px 16px; border: 1px solid var(--line-strong); border-radius: 4px; background: var(--surface-2); }
.import-precheck-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.import-precheck-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }
.import-precheck-cell { min-width: 0; }
.import-precheck-cell b { display: block; font-family: var(--font-mono); font-size: 24px; font-weight: 500; line-height: 1.15; color: var(--ink); }
.import-precheck-cell b.is-warn { color: var(--warn); }
.import-precheck-cell span { display: block; margin-top: 3px; font-size: 12px; color: var(--ink-3); }
.import-precheck-loading { margin: 8px 0 0; font-size: 12px; color: var(--ink-3); }

.import-layout { display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 44px; margin-top: 26px; align-items: start; }
.import-main { min-width: 0; }
.import-rail { border-top: 1px solid var(--line); padding-top: 13px; }
.rail-title { font-size: 12px; font-weight: 600; letter-spacing: .06em; color: var(--ink-2); }
.rules-list { margin: 10px 0 0; padding: 0 0 0 15px; }
.rules-list li { font-size: 12px; line-height: 1.8; color: var(--ink-3); margin-bottom: 6px; }

.step-block { padding: 22px 0 26px; border-top: 1px solid var(--line); }
.step-block:first-of-type { border-top: 0; padding-top: 0; }
.step-head { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 20px; }
.step-head .tag { margin-left: auto; }
.step-no { font-size: 12px; letter-spacing: .04em; color: var(--ink-4); padding-top: 3px; }
.step-title { font-family: var(--font-serif); font-size: 19px; font-weight: 600; line-height: 1.3; }
.step-sub { margin-top: 4px; font-size: 12px; line-height: 1.7; color: var(--ink-3); max-width: 62ch; }

.file-drop { display: flex; align-items: center; gap: 12px; min-height: 76px; padding: 16px 18px; border: 1px dashed var(--line-strong); background: var(--surface); cursor: default; transition: border-color .15s ease, background .15s ease; }
.file-drop:hover, .file-drop.is-dragging { border-color: var(--brand-line); background: var(--surface-2); }
.file-drop.is-dragging { flex-direction: column; justify-content: center; color: var(--brand); }
.file-icon { display: grid; place-items: center; width: 34px; height: 34px; border: 1px solid var(--line); color: var(--ink-3); flex: none; }
.file-main { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1; }
.file-name { font-size: 13px; color: var(--ink); overflow-wrap: anywhere; }
.file-meta { font-size: 12px; color: var(--ink-3); }
.file-input-hidden { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.file-formats { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.file-formats .tag { font-size: 12px; }

.import-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--line); }

.mapping-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px 18px; }
.sample-block { margin-top: 22px; }
.sample-scroll { overflow-x: auto; border-top: 1px solid var(--line); }
.sample-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sample-table th { padding: 7px 10px; text-align: left; font-size: 12px; letter-spacing: .05em; font-weight: 600; color: var(--ink-3); border-bottom: 1px solid var(--line); white-space: nowrap; }
.sample-table td { padding: 7px 10px; border-bottom: 1px solid var(--line); color: var(--ink-2); vertical-align: top; max-width: 220px; }

.pdf-list { display: flex; flex-direction: column; gap: 0; }
.pdf-card { border-top: 1px solid var(--line); padding: 18px 0; }
.pdf-card:first-child { border-top: 0; padding-top: 4px; }
.pdf-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
.pdf-card-actions { display: flex; gap: 2px; flex-wrap: wrap; }
.pdf-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }
.pdf-options { margin-top: 14px; }
.pdf-options-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.pdf-option-row { display: flex; gap: 7px; align-items: center; margin-top: 6px; }
.opt-key { width: 46px; flex: none; text-align: center; }

.dup-list { margin-top: 14px; }
.pdf-duplicates { margin-top: 18px; }
.qrow-stem { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-family: var(--font-serif); font-size: 13.5px; line-height: 1.65; }
.result-block .kv { margin-top: 2px; }

@media (max-width: 960px) {
  .import-layout { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .import-rail { display: none; }
  .mapping-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .import-page { overflow-x: hidden; }
  .import-steps { gap: 14px; }
  .import-step { flex: 1 1 40%; min-width: 0; }
  .step-state { display: none; }
  .import-precheck-grid { gap: 8px; }
  .import-precheck-cell b { font-size: 20px; }
  .mapping-grid, .pdf-grid { grid-template-columns: minmax(0, 1fr); }
  .file-drop { flex-wrap: wrap; }
  .file-drop .btn { margin-left: 0; flex: 1 1 auto; justify-content: center; }
  .file-main { flex-basis: calc(100% - 46px); }
  .step-block { padding: 18px 0 22px; }
  .step-title { font-size: 17px; }
  .step-head { flex-wrap: wrap; }
  .pdf-card-head { flex-wrap: wrap; align-items: flex-start; }
  .pdf-card-actions { width: 100%; justify-content: flex-end; }
  .pdf-option-row { flex-wrap: wrap; }
  .import-actions .btn { flex: 1 1 auto; justify-content: center; }
}
</style>
