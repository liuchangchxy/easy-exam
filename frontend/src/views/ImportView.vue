<template>
  <main class="import-page">
    <header class="page-header"><button @click="$emit('back')">返回</button><h1>导入题目</h1></header>
    <form class="bank-card import-form" @submit.prevent="submit">
      <label>目标题库
        <select v-model="bankId" required>
          <option value="" disabled>选择题库</option>
          <option v-for="bank in banks" :key="bank.id" :value="bank.id">{{ bank.name }}</option>
        </select>
      </label>
      <label>题目文件
        <input type="file" accept=".xlsx,.csv,.json,.txt,.md,.markdown,.pdf" required @change="selectFile" />
      </label>
      <p class="muted">支持 XLSX、CSV、JSON、文本/Markdown 和可提取文本的 PDF。纯图片 PDF 会被拒绝。</p>

      <div v-if="isSpreadsheet && !spreadsheetPreview" class="preview-actions">
        <button type="button" class="preview-btn" :disabled="loading || !bankId || !file" @click="inspectSpreadsheet">
          {{ loading ? '正在分析…' : '预览表格列映射' }}
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

      <button type="submit" :disabled="loading || !bankId || !file">
        {{ loading ? '正在处理…' : duplicatePreview ? '确认重复处理并导入' : spreadsheetPreview ? '确认列映射并导入' : '检查并导入' }}
      </button>
    </form>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { listBanks } from '../api/banks'
import { previewFileImport, uploadImport } from '../api/imports'

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
.preview-actions {
  margin: 10px 0;
}
.preview-btn {
  background-color: #4a5568;
}
.column-mapping-panel {
  background: #f7fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 16px;
  margin: 16px 0;
}
.mapping-hint {
  font-size: 0.88rem;
  color: #4a5568;
  margin-bottom: 12px;
}
.mapping-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.missing-warning {
  margin-bottom: 12px;
}
.sample-table-container {
  overflow-x: auto;
  max-height: 200px;
  margin-top: 12px;
}
.sample-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.sample-table th, .sample-table td {
  border: 1px solid #cbd5e0;
  padding: 4px 8px;
  text-align: left;
  white-space: nowrap;
}
.sample-table th {
  background: #edf2f7;
}
</style>
