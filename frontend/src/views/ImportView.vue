<template>
  <main class="import-page">
    <header class="page-header import-header">
      <div class="header-left">
        <button type="button" class="btn-back" @click="$emit('back')">← {{ t('common.back') }}</button>
        <h1>{{ t('imports.title') }}</h1>
      </div>
    </header>
    <form class="bank-card import-form" @submit.prevent="submit">
      <label>目标题库
        <select v-model="bankId" required>
          <option value="" disabled>选择题库</option>
          <option v-for="bank in banks" :key="bank.id" :value="bank.id">{{ bank.name }}</option>
        </select>
      </label>
      <div class="file-upload-card">
        <div class="file-card-inner">
          <span class="file-upload-icon">
            <LinearIcon name="inbox" size="24" />
          </span>
          <div class="file-card-text">
            <strong>选择或上传题目文件</strong>
            <small>支持 XLSX、CSV、JSON、Markdown/TXT 和可提取文本的 PDF</small>
          </div>
        </div>
        <input type="file" accept=".xlsx,.csv,.json,.txt,.md,.markdown,.pdf" required @change="selectFile" class="file-styled-input" />
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
          {{ loading ? '正在分析…' : '预览表格列映射' }}
        </button>
      </div>

      <div v-if="isPdf && !pdfPreview" class="preview-actions">
        <button type="button" class="preview-btn" :disabled="loading || !bankId || !file" @click="inspectPdf">
          {{ loading ? '正在解析 PDF…' : '预览与校对 PDF（含人工校正）' }}
        </button>
      </div>

      <!-- Exameow-style Column Mapping Preview Panel -->
      <section v-if="spreadsheetPreview" class="column-mapping-panel">
        <h3>表格列映射预览</h3>
        <p class="mapping-hint">已自动推断表头对应关系，您也可以手工调整列绑定：</p>
        <div class="mapping-grid">
          <label>题干列 (必填)
            <select id="select-stem" v-model.number="currentMapping.stem">
              <option :value="null">-- 未选择 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>答案列 (必填)
            <select id="select-answer" v-model.number="currentMapping.answer">
              <option :value="null">-- 未选择 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>题型列
            <select id="select-type" v-model.number="currentMapping.type">
              <option :value="null">-- 自动推断 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>解析列
            <select id="select-explanation" v-model.number="currentMapping.explanation">
              <option :value="null">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>难度列
            <select id="select-difficulty" v-model.number="currentMapping.difficulty">
              <option :value="null">-- 默认适中 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>标签/章节列
            <select id="select-tags" v-model.number="currentMapping.tags">
              <option :value="null">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>组合选项列
            <select id="select-combined-options" v-model.number="currentMapping.combined_options">
              <option :value="null">-- 无组合选项 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label v-if="currentMapping.combined_options !== null">选项分隔符
            <select id="select-options-delimiter" v-model="currentMapping.options_delimiter">
              <option value="">自动检测</option>
              <option value="prefix">前缀字母 (A. B. C.)</option>
              <option value=";">英文分号 (;)</option>
              <option value="；">中文分号 (；)</option>
              <option value="\n">换行符</option>
              <option value="|">竖线 (|)</option>
              <option value="、">顿号 (、)</option>
            </select>
          </label>
          <label>选项 A 列
            <select id="select-opt-a" :value="getOptionCol(0)" @change="setOptionCol(0, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>选项 B 列
            <select id="select-opt-b" :value="getOptionCol(1)" @change="setOptionCol(1, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>选项 C 列
            <select id="select-opt-c" :value="getOptionCol(2)" @change="setOptionCol(2, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>选项 D 列
            <select id="select-opt-d" :value="getOptionCol(3)" @change="setOptionCol(3, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>选项 E 列
            <select id="select-opt-e" :value="getOptionCol(4)" @change="setOptionCol(4, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>选项 F 列
            <select id="select-opt-f" :value="getOptionCol(5)" @change="setOptionCol(5, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>选项 G 列
            <select id="select-opt-g" :value="getOptionCol(6)" @change="setOptionCol(6, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
          <label>选项 H 列
            <select id="select-opt-h" :value="getOptionCol(7)" @change="setOptionCol(7, $event.target.value)">
              <option value="">-- 无 --</option>
              <option v-for="(h, idx) in spreadsheetPreview.headers" :key="idx" :value="idx">{{ idx }}: {{ h }}</option>
            </select>
          </label>
        </div>

        <div v-if="spreadsheetPreview.missing?.length" class="error missing-warning">
          警告：缺少必要字段映射（{{ spreadsheetPreview.missing.join(', ') }}），请修正上方绑定后导入。
        </div>

        <div v-if="spreadsheetPreview.preview_rows?.length" class="sample-table-container">
          <h4>前 {{ spreadsheetPreview.preview_rows.length }} 行内容采样：</h4>
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
          <h3 style="color: var(--text-main);">PDF 题目校对预览</h3>
          <span :style="{ fontSize: '0.8rem', padding: '0.25rem 0.6rem', borderRadius: '4px', fontWeight: 'bold', background: pdfPreview.confidence === 'HIGH' ? 'var(--success-light)' : 'var(--warning-light)', color: pdfPreview.confidence === 'HIGH' ? 'var(--success)' : 'var(--warning)' }">
            {{ pdfPreview.confidence === 'HIGH' ? '解析置信度：高' : '解析置信度：较低（格式存在歧义，请人工核校）' }}
          </span>
        </div>
        <p class="mapping-hint" style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1rem;">
          共提取出 {{ pdfCandidates.length }} 道候选题目。您可在入库前手动编辑、拆分、合并或剔除题目：
        </p>

        <div style="display: flex; flex-direction: column; gap: 1rem;">
          <div v-for="(cand, cIdx) in pdfCandidates" :key="cIdx" style="border: 1px solid var(--border); border-radius: 8px; padding: 1rem; background: var(--bg-subtle);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <span style="font-weight: 600; font-size: 0.9rem; color: var(--text-main);">第 {{ cIdx + 1 }} 题</span>
              <div style="display: flex; gap: 0.5rem;">
                <button v-if="cIdx > 0" type="button" class="action-link-btn" style="font-size: 0.75rem;" @click="mergeWithPrev(cIdx)">合并至上一题</button>
                <button type="button" class="action-link-btn" style="font-size: 0.75rem;" @click="splitCandidate(cIdx)">在此拆分</button>
                <button type="button" class="action-link-btn" style="font-size: 0.75rem; color: var(--danger);" @click="removeCandidate(cIdx)">删除</button>
              </div>
            </div>

            <div v-if="cand.is_uncertain" style="padding: 0.4rem 0.6rem; background: var(--warning-light); border: 1px solid var(--warning-border); border-radius: 4px; font-size: 0.8rem; color: var(--warning); margin-bottom: 0.5rem;">
              ⚠️ 校对提示：{{ cand.uncertain_reason }}
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.5rem;">
              <label style="font-size: 0.8rem;">题型：
                <select v-model="cand.type" style="width: 100%; margin-top: 0.2rem;">
                  <option value="SINGLE">单选题</option>
                  <option value="MULTI">多选题</option>
                  <option value="JUDGE">判断题</option>
                  <option value="QA">简答/问答题</option>
                </select>
              </label>
              <label style="font-size: 0.8rem;">正确答案：
                <input v-model="cand.answer" placeholder="如 A / AB / 正确 / 错误" style="width: 100%; margin-top: 0.2rem;" />
              </label>
            </div>

            <label style="font-size: 0.8rem; display: block; margin-bottom: 0.5rem;">题干：
              <textarea v-model="cand.stem" rows="2" style="width: 100%; margin-top: 0.2rem;"></textarea>
            </label>

            <div v-if="cand.type === 'SINGLE' || cand.type === 'MULTI'" style="margin-bottom: 0.5rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.8rem; font-weight: 500;">选项列表：</span>
                <button type="button" class="action-link-btn" style="font-size: 0.75rem;" @click="addCandidateOption(cand)">+ 增加选项</button>
              </div>
              <div v-for="(opt, optIdx) in cand.options" :key="optIdx" style="display: flex; gap: 0.4rem; margin-top: 0.25rem;">
                <input v-model="opt.key" style="width: 3rem;" placeholder="A" />
                <input v-model="opt.content" style="flex: 1;" placeholder="选项文本" />
                <button type="button" style="color: var(--danger); border: none; background: none; cursor: pointer;" @click="cand.options.splice(optIdx, 1)">×</button>
              </div>
            </div>

            <label style="font-size: 0.8rem; display: block;">解析：
              <input v-model="cand.explanation" placeholder="题目解析（可选）" style="width: 100%; margin-top: 0.2rem;" />
            </label>
          </div>
        </div>

        <div class="preview-actions" style="margin-top: 1rem; display: flex; gap: 0.75rem;">
          <button type="button" class="primary" :disabled="loading || !pdfCandidates.length" @click="confirmPdfImportAction">
            {{ loading ? '入库中…' : '确认校对并导入题库' }}
          </button>
          <button type="button" @click="pdfPreview = null">取消校对</button>
        </div>
      </section>

      <p v-if="duplicatePreview" class="warning">检测到 {{ duplicatePreview.duplicates?.length || 0 }} 道重复题。请选择如何处理后再次导入。</p>
      <label v-if="duplicatePreview">重复题处理
        <select v-model="duplicateStrategy">
          <option value="skip">跳过重复题</option>
          <option value="new">作为新题导入</option>
          <option value="merge">合并到原题新版本</option>
        </select>
      </label>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="result" class="success">导入完成：新增/更新 {{ result.imported_count }} 题，任务 {{ result.job_id }}</p>

      <button type="submit" class="primary btn-submit-import" :disabled="loading || !bankId || !file">
        {{ loading ? '正在处理…' : duplicatePreview ? '确认重复处理并导入' : spreadsheetPreview ? '确认列映射并导入' : '检查并导入' }}
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
const loading = ref(false)
const error = ref('')
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

function selectFile(event) {
  file.value = event.target.files?.[0] || null
  result.value = null
  duplicatePreview.value = null
  spreadsheetPreview.value = null
  pdfPreview.value = null
  pdfCandidates.value = []
  optionSlots.value = Array(8).fill('')
  error.value = ''
}

onMounted(async () => {
  try {
    banks.value = await listBanks(props.token)
  } catch (err) {
    error.value = err.detail || err.message
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
    error.value = err.message
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
    error.value = err.message
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
  const newStem = item.stem.slice(half).trim() || '拆分题目'
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
    uncertain_reason: '手动拆分题目，请核准题干与答案',
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
    error.value = err.message
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
      error.value = err.message
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
