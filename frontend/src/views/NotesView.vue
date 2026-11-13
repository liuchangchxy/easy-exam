<template>
  <div class="library-page notes-page" :class="{ 'is-reader-open': readerOpen && selected }">
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
        <input v-model.trim="searchQuery" class="input" :placeholder="t('ep.library.search')" :aria-label="t('ep.library.search')" />
      </div>
      <div class="tabs library-tabs">
        <button v-for="tab in tabs" :key="tab.key" type="button" class="tab" :class="{ 'is-active': filterType === tab.key }" @click="filterType = tab.key">
          {{ t(tab.label) }}<span class="count">{{ tab.count }}</span>
        </button>
      </div>
    </div>

    <div v-if="notice && !readerOpen" class="notice" :class="noticeIsError ? 'bad' : 'ok'" style="margin-top: 16px">
      <LinearIcon :name="noticeIsError ? 'alert' : 'check'" :size="15" /><span>{{ notice }}</span>
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

    <div v-else class="notes-layout">
      <div class="notes-list">
        <button
          v-for="item in filteredAssets"
          :key="item.id"
          type="button"
          class="library-row"
          :class="{ 'is-active': selectedId === item.id }"
          @click="openReader(item, $event)"
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

      <article
        v-if="selected"
        class="notes-reader"
        :class="{ 'is-open': readerOpen }"
        role="dialog"
        aria-modal="true"
        :aria-label="plainTitle(selected)"
      >
        <div class="notes-reader-head">
          <div style="min-width: 0; flex: 1">
            <div class="page-eyebrow">{{ formatType(selected.asset_type) }} · {{ formatDate(selected.created_at) }}</div>
            <h2 class="reader-title notes-reader-title">{{ plainTitle(selected) }}</h2>
          </div>
          <button ref="readerCloseRef" type="button" class="icon-btn notes-reader-close" :aria-label="t('ep.common.close')" @click="closeReader">
            <LinearIcon name="x" :size="17" />
          </button>
        </div>

        <div v-if="notice" class="notice notes-reader-notice" :class="noticeIsError ? 'bad' : 'ok'" role="status">
          <LinearIcon :name="noticeIsError ? 'alert' : 'check'" :size="15" /><span>{{ notice }}</span>
        </div>

        <div v-if="editingNote" class="reader-edit notes-reader-edit">
          <textarea v-model="editContent" class="textarea reader-edit-input" rows="10" :placeholder="t('ep.library.note_body_placeholder')" :aria-label="t('ep.library.note_body')"></textarea>
          <div class="reader-edit-actions">
            <button type="button" class="btn btn-sm" :disabled="savingNote" @click="cancelEdit">{{ t('ep.common.cancel') }}</button>
            <button type="button" class="btn btn-sm btn-primary" :disabled="savingNote || !editContent.trim()" @click="saveNote">
              {{ savingNote ? t('ep.library.saving') : t('ep.common.save') }}
            </button>
          </div>
        </div>
        <div v-else class="reader-body notes-reader-body">{{ selected.content || selected.file_name }}</div>

        <div v-if="selected.file_name" class="reader-file notes-reader-file">
          <LinearIcon name="file" :size="15" />
          <span class="mono reader-file-name">{{ selected.file_name }}</span>
          <span class="reader-file-actions">
            <button type="button" class="btn btn-sm btn-quiet file-preview" @click="previewFile(selected)">{{ t('ep.library.preview_file') }}</button>
            <button type="button" class="btn btn-sm btn-quiet file-download" @click="downloadFile(selected)">{{ t('ep.library.download_file') }}</button>
          </span>
        </div>
        <div class="reader-foot notes-reader-foot">
          <button v-if="!editingNote" type="button" class="btn btn-sm note-edit" @click="startEdit(selected)">
            {{ t('ep.library.note_edit') }}
          </button>
          <button type="button" class="btn btn-sm btn-danger note-delete" :disabled="savingNote" @click="handleDelete(selected.id)">
            {{ t('ep.library.delete_asset') }}
          </button>
        </div>
      </article>
    </div>

    <div
      v-if="showUnsavedDialog"
      class="exam-setup-backdrop"
      data-testid="unsaved-edit-dialog"
      @click.self="cancelUnsavedDecision"
      @keydown.esc="cancelUnsavedDecision"
    >
      <div class="exam-setup-dialog" role="dialog" aria-modal="true" :aria-label="t('ep.library.note_unsaved_title')">
        <h2>{{ t('ep.library.note_unsaved_title') }}</h2>
        <p>{{ t('ep.library.note_unsaved_desc') }}</p>
        <p v-if="unsavedError" class="error">{{ unsavedError }}</p>
        <div class="bank-actions">
          <button type="button" @click="cancelUnsavedDecision">{{ t('ep.common.cancel') }}</button>
          <button type="button" class="btn btn-danger" :disabled="savingNote" @click="discardAndContinue">{{ t('ui.k0214') }}</button>
          <button type="button" class="btn btn-primary" :disabled="savingNote || !editContent.trim()" @click="saveAndContinue">
            {{ savingNote ? t('ep.library.saving') : t('ep.common.save') }}
          </button>
        </div>
      </div>
    </div>

    <AppDialog
      :open="showAddModal"
      :title="t('ep.library.note_create')"
      class="library-dialog"
      style="--app-dialog-width: 520px"
      initial-focus="#note-create-content"
      data-testid="note-create-dialog"
      @close="closeCreateDialog"
    >
      <form id="note-create-form" class="form-grid" @submit.prevent="handleCreateAsset">
        <p class="hint">{{ t('ep.library.new_note_desc') }}</p>
        <label class="field"><span class="label">{{ t('ep.library.type_label') }}</span>
          <select v-model="newAssetType" class="select">
            <option value="NOTE">{{ t('ep.library.type_note') }}</option>
            <option value="MISTAKE_SUMMARY">{{ t('ep.library.type_summary') }}</option>
            <option value="KNOWLEDGE">{{ t('ep.library.type_knowledge') }}</option>
          </select>
        </label>
        <label class="field"><span class="label">{{ t('ep.library.note_body') }}</span>
          <textarea id="note-create-content" v-model="newAssetContent" class="textarea" rows="7" :placeholder="t('ep.library.note_body_placeholder')"></textarea>
        </label>
        <p class="hint">{{ t('ep.library.upload_hint') }}</p>
      </form>
      <template #foot>
        <button type="button" class="btn btn-quiet" @click="closeCreateDialog">{{ t('ep.common.cancel') }}</button>
        <button type="submit" class="btn btn-primary" form="note-create-form" :disabled="savingAsset || !newAssetContent.trim()">
          {{ savingAsset ? t('ep.library.saving') : t('ep.common.save') }}
        </button>
      </template>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import AppDialog from '../components/AppDialog.vue'
import { useLocale } from '../composables/useLocale.js'
import { readQueryEnum, readQueryString, replaceQueryState } from '../utils/routeQuery.js'
import { listAssets, createAsset, uploadAssetFile, updateAsset, deleteAsset, fetchAssetBlob } from '../api/assets'

const props = defineProps({
  token: { type: String, required: true },
})

const { t, locale } = useLocale()
const route = useRoute()
const router = useRouter()

const LIBRARY_TYPE_KEYS = ['ALL', 'NOTE', 'MISTAKE_SUMMARY', 'KNOWLEDGE']
const LIBRARY_QUERY_DEFAULTS = { type: 'ALL', q: '' }

const assetsList = ref([])
const loadingAssets = ref(false)
const showAddModal = ref(false)
const savingAsset = ref(false)
const uploadingAsset = ref(false)
const newAssetType = ref('NOTE')
const newAssetContent = ref('')
const filterType = ref(readQueryEnum(route?.query?.type, LIBRARY_TYPE_KEYS, 'ALL'))
const searchQuery = ref(readQueryString(route?.query?.q))
const selectedId = ref('')
const readerOpen = ref(false)
const notice = ref('')
const noticeIsError = ref(false)
const editingNote = ref(false)
const editContent = ref('')
const savingNote = ref(false)
const showUnsavedDialog = ref(false)
const unsavedError = ref('')
let pendingAfterDiscard = null
const fileInputRef = ref(null)
const readerCloseRef = ref(null)
const readerTrigger = ref(null)

const tabs = computed(() => [
  { key: 'ALL', label: 'ep.common.all', count: assetsList.value.length },
  { key: 'NOTE', label: 'ep.library.type_note', count: countType('NOTE') },
  { key: 'MISTAKE_SUMMARY', label: 'ep.library.type_summary', count: countType('SUMMARY') },
  { key: 'KNOWLEDGE', label: 'ep.library.type_knowledge', count: countType('MNEMONIC') },
])

// Search and type filter are URL state: a refreshed tab, a browser Back or a
// link to "笔记 + keyword" must reopen the same list.
function syncLibraryQuery(patch) {
  replaceQueryState(router, route?.query, patch, LIBRARY_QUERY_DEFAULTS)
}

watch(filterType, value => syncLibraryQuery({ type: value }))

watch(searchQuery, value => syncLibraryQuery({ q: String(value || '').trim() }))

watch(() => route?.query?.type, value => {
  const next = readQueryEnum(value, LIBRARY_TYPE_KEYS, 'ALL')
  if (next !== filterType.value) filterType.value = next
})

watch(() => route?.query?.q, value => {
  const next = readQueryString(value)
  if (next !== searchQuery.value) searchQuery.value = next
})

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

watch(selectedId, () => {
  editingNote.value = false
  editContent.value = ''
})

function hasUnsavedEdit() {
  if (!editingNote.value || !selected.value) return false
  return editContent.value !== (selected.value.content || '')
}

function openReaderNow(item, trigger) {
  readerTrigger.value = trigger || null
  selectedId.value = item.id
  readerOpen.value = true
  nextTick(() => readerCloseRef.value?.focus?.())
}

function openReader(item, event) {
  if (!item) return
  const trigger = event?.currentTarget || null
  if (item.id !== selectedId.value && hasUnsavedEdit()) {
    pendingAfterDiscard = () => openReaderNow(item, trigger)
    unsavedError.value = ''
    showUnsavedDialog.value = true
    return
  }
  openReaderNow(item, trigger)
}

function closeReaderNow() {
  const trigger = readerTrigger.value
  readerOpen.value = false
  editingNote.value = false
  editContent.value = ''
  readerTrigger.value = null
  nextTick(() => {
    if (trigger && typeof trigger.focus === 'function') trigger.focus()
  })
}

function closeReader() {
  if (hasUnsavedEdit()) {
    pendingAfterDiscard = () => closeReaderNow()
    unsavedError.value = ''
    showUnsavedDialog.value = true
    return
  }
  closeReaderNow()
}

function finishPendingDiscard() {
  const pending = pendingAfterDiscard
  pendingAfterDiscard = null
  showUnsavedDialog.value = false
  unsavedError.value = ''
  if (typeof pending === 'function') pending()
}

function discardAndContinue() {
  editingNote.value = false
  editContent.value = ''
  notice.value = ''
  finishPendingDiscard()
}

async function saveAndContinue() {
  unsavedError.value = ''
  const saved = await saveNote()
  if (!saved) {
    unsavedError.value = notice.value || t('ep.library.saving')
    return
  }
  finishPendingDiscard()
}

function cancelUnsavedDecision() {
  pendingAfterDiscard = null
  showUnsavedDialog.value = false
  unsavedError.value = ''
}

function onReaderKeydown(event) {
  if (event.key !== 'Escape') return
  // AppDialog handles Escape for its own dialogs from a document capture
  // listener and prevents the default before this bubble-phase handler runs.
  // Without this guard, dismissing the create dialog would also close the
  // reader (or raise its unsaved prompt) in the same keystroke.
  if (event.defaultPrevented) return
  if (showUnsavedDialog.value) {
    event.preventDefault()
    cancelUnsavedDecision()
    return
  }
  if (readerOpen.value) {
    event.preventDefault()
    closeReader()
  }
}

function showNotice(message, isError = true) {
  notice.value = message || ''
  noticeIsError.value = isError
}

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
    showNotice(err.detail || err.message)
  } finally {
    loadingAssets.value = false
  }
}

function openCreate() {
  newAssetContent.value = ''
  newAssetType.value = 'NOTE'
  showAddModal.value = true
}

function closeCreateDialog() {
  showAddModal.value = false
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
    showNotice(err.detail || err.message)
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
    showNotice(err.detail || err.message)
  } finally {
    uploadingAsset.value = false
    e.target.value = ''
  }
}

function startEdit(item) {
  if (!item) return
  selectedId.value = item.id
  editContent.value = item.content || ''
  editingNote.value = true
  notice.value = ''
}

function cancelEdit() {
  editingNote.value = false
  editContent.value = ''
}

async function saveNote() {
  const item = selected.value
  if (!item || !editContent.value.trim()) return false
  savingNote.value = true
  notice.value = ''
  try {
    const updated = await updateAsset(props.token, item.id, { content: editContent.value.trim() })
    assetsList.value = assetsList.value.map(asset => asset.id === updated.id ? { ...asset, ...updated } : asset)
    editingNote.value = false
    showNotice(t('ep.library.note_saved'), false)
    return true
  } catch (err) {
    showNotice(err.detail || err.message)
    return false
  } finally {
    savingNote.value = false
  }
}

async function previewFile(item) {
  if (!item) return
  const previewWindow = window.open('', '_blank')
  notice.value = ''
  try {
    const { blob } = await fetchAssetBlob(props.token, item.id)
    const url = URL.createObjectURL(blob)
    if (previewWindow) previewWindow.location.href = url
    else window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (err) {
    if (previewWindow) previewWindow.close()
    showNotice(err.detail || err.message)
  }
}

async function downloadFile(item) {
  if (!item) return
  notice.value = ''
  try {
    const { blob } = await fetchAssetBlob(props.token, item.id, { download: true })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = item.file_name || 'material'
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (err) {
    showNotice(err.detail || err.message)
  }
}

async function handleDelete(id) {
  if (!window.confirm(t('ep.library.note_delete_confirm'))) return
  notice.value = ''
  try {
    await deleteAsset(props.token, id)
    closeReaderNow()
    await fetchAssets()
  } catch (err) {
    showNotice(err.detail || err.message)
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

onMounted(() => {
  fetchAssets()
  window.addEventListener('keydown', onReaderKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onReaderKeydown)
})
</script>

<style scoped>
.library-page { padding-top: 26px; }
.file-input-hidden { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.library-toolbar { border-top: 0; margin-top: 0; }
.library-tabs { border-bottom: 0; }
.library-empty { margin-top: 28px; }
.notes-layout { margin-top: 18px; border-top: 1px solid var(--line); transition: padding-right .18s var(--ease); }
.notes-list { max-height: none; overflow-y: visible; }
.library-row {
  display: flex; align-items: center; gap: 12px; width: 100%;
  padding: 13px 14px 13px 4px; border: 0; border-bottom: 1px solid var(--line);
  background: none; text-align: left; color: var(--ink-2); cursor: pointer;
}
.library-row:hover { background: var(--surface-2); }
.library-row.is-active { background: var(--surface); box-shadow: inset 2px 0 0 var(--brand); }
.library-row-main { display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; }
.library-row-title { font-size: 13px; line-height: 1.55; color: var(--ink); overflow-wrap: anywhere; }
.library-row-meta { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; font-size: 12px; color: var(--ink-3); }
.notes-reader {
  position: fixed; top: var(--topbar-h); right: 0; bottom: 0;
  z-index: 45; width: min(460px, 100vw);
  display: flex; flex-direction: column; min-width: 0;
  background: var(--surface);
  border-left: 1px solid var(--line-strong);
  box-shadow: -24px 0 60px -40px rgba(20, 23, 19, .5);
  transform: translateX(100%); visibility: hidden;
  transition: transform .18s var(--ease), visibility .18s;
}
.notes-reader.is-open { transform: none; visibility: visible; }
.notes-reader-head { flex: none; display: flex; align-items: flex-start; gap: 12px; padding: 20px 24px 14px; border-bottom: 1px solid var(--line); }
.notes-reader-notice { flex: none; margin: 12px 24px 0; }
.notes-reader-title { margin-top: 4px; }
.notes-reader-close { flex: none; }
.notes-reader-body { flex: 1; overflow-y: auto; padding: 22px 24px 30px; }
.notes-reader-edit { flex: 1; overflow-y: auto; padding: 18px 24px; }
.notes-reader-file { padding: 10px 24px; background: var(--surface); }
.notes-reader-foot { flex: none; padding: 12px 24px calc(12px + env(safe-area-inset-bottom)); }
.reader-title { margin: 6px 0 0; font-family: var(--font-serif); font-size: 24px; font-weight: 600; line-height: 1.45; overflow-wrap: anywhere; }
.reader-body { font-family: var(--font-serif); font-size: 15.5px; line-height: 1.95; color: var(--ink); white-space: pre-wrap; overflow-wrap: anywhere; }
.reader-edit { display: flex; flex-direction: column; gap: 10px; }
.reader-edit-input { width: 100%; min-height: 220px; resize: vertical; font-family: var(--font-serif); line-height: 1.8; }
.reader-edit-actions { display: flex; justify-content: flex-end; gap: 8px; }
.reader-file { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; border-top: 1px solid var(--line); font-size: 12px; color: var(--ink-2); }
.reader-file-name { overflow-wrap: anywhere; }
.reader-file-actions { margin-left: auto; display: flex; gap: 4px; flex-wrap: wrap; }
.reader-foot { display: flex; gap: 8px; border-top: 1px solid var(--line); }
@media (min-width: 1100px) {
  /* The fixed 460px reader overlays the right edge of the work surface.
     Keep the page head (upload / new note) clear of it. */
  .notes-page.is-reader-open .page-head { padding-right: 484px; }
  .notes-page.is-reader-open .notes-layout { padding-right: 460px; }
}
@media (max-width: 640px) {
  .library-toolbar { flex-wrap: wrap; gap: 10px; }
  .library-toolbar .search-box { width: 100%; }
  .library-tabs { gap: 16px; overflow-x: auto; }
  .library-tabs .tab { white-space: nowrap; }
  .reader-title { font-size: 20px; }
}
@media (max-width: 768px) {
  .notes-reader {
    top: 52px; width: 100%; z-index: 80;
    border-left: 0; box-shadow: none;
  }
  .notes-reader-head { padding: 16px 16px 12px; }
  .notes-reader-notice { margin: 12px 16px 0; }
  .notes-reader-body { padding: 16px 16px 24px; }
  .notes-reader-edit { padding: 16px 16px 20px; }
  .notes-reader-file { padding: 10px 16px; }
  .notes-reader-foot { padding: 10px 16px calc(10px + env(safe-area-inset-bottom)); }
  .notes-reader-foot .btn { flex: 1; }
}
</style>
