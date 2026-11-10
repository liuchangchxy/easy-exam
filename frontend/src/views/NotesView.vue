<template>
  <div class="library-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.nav.study') }}</div>
        <h1 class="page-title">{{ t('ep.library.title') }}</h1>
        <p class="page-sub">{{ t('ep.library.sub') }}</p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn" :disabled="uploadingAsset" @click="triggerUpload">
          <LinearIcon name="upload" :size="14" />{{ uploadingAsset ? t('ep.library.uploading') : t('ep.library.upload') }}
        </button>
        <button type="button" class="btn btn-primary" @click="openCreate">
          <LinearIcon name="plus" :size="14" />{{ t('ep.library.new_note') }}
        </button>
        <input ref="fileInputRef" type="file" accept=".txt,.md,.pdf" class="file-input-hidden" @change="handleFileUpload" />
      </div>
    </div>

    <div class="toolbar library-toolbar">
      <div class="search-box">
        <LinearIcon name="search" :size="15" />
        <input v-model.trim="searchQuery" class="input" :placeholder="t('ep.library.search')" />
      </div>
      <div class="tabs library-tabs">
        <button v-for="tab in tabs" :key="tab.key" type="button" class="tab" :class="{ 'is-active': filterType === tab.key }" @click="filterType = tab.key">
          {{ t(tab.label) }}<span class="count">{{ tab.count }}</span>
        </button>
      </div>
    </div>

    <div v-if="notice" class="notice bad" style="margin-top: 16px">
      <LinearIcon name="alert" :size="15" /><span>{{ notice }}</span>
    </div>

    <div v-if="loadingAssets" class="skeleton-rows">
      <div class="skeleton"></div><div class="skeleton"></div>
    </div>

    <div v-else-if="!filteredAssets.length" class="empty library-empty">
      <div class="empty-mark"><LinearIcon name="note" :size="26" /></div>
      <div class="empty-title">{{ searchQuery ? t('ep.library.no_results') : t('ep.library.empty') }}</div>
      <div class="empty-desc">{{ searchQuery ? t('ep.library.search') : t('ep.library.empty_hint') }}</div>
      <div class="empty-actions">
        <button type="button" class="btn" @click="openCreate">{{ t('ep.library.empty_cta') }}</button>
        <button type="button" class="btn" @click="triggerUpload">{{ t('ep.library.upload') }}</button>
      </div>
    </div>

    <div v-else class="library-layout">
      <div class="library-list">
        <button
          v-for="item in filteredAssets"
          :key="item.id"
          type="button"
          class="library-row"
          :class="{ 'is-active': selectedId === item.id }"
          @click="selectedId = item.id"
        >
          <span class="library-row-main">
            <span class="library-row-title">{{ plainTitle(item) }}</span>
            <span class="library-row-meta">
              <span>{{ formatType(item.asset_type) }}</span>
              <span>{{ formatDate(item.created_at) }}</span>
              <span v-if="item.file_name" class="tag mono">{{ fileLabel(item.file_name) }}</span>
            </span>
          </span>
          <LinearIcon name="chevron-right" :size="14" />
        </button>
      </div>

      <article v-if="selected" class="library-reader">
        <div class="reader-head">
          <div class="page-eyebrow">{{ formatType(selected.asset_type) }} · {{ formatDate(selected.created_at) }}</div>
          <h2 class="reader-title">{{ plainTitle(selected) }}</h2>
        </div>
        <div class="reader-body">{{ selected.content || selected.file_name }}</div>
        <div v-if="selected.file_name" class="reader-file">
          <LinearIcon name="file" :size="15" />
          <span class="mono">{{ selected.file_name }}</span>
        </div>
        <div class="reader-foot">
          <button type="button" class="btn btn-sm btn-danger" @click="handleDelete(selected.id)">
            {{ t('ep.library.delete_asset') }}
          </button>
        </div>
      </article>
    </div>

    <div v-if="showAddModal" class="exam-setup-backdrop" @click.self="showAddModal = false">
      <form class="exam-setup-dialog library-dialog" role="dialog" aria-modal="true" @submit.prevent="handleCreateAsset">
        <h2>{{ t('ep.library.note_create') }}</h2>
        <p class="hint">{{ t('ep.library.new_note_desc') }}</p>
        <label>{{ t('ep.library.type_label') }}
          <select v-model="newAssetType">
            <option value="NOTE">{{ t('ep.library.type_note') }}</option>
            <option value="MISTAKE_SUMMARY">{{ t('ep.library.type_summary') }}</option>
            <option value="KNOWLEDGE">{{ t('ep.library.type_knowledge') }}</option>
          </select>
        </label>
        <label>{{ t('ep.library.note_body') }}
          <textarea v-model="newAssetContent" rows="7" :placeholder="t('ep.library.note_body_placeholder')"></textarea>
        </label>
        <p class="hint">{{ t('ep.library.upload_hint') }}</p>
        <div class="bank-actions">
          <button type="button" @click="showAddModal = false">{{ t('ep.common.cancel') }}</button>
          <button type="submit" class="primary" :disabled="savingAsset || !newAssetContent.trim()">
            {{ savingAsset ? t('ep.library.saving') : t('ep.common.save') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import { listAssets, createAsset, uploadAssetFile, deleteAsset } from '../api/assets'

const props = defineProps({
  token: { type: String, required: true },
})

const { t, locale } = useLocale()

const assetsList = ref([])
const loadingAssets = ref(false)
const showAddModal = ref(false)
const savingAsset = ref(false)
const uploadingAsset = ref(false)
const newAssetType = ref('NOTE')
const newAssetContent = ref('')
const filterType = ref('ALL')
const searchQuery = ref('')
const selectedId = ref('')
const notice = ref('')
const fileInputRef = ref(null)

const tabs = computed(() => [
  { key: 'ALL', label: 'ep.common.all', count: assetsList.value.length },
  { key: 'NOTE', label: 'ep.library.type_note', count: countType('NOTE') },
  { key: 'MISTAKE_SUMMARY', label: 'ep.library.type_summary', count: countType('SUMMARY') },
  { key: 'KNOWLEDGE', label: 'ep.library.type_knowledge', count: countType('MNEMONIC') },
])

const filteredAssets = computed(() => {
  return assetsList.value.filter(item => {
    if (filterType.value !== 'ALL') {
      const match = (filterType.value === item.asset_type) ||
        (filterType.value === 'MISTAKE_SUMMARY' && item.asset_type === 'SUMMARY') ||
        (filterType.value === 'KNOWLEDGE' && item.asset_type === 'MNEMONIC')
      if (!match) return false
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

const selected = computed(() => filteredAssets.value.find(item => item.id === selectedId.value) || filteredAssets.value[0] || null)

watch(filteredAssets, list => {
  if (!list.length) selectedId.value = ''
  else if (!list.some(item => item.id === selectedId.value)) selectedId.value = list[0].id
})

function countType(type) {
  return assetsList.value.filter(item => item.asset_type === type).length
}

async function fetchAssets() {
  if (!props.token) return
  loadingAssets.value = true
  notice.value = ''
  try {
    const res = await listAssets(props.token)
    assetsList.value = Array.isArray(res) ? res : (res?.assets || [])
  } catch (err) {
    notice.value = err.detail || err.message
  } finally {
    loadingAssets.value = false
  }
}

function openCreate() {
  newAssetContent.value = ''
  newAssetType.value = 'NOTE'
  showAddModal.value = true
}

function triggerUpload() {
  fileInputRef.value?.click()
}

function apiType() {
  if (newAssetType.value === 'MISTAKE_SUMMARY') return 'SUMMARY'
  if (newAssetType.value === 'KNOWLEDGE') return 'MNEMONIC'
  return newAssetType.value
}

async function handleCreateAsset() {
  if (!newAssetContent.value.trim()) return
  savingAsset.value = true
  notice.value = ''
  try {
    await createAsset(props.token, {
      asset_type: apiType(),
      content: newAssetContent.value.trim(),
    })
    newAssetContent.value = ''
    showAddModal.value = false
    await fetchAssets()
  } catch (err) {
    notice.value = err.detail || err.message
  } finally {
    savingAsset.value = false
  }
}

async function handleFileUpload(e) {
  const file = e.target?.files?.[0]
  if (!file) return
  uploadingAsset.value = true
  notice.value = ''
  try {
    await uploadAssetFile(props.token, file, apiType())
    showAddModal.value = false
    await fetchAssets()
  } catch (err) {
    notice.value = err.detail || err.message
  } finally {
    uploadingAsset.value = false
    e.target.value = ''
  }
}

async function handleDelete(id) {
  if (!window.confirm(t('ep.library.note_delete_confirm'))) return
  notice.value = ''
  try {
    await deleteAsset(props.token, id)
    await fetchAssets()
  } catch (err) {
    notice.value = err.detail || err.message
  }
}

function formatType(type) {
  if (type === 'MISTAKE_SUMMARY' || type === 'SUMMARY') return t('ep.library.type_summary')
  if (type === 'KNOWLEDGE' || type === 'MNEMONIC') return t('ep.library.type_knowledge')
  return t('ep.library.type_note')
}

function plainTitle(item) {
  const text = String(item.content || item.file_name || '').trim().replace(/\s+/g, ' ')
  if (!text) return formatType(item.asset_type)
  return text.length > 56 ? text.slice(0, 56) + '…' : text
}

function fileLabel(name) {
  const parts = String(name).split('.')
  return parts.length > 1 ? '.' + parts.pop() : name
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return new Intl.DateTimeFormat(locale.value, { month: 'short', day: 'numeric' }).format(d)
  } catch (_) {
    return isoStr
  }
}

onMounted(fetchAssets)
</script>

<style scoped>
.library-page { padding-top: 26px; }
.file-input-hidden { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.library-toolbar { border-top: 0; margin-top: 0; }
.library-tabs { border-bottom: 0; }
.library-empty { margin-top: 28px; }
.library-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: 0; margin-top: 18px; border-top: 1px solid var(--line); }
.library-list { border-right: 1px solid var(--line); max-height: 72vh; overflow-y: auto; }
.library-row {
  display: flex; align-items: center; gap: 12px; width: 100%;
  padding: 13px 14px 13px 4px; border: 0; border-bottom: 1px solid var(--line);
  background: none; text-align: left; color: var(--ink-2); cursor: pointer;
}
.library-row:hover { background: var(--surface-2); }
.library-row.is-active { background: var(--surface); box-shadow: inset 2px 0 0 var(--brand); }
.library-row-main { display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; }
.library-row-title { font-size: 13px; line-height: 1.55; color: var(--ink); overflow-wrap: anywhere; }
.library-row-meta { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; font-size: 10.5px; color: var(--ink-3); }
.library-reader { padding: 24px 30px 30px; min-width: 0; }
.reader-head { border-bottom: 1px solid var(--line); padding-bottom: 16px; }
.reader-title { margin: 6px 0 0; font-family: var(--font-serif); font-size: 24px; font-weight: 600; line-height: 1.45; overflow-wrap: anywhere; }
.reader-body { padding: 22px 0; font-family: var(--font-serif); font-size: 15.5px; line-height: 1.95; color: var(--ink); white-space: pre-wrap; overflow-wrap: anywhere; }
.reader-file { display: flex; align-items: center; gap: 8px; padding: 10px 0; border-top: 1px solid var(--line); font-size: 11.5px; color: var(--ink-2); }
.reader-foot { display: flex; gap: 8px; padding-top: 14px; border-top: 1px solid var(--line); }
.library-dialog { width: min(100%, 520px); }
@media (max-width: 860px) {
  .library-layout { grid-template-columns: minmax(0, 1fr); }
  .library-list { border-right: 0; max-height: none; }
  .library-reader { padding: 20px 0 24px; border-top: 1px solid var(--line); }
}
@media (max-width: 640px) {
  .library-toolbar { flex-wrap: wrap; gap: 10px; }
  .library-toolbar .search-box { width: 100%; }
  .library-tabs { gap: 16px; overflow-x: auto; }
  .library-tabs .tab { white-space: nowrap; }
  .reader-title { font-size: 20px; }
}
</style>
