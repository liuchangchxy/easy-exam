<template>
  <div class="notes-page">
    <header class="notes-header">
      <div class="header-left">
        <div class="header-title-row">
          <LinearIcon name="edit" size="20" class="header-icon" />
          <h1>{{ t('nav.notes') }}</h1>
          <span class="count-badge font-mono-code">{{ assetsList.length }}</span>
        </div>
        <p class="header-desc">{{ t('notes.desc') }}</p>
      </div>
      <div class="header-actions">
        <button type="button" class="primary-btn" @click="showAddModal = true">
          <LinearIcon name="plus" size="14" />
          <span>{{ t('notes.add_btn') }}</span>
        </button>
      </div>
    </header>

    <!-- 快速创建卡片 -->
    <section v-if="showAddModal" class="add-note-card">
      <div class="card-header">
        <h3>{{ t('notes.new_title') }}</h3>
        <button type="button" class="btn-close" @click="showAddModal = false">✕</button>
      </div>
      <div class="add-note-body">
        <div class="form-row">
          <label>{{ t('notes.type_label') }}</label>
          <select v-model="newAssetType" class="select-type">
            <option value="NOTE">{{ t('notes.type_note') }}</option>
            <option value="MISTAKE_SUMMARY">{{ t('notes.type_summary') }}</option>
            <option value="KNOWLEDGE">{{ t('notes.type_knowledge') }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>{{ t('notes.content_label') }}</label>
          <textarea
            v-model="newAssetContent"
            rows="4"
            class="note-textarea"
            :placeholder="t('notes.placeholder')"
          ></textarea>
        </div>
        <div class="card-actions">
          <label class="btn-upload-file" :class="{ disabled: uploadingAsset }">
            <LinearIcon name="upload" size="14" />
            <span>{{ uploadingAsset ? t('notes.uploading') : t('notes.upload_file') }}</span>
            <input type="file" accept=".txt,.md,.pdf" style="display: none;" @change="handleFileUpload" />
          </label>
          <div class="action-buttons">
            <button type="button" class="secondary-btn" @click="showAddModal = false">{{ t('ui.k0134') }}</button>
            <button type="button" class="primary-btn" :disabled="savingAsset || !newAssetContent.trim()" @click="handleCreateAsset">
              {{ savingAsset ? t('ui.k0640') : t('notes.save_btn') }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- 过滤器与搜索栏 -->
    <div class="filter-bar">
      <div class="type-filter-group">
        <button
          type="button"
          class="filter-pill"
          :class="{ active: filterType === 'ALL' }"
          @click="filterType = 'ALL'"
        >
          {{ t('notes.filter_all') }}
        </button>
        <button
          type="button"
          class="filter-pill"
          :class="{ active: filterType === 'NOTE' }"
          @click="filterType = 'NOTE'"
        >
          {{ t('notes.type_note') }}
        </button>
        <button
          type="button"
          class="filter-pill"
          :class="{ active: filterType === 'MISTAKE_SUMMARY' }"
          @click="filterType = 'MISTAKE_SUMMARY'"
        >
          {{ t('notes.type_summary') }}
        </button>
        <button
          type="button"
          class="filter-pill"
          :class="{ active: filterType === 'KNOWLEDGE' }"
          @click="filterType = 'KNOWLEDGE'"
        >
          {{ t('notes.type_knowledge') }}
        </button>
      </div>
      <div class="search-box">
        <LinearIcon name="search" size="14" />
        <input v-model="searchQuery" type="text" :placeholder="t('notes.search_placeholder')" />
      </div>
    </div>

    <!-- 笔记卡片栅格 -->
    <div v-if="loadingAssets" class="loading-state">
      <div class="spinner"></div>
      <p>{{ t('ui.k0254') }}</p>
    </div>

    <div v-else-if="filteredAssets.length === 0" class="empty-state">
      <div class="empty-icon"><LinearIcon name="file" size="32" /></div>
      <h3>{{ t('notes.empty_title') }}</h3>
      <p>{{ t('notes.empty_desc') }}</p>
      <button type="button" class="primary-btn" @click="showAddModal = true">
        <LinearIcon name="plus" size="14" />
        <span>{{ t('notes.add_first') }}</span>
      </button>
    </div>

    <div v-else class="notes-grid">
      <article v-for="item in filteredAssets" :key="item.id" class="note-card">
        <div class="note-card-top">
          <span class="type-pill" :class="item.asset_type.toLowerCase()">
            {{ formatType(item.asset_type) }}
          </span>
          <div class="card-top-right">
            <span class="note-date font-mono-code">{{ formatDate(item.created_at) }}</span>
            <button type="button" class="btn-delete" :title="t('ui.k0137')" @click="handleDelete(item.id)">
              <LinearIcon name="trash" size="13" />
            </button>
          </div>
        </div>

        <div class="note-content">
          <p>{{ item.content || item.file_name }}</p>
        </div>

        <div v-if="item.file_name" class="note-file-badge">
          <LinearIcon name="file" size="13" />
          <span class="file-name" :title="item.file_name">{{ item.file_name }}</span>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import { listAssets, createAsset, uploadAssetFile, deleteAsset } from '../api/assets'

const props = defineProps({
  token: { type: String, required: true }
})

const { t } = useLocale()

const assetsList = ref([])
const loadingAssets = ref(false)
const showAddModal = ref(false)
const savingAsset = ref(false)
const uploadingAsset = ref(false)
const newAssetType = ref('NOTE')
const newAssetContent = ref('')
const filterType = ref('ALL')
const searchQuery = ref('')

async function fetchAssets() {
  if (!props.token) return
  loadingAssets.value = true
  try {
    const res = await listAssets(props.token)
    assetsList.value = Array.isArray(res) ? res : (res?.assets || [])
  } catch (err) {
    console.error('Failed to list assets', err)
  } finally {
    loadingAssets.value = false
  }
}

async function handleCreateAsset() {
  if (!newAssetContent.value.trim()) return
  savingAsset.value = true
  try {
    await createAsset(props.token, {
      asset_type: newAssetType.value,
      content: newAssetContent.value.trim()
    })
    newAssetContent.value = ''
    showAddModal.value = false
    await fetchAssets()
  } catch (err) {
    alert(`${t('ui.k0271')}${err.detail || err.message}`)
  } finally {
    savingAsset.value = false
  }
}

async function handleFileUpload(e) {
  const file = e.target?.files?.[0]
  if (!file) return
  uploadingAsset.value = true
  try {
    await uploadAssetFile(props.token, file, newAssetType.value)
    showAddModal.value = false
    await fetchAssets()
  } catch (err) {
    alert(`${t('ui.k0272')}${err.detail || err.message}`)
  } finally {
    uploadingAsset.value = false
    e.target.value = ''
  }
}

async function handleDelete(id) {
  if (!window.confirm(t('ui.k0273'))) return
  try {
    await deleteAsset(props.token, id)
    await fetchAssets()
  } catch (err) {
    alert(`${t('ui.k0274')}${err.detail || err.message}`)
  }
}

function formatType(type) {
  if (type === 'MISTAKE_SUMMARY') return t('notes.type_summary')
  if (type === 'KNOWLEDGE') return t('notes.type_knowledge')
  return t('notes.type_note')
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch (_) {
    return isoStr
  }
}

const filteredAssets = computed(() => {
  return assetsList.value.filter(item => {
    if (filterType.value !== 'ALL' && item.asset_type !== filterType.value) {
      return false
    }
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      const c = (item.content || '').toLowerCase()
      const f = (item.file_name || '').toLowerCase()
      if (!c.includes(q) && !f.includes(q)) return false
    }
    return true
  })
})

onMounted(() => {
  fetchAssets()
})
</script>

<style scoped>
.notes-page {
  padding: 1.75rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.notes-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  gap: 1rem;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.header-icon {
  color: var(--primary);
}

.notes-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-main);
}

.count-badge {
  font-size: 0.78rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.header-desc {
  font-size: 0.88rem;
  color: var(--text-muted);
  margin: 0.35rem 0 0 0;
}

.add-note-card {
  background: var(--bg-card);
  border: 1px solid var(--primary);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.card-header h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}

.btn-close {
  background: none;
  border: none;
  color: var(--text-tertiary);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-sm);
}

.btn-close:hover {
  color: var(--text-main);
  background: var(--bg-subtle);
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 0.85rem;
}

.form-row label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.select-type {
  width: 100%;
  max-width: 240px;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-page);
  color: var(--text-main);
  font-size: 0.88rem;
}

.note-textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-page);
  color: var(--text-main);
  font-size: 0.9rem;
  resize: vertical;
  line-height: 1.5;
}

.card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.btn-upload-file {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  color: var(--primary);
  background: var(--primary-light);
  padding: 0.45rem 0.8rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-weight: 500;
  transition: all 120ms ease;
}

.btn-upload-file:hover {
  opacity: 0.9;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.type-filter-group {
  display: flex;
  gap: 0.4rem;
}

.filter-pill {
  padding: 0.35rem 0.8rem;
  font-size: 0.82rem;
  border-radius: 9999px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 120ms ease;
}

.filter-pill.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
  font-weight: 600;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  min-width: 240px;
}

.search-box input {
  border: none;
  background: transparent;
  color: var(--text-main);
  font-size: 0.85rem;
  width: 100%;
  outline: none;
}

.notes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

.note-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  transition: transform 120ms ease, box-shadow 120ms ease;
}

.note-card:hover {
  border-color: var(--border-hover, #94a3b8);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.note-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.type-pill {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

.type-pill.note {
  background: var(--primary-light);
  color: var(--primary);
}

.type-pill.mistake_summary {
  background: var(--warning-light, #fef3c7);
  color: var(--warning, #d97706);
}

.type-pill.knowledge {
  background: var(--success-light, #d1fae5);
  color: var(--success, #059669);
}

.card-top-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.note-date {
  font-size: 0.72rem;
  color: var(--text-tertiary);
}

.btn-delete {
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 0.2rem;
  border-radius: var(--radius-xs);
  display: inline-flex;
  align-items: center;
}

.btn-delete:hover {
  color: var(--danger);
  background: var(--danger-light);
}

.note-content p {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.5;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.note-file-badge {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  color: var(--text-muted);
  background: var(--bg-subtle);
  padding: 0.3rem 0.5rem;
  border-radius: var(--radius-sm);
  margin-top: auto;
}

.note-file-badge .file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-state {
  text-align: center;
  padding: 3rem 1.5rem;
  background: var(--bg-card);
  border: 1px dashed var(--border);
  border-radius: var(--radius-xl);
  margin-top: 1rem;
}

.empty-icon {
  color: var(--text-tertiary);
  margin-bottom: 0.75rem;
}

.empty-state h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.15rem;
  color: var(--text-main);
}

.empty-state p {
  color: var(--text-muted);
  font-size: 0.88rem;
  max-width: 480px;
  margin: 0 auto 1.25rem auto;
  line-height: 1.5;
}

.loading-state {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
