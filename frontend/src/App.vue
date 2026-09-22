<template>
  <div class="app-root">
    <!-- Active Practice Session View -->
    <PracticeView
      v-if="activeSession"
      :session-id="activeSession.id"
      :bank-id="activeSession.bank_id"
      :initial-mode="activeSession.mode"
      :initial-time-limit="activeSession.time_limit || 0"
      @back="exitSession"
      @session-completed="handleSessionCompleted"
    />

    <!-- Main Home / Bank Selection Dashboard -->
    <div v-else class="home-container">
      <!-- App Header -->
      <header class="app-header">
        <div class="header-content">
          <div class="brand">
            <span class="brand-logo">🎯</span>
            <div>
              <h1 class="brand-title">FnExam 飞牛刷题</h1>
              <p class="brand-subtitle">极简高可用触屏刷题 · 飞牛 NAS 原生</p>
            </div>
          </div>
          <button class="btn-import-header" @click="showImportModal = true">
            ➕ 导入题库
          </button>
        </div>
      </header>

      <!-- Local Draft Resume Banner -->
      <div v-if="resumeDraft" class="draft-resume-banner animate-slide-up">
        <div class="draft-resume-info">
          <span class="draft-icon">⚡</span>
          <div>
            <strong>发现未完成的刷题草稿</strong>
            <p>已作答 {{ Object.keys(resumeDraft.answers || {}).length }} 题，第 {{ (resumeDraft.currentIndex || 0) + 1 }} 题</p>
          </div>
        </div>
        <div class="draft-actions">
          <button class="btn-resume" @click="handleResumeDraft">继续作答</button>
          <button class="btn-discard" @click="handleDiscardDraft">放弃</button>
        </div>
      </div>

      <!-- Main Content -->
      <main class="home-main">
        <div class="section-title-bar">
          <h2 class="section-title">我的题库 ({{ banks.length }})</h2>
          <button class="btn-refresh" @click="fetchBanks" :disabled="loading">
            刷新
          </button>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>正在读取题库数据...</p>
        </div>

        <div v-else-if="banks.length === 0" class="empty-bank-card">
          <div class="empty-icon">📚</div>
          <h3>暂无题库</h3>
          <p>点击下方按钮一键导入首批题目，开启现代化刷题体验！</p>
          <button class="btn-primary" @click="showImportModal = true">
            立即导入题目
          </button>
        </div>

        <div v-else class="bank-grid">
          <div v-for="bank in banks" :key="bank.id" class="bank-card">
            <div class="bank-card-header">
              <span class="bank-category">{{ bank.category || '综合题库' }}</span>
              <span class="bank-count">{{ bank.question_count || 0 }} 题</span>
            </div>
            <h3 class="bank-name">{{ bank.name }}</h3>
            <p class="bank-desc">{{ bank.description || '暂无描述' }}</p>

            <div class="bank-actions">
              <button
                class="btn-mode btn-practice"
                :disabled="!bank.question_count"
                @click="startSession(bank.id, 'PRACTICE', 0)"
              >
                🚀 即判刷题
              </button>
              <button
                class="btn-mode btn-exam"
                :disabled="!bank.question_count"
                @click="startSession(bank.id, 'EXAM', 45)"
              >
                ⏱️ 模拟考试
              </button>
              <button
                class="btn-mode btn-elimination"
                :disabled="!bank.question_count"
                @click="startSession(bank.id, 'ELIMINATION', 0)"
              >
                🎯 错题攻坚
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- Import Questions Modal -->
      <div v-if="showImportModal" class="modal-overlay" @click.self="showImportModal = false">
        <div class="import-modal animate-slide-up">
          <div class="modal-header">
            <h3>导入题库题目</h3>
            <button class="btn-close" @click="showImportModal = false">✕</button>
          </div>

          <div class="modal-body">
            <div class="form-group">
              <label>选择或新建题库:</label>
              <select v-model="importBankId" class="form-select">
                <option value="__NEW__">+ 新建题库</option>
                <option v-for="b in banks" :key="b.id" :value="b.id">
                  {{ b.name }} ({{ b.question_count || 0 }}题)
                </option>
              </select>
            </div>

            <div v-if="importBankId === '__NEW__'" class="form-group">
              <label>新题库名称:</label>
              <input v-model="newBankName" type="text" placeholder="例如：软件工程历年真题" class="form-input" />
            </div>

            <div class="form-group">
              <label>导入格式:</label>
              <div class="format-radios">
                <label><input v-model="importFormat" type="radio" value="text" /> 纯文本 / Markdown</label>
                <label><input v-model="importFormat" type="radio" value="csv" /> CSV 表格</label>
                <label><input v-model="importFormat" type="radio" value="json" /> JSON 结构化</label>
              </div>
            </div>

            <div class="form-group">
              <label>粘贴题目内容:</label>
              <textarea
                v-model="importContent"
                rows="8"
                class="form-textarea"
                placeholder="例如：&#10;1. 计算机网络的拓扑结构不包括下列哪项？&#10;A. 星型拓扑&#10;B. 总线拓扑&#10;C. 宇宙拓扑&#10;D. 环型拓扑&#10;【答案】C&#10;【解析】计算机网络拓扑包含星型、总线、环型、树型、网状等，不包含宇宙拓扑。"
              ></textarea>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-cancel" @click="showImportModal = false">取消</button>
            <button class="btn-primary" :disabled="importing || !importContent.trim()" @click="handleImportSubmit">
              {{ importing ? '正在解析导入...' : '开始导入' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PracticeView from './views/PracticeView.vue'

const banks = ref([])
const loading = ref(false)
const activeSession = ref(null)
const resumeDraft = ref(null)

// Import modal state
const showImportModal = ref(false)
const importBankId = ref('__NEW__')
const newBankName = ref('')
const importFormat = ref('text')
const importContent = ref('')
const importing = ref(false)

onMounted(async () => {
  await fetchBanks()
  checkResumeDraft()
})

async function fetchBanks() {
  loading.value = true
  try {
    const res = await fetch('/api/banks')
    if (res.ok) {
      banks.value = await res.json()
      if (banks.value.length && importBankId.value === '__NEW__') {
        importBankId.value = banks.value[0].id
      }
    }
  } catch (err) {
    console.warn('Fetch banks failed:', err)
  } finally {
    loading.value = false
  }
}

function checkResumeDraft() {
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith('fnexam_draft_')) {
        const sid = key.replace('fnexam_draft_', '')
        const val = JSON.parse(localStorage.getItem(key) || '{}')
        if (val && val.answers && Object.keys(val.answers).length > 0) {
          resumeDraft.value = {
            sessionId: sid,
            ...val
          }
          break
        }
      }
    }
  } catch (e) {
    console.warn('Check draft error:', e)
  }
}

async function handleResumeDraft() {
  if (!resumeDraft.value) return
  const sid = resumeDraft.value.sessionId
  try {
    const res = await fetch(`/api/sessions/${sid}`)
    if (res.ok) {
      const session = await res.json()
      activeSession.value = session
      resumeDraft.value = null
    }
  } catch (e) {
    console.warn('Failed resuming session:', e)
  }
}

function handleDiscardDraft() {
  if (resumeDraft.value) {
    localStorage.removeItem(`fnexam_draft_${resumeDraft.value.sessionId}`)
    resumeDraft.value = null
  }
}

async function startSession(bankId, mode, timeLimit) {
  try {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bank_id: bankId,
        mode: mode,
        total_questions: 0,
        time_limit: timeLimit
      })
    })
    if (res.ok) {
      activeSession.value = await res.json()
    }
  } catch (err) {
    console.warn('Start session failed:', err)
  }
}

function exitSession() {
  activeSession.value = null
  fetchBanks()
  checkResumeDraft()
}

function handleSessionCompleted(report) {
  // Session completed callback
}

async function handleImportSubmit() {
  importing.value = true
  try {
    let targetBankId = importBankId.value

    if (targetBankId === '__NEW__') {
      const name = newBankName.value.trim() || '新建题库 ' + new Date().toLocaleDateString()
      const bRes = await fetch('/api/banks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description: '自建题库', category: '通用' })
      })
      if (!bRes.ok) throw new Error('Create bank failed')
      const newBank = await bRes.json()
      targetBankId = newBank.id
    }

    const impRes = await fetch(`/api/banks/${targetBankId}/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        format: importFormat.value,
        content: importContent.value
      })
    })

    if (impRes.ok) {
      const data = await impRes.json()
      alert(`导入成功！共计录入 ${data.imported_count} 道题目。`)
      showImportModal.value = false
      importContent.value = ''
      await fetchBanks()
    } else {
      const err = await impRes.json()
      alert('导入失败: ' + (err.detail || '格式错误'))
    }
  } catch (err) {
    alert('导入出错: ' + err.message)
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.app-root {
  min-height: 100vh;
  background-color: var(--bg-page);
  display: flex;
  flex-direction: column;
}

.home-container {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  padding: 0 16px 40px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Header */
.app-header {
  padding: 24px 0 16px;
  border-bottom: 1px solid var(--border);
}
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-logo {
  font-size: 2.5rem;
}
.brand-title {
  font-size: 1.375rem;
  font-weight: 800;
  color: var(--text-main);
  line-height: 1.2;
}
.brand-subtitle {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-top: 2px;
}
.btn-import-header {
  padding: 8px 14px;
  background-color: var(--primary-light);
  color: var(--primary);
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
}

/* Draft Resume Banner */
.draft-resume-banner {
  background-color: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.draft-resume-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.875rem;
  color: #92400e;
}
.draft-icon {
  font-size: 1.5rem;
}
.draft-actions {
  display: flex;
  gap: 8px;
}
.btn-resume {
  padding: 6px 12px;
  background-color: #d97706;
  color: #ffffff;
  border-radius: 6px;
  font-size: 0.8125rem;
  font-weight: 600;
}
.btn-discard {
  padding: 6px 10px;
  color: #78350f;
  font-size: 0.8125rem;
}

/* Bank Section */
.section-title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-main);
}
.btn-refresh {
  font-size: 0.8125rem;
  color: var(--primary);
}

.empty-bank-card {
  text-align: center;
  padding: 48px 16px;
  background-color: #ffffff;
  border-radius: 16px;
  border: 1px dashed var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.empty-icon {
  font-size: 3.5rem;
}

.bank-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.bank-card {
  background-color: #ffffff;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.15s, box-shadow 0.15s;
}
.bank-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.bank-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
}
.bank-category {
  background-color: #f1f5f9;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 4px;
}
.bank-count {
  font-weight: 700;
  color: var(--primary);
}

.bank-name {
  font-size: 1.0625rem;
  font-weight: 700;
  color: var(--text-main);
}
.bank-desc {
  font-size: 0.8125rem;
  color: var(--text-muted);
  line-height: 1.4;
  min-height: 2.8em;
}

.bank-actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-top: auto;
  padding-top: 8px;
}

.btn-mode {
  padding: 8px 4px;
  border-radius: 8px;
  font-size: 0.8125rem;
  font-weight: 600;
  text-align: center;
  transition: background-color 0.15s;
}
.btn-mode:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-practice {
  background-color: var(--primary-light);
  color: var(--primary);
}
.btn-exam {
  background-color: #fef3c7;
  color: #b45309;
}
.btn-elimination {
  background-color: var(--danger-light);
  color: var(--danger);
}

/* Modals */
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(2px);
  z-index: 150;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.import-modal {
  background-color: #ffffff;
  border-radius: 16px;
  width: 100%;
  max-width: 520px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
}
.btn-close {
  font-size: 1.25rem;
  color: var(--text-muted);
}

.modal-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 70vh;
  overflow-y: auto;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.875rem;
}
.form-select, .form-input, .form-textarea {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 0.875rem;
}
.form-textarea {
  resize: vertical;
  line-height: 1.5;
}

.format-radios {
  display: flex;
  gap: 16px;
  font-size: 0.8125rem;
}

.modal-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.btn-cancel {
  padding: 8px 16px;
  color: var(--text-muted);
}
.btn-primary {
  padding: 8px 18px;
  background-color: var(--primary);
  color: #ffffff;
  border-radius: 8px;
  font-weight: 600;
}
.btn-primary:disabled {
  background-color: #cbd5e1;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e8f0;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
