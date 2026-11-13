<template>
  <div class="banks-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.brand.sub') }}</div>
        <h1 class="page-title">{{ t('ep.banks.title') }}</h1>
        <p class="page-sub">
          {{ showRecycle
            ? t('ep.banks.recycle_sub', { count: banks.length })
            : t('ep.banks.sub', { count: banks.length }) }}
        </p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn" @click="router.push('/import')">
          <LinearIcon name="upload" :size="14" />{{ t('ep.common.import') }}
        </button>
        <button type="button" class="btn btn-primary" @click="openCreate">
          <LinearIcon name="plus" :size="14" />{{ t('ep.today.create_bank') }}
        </button>
      </div>
    </div>

    <div class="toolbar banks-toolbar">
      <div class="search-box">
        <LinearIcon name="search" :size="15" />
        <input v-model.trim="query" class="input" :placeholder="t('ep.banks.search')" :aria-label="t('ep.banks.search')" />
      </div>
      <label class="toolbar-field">
        <span class="toolbar-field-label">{{ t('ep.banks.filter_category') }}</span>
        <select v-model="category" class="select">
          <option value="">{{ t('ep.banks.all_categories') }}</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <button
        type="button"
        class="btn btn-sm btn-quiet"
        data-testid="bank-category-manage"
        :disabled="!hasAdminBank"
        :title="hasAdminBank ? null : t('ep.common.owner_only_action')"
        @click="openCategoryManager"
      >
        {{ t('ep.banks.category_manage') }}
      </button>
      <label class="toolbar-field">
        <span class="toolbar-field-label">{{ t('ep.banks.filter_sort') }}</span>
        <select v-model="sortKey" class="select" data-testid="bank-sort">
          <option value="recent">{{ t('ep.banks.sort_recent') }}</option>
          <option value="name">{{ t('ep.banks.sort_name') }}</option>
          <option value="count">{{ t('ep.banks.sort_count') }}</option>
        </select>
      </label>
      <div class="spacer"></div>
      <span class="small dim" data-testid="bank-filtered-count">
        {{ t('ep.common.filter') }} · {{ t('ep.manage.shown', { shown: filteredBanks.length, total: banks.length }) }}
      </span>
      <div class="banks-view-switch" role="group" :aria-label="t('ep.banks.title')">
        <button
          type="button"
          class="btn btn-sm"
          :class="{ 'btn-quiet': showRecycle, 'is-on': !showRecycle }"
          :aria-pressed="!showRecycle"
          data-testid="bank-view-all"
          @click="setView(false)"
        >
          {{ t('ep.banks.view_all') }}
        </button>
        <button
          type="button"
          class="btn btn-sm"
          :class="{ 'btn-quiet': !showRecycle, 'is-on': showRecycle }"
          :aria-pressed="showRecycle"
          data-testid="bank-recycle-toggle"
          @click="setView(!showRecycle)"
        >
          <LinearIcon name="archive" :size="13" />{{ t('ep.banks.recycle') }}
        </button>
      </div>
    </div>

    <div v-if="showRecycle" class="notice info recycle-notice">
      <LinearIcon name="info" :size="15" />
      <span>{{ t('ep.banks.recycle_note') }}</span>
      <button type="button" class="btn btn-sm btn-quiet" data-testid="bank-back-to-active" @click="setView(false)">
        {{ t('ep.banks.back_to_active') }}
      </button>
    </div>

    <div v-if="pageError && banks.length" class="notice bad practice-notice" role="alert">
      <LinearIcon name="alert" :size="15" />
      <span class="practice-notice-text">{{ pageError }}</span>
      <span class="practice-notice-actions">
        <button
          v-if="retryAction"
          type="button"
          class="btn btn-sm btn-quiet"
          data-testid="bank-error-retry"
          @click="retryPageAction"
        >{{ t('ep.common.retry') }}</button>
        <button
          type="button"
          class="icon-btn sm"
          data-testid="bank-error-dismiss"
          :aria-label="t('ep.common.close')"
          @click="dismissPageError"
        >
          <LinearIcon name="x" :size="14" />
        </button>
      </span>
    </div>
    <div v-if="successToast" class="notice ok practice-notice">
      <LinearIcon name="check" :size="15" /><span>{{ successToast }}</span>
    </div>

    <div v-if="selectedIds.size && !showRecycle" class="batch-bar bank-batch-bar">
      <div class="batch-bar-head">
        <span class="batch-title">{{ t('ep.banks.batch_selected', { count: selectedIds.size }) }}</span>
        <button type="button" class="btn btn-sm btn-quiet" @click="clearSelection">{{ t('ep.banks.clear_selection') }}</button>
      </div>
      <div class="batch-controls">
        <button
          type="button"
          class="btn btn-sm btn-danger"
          data-testid="bank-batch-archive"
          :disabled="batchBusy || !batchAllAdmin"
          :title="batchAllAdmin ? null : t('ep.common.owner_only_action')"
          @click="runBatch('archive')"
        >
          {{ t('ep.banks.action_archive') }}
        </button>
        <span class="batch-group">
          <input v-model.trim="batchCategory" class="input" :placeholder="t('ep.banks.category_placeholder')" :disabled="batchBusy" />
          <button
            type="button"
            class="btn btn-sm"
            data-testid="bank-batch-set-category"
            :disabled="batchBusy || !batchCategory || !batchAllAdmin"
            :title="batchAllAdmin ? null : t('ep.common.owner_only_action')"
            @click="runBatch('set_category')"
          >
            {{ t('ep.banks.set_category') }}
          </button>
        </span>
      </div>
    </div>

    <div v-if="loading" class="skeleton-rows">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </div>

    <div v-else-if="pageError && !banks.length" class="empty" data-testid="bank-load-error" role="alert">
      <div class="empty-title">{{ t('ep.common.load_failed') }}</div>
      <div class="empty-desc">{{ pageError }}</div>
      <div class="empty-actions">
        <button type="button" class="btn" data-testid="bank-retry" @click="load">{{ t('ep.common.retry') }}</button>
      </div>
    </div>

    <div v-else-if="filteredBanks.length" class="bank-list">
      <div v-for="bank in filteredBanks" :key="bank.id" class="banks-row" :class="{ 'recycle-row': showRecycle }">
        <label v-if="!showRecycle" class="bank-select-cell">
          <input
            type="checkbox"
            :checked="selectedIds.has(bank.id)"
            :aria-label="`${t('ep.banks.select_bank')} ${bank.name}`"
            @change="toggleBankSelection(bank.id)"
          />
        </label>
        <button
          v-if="!showRecycle"
          type="button"
          class="bank-open"
          :aria-label="`${t('ep.banks.open')} ${bank.name}`"
          @click="router.push(`/banks/${bank.id}`)"
        >
          <span class="od-stack" style="--od-gap:2px;text-align:left;min-width:0">
            <span class="bank-name">
              <span class="bank-name-text">{{ bank.name }}</span>
              <span v-if="bank.role !== 'ADMIN'" class="tag">{{ roleLabel(bank.role) }}</span>
              <span v-if="bank.has_active_exam" class="tag warn" :title="t('ep.manage.locked_desc')">{{ t('ep.today.active_badge') }}</span>
              <span v-if="bank.deleted" class="tag bad">{{ t('ep.banks.deleted_badge') }}</span>
            </span>
            <span class="bank-meta">
              <span>{{ bank.category || t('ep.common.none') }}</span>
              <span v-if="bank.archived_question_count" class="mono">{{ t('ep.banks.archived_count', { count: bank.archived_question_count }) }}</span>
              <span v-if="bank.description" class="od-truncate">{{ bank.description }}</span>
            </span>
          </span>
        </button>
        <div v-else class="bank-static">
          <span class="od-stack" style="--od-gap:2px;text-align:left;min-width:0">
            <span class="bank-name">
              <span class="bank-name-text">{{ bank.name }}</span>
              <span v-if="bank.role !== 'ADMIN'" class="tag">{{ roleLabel(bank.role) }}</span>
              <span v-if="bank.deleted" class="tag bad">{{ t('ep.banks.deleted_badge') }}</span>
            </span>
            <span class="bank-meta">
              <span>{{ bank.category || t('ep.common.none') }}</span>
              <span v-if="bank.archived_question_count" class="mono">{{ t('ep.banks.archived_count', { count: bank.archived_question_count }) }}</span>
              <span v-if="bank.description" class="od-truncate">{{ bank.description }}</span>
            </span>
          </span>
        </div>
        <span class="bank-count">
          <strong>{{ bank.question_count || 0 }}</strong>
          <span>{{ t('ui.k0101') }}</span>
        </span>
        <span class="bank-action-cluster">
          <template v-if="showRecycle">
            <button
              type="button"
              class="btn btn-sm"
              data-testid="row-restore"
              :aria-label="`${t('ep.banks.action_restore')} ${bank.name}`"
              @click.stop="restoreBankRow(bank)"
            >{{ t('ep.banks.action_restore') }}</button>
          </template>
          <template v-else>
            <span class="bank-actions-cell">
              <button
                type="button"
                class="btn btn-sm bank-practice-btn"
                :disabled="bank.deleted || Boolean(startingId)"
                :aria-busy="startingId === bank.id ? 'true' : 'false'"
                :aria-label="`${t('ep.banks.practice')} ${bank.name}`"
                @click.stop="startPractice(bank)"
              >{{ startingId === bank.id ? t('ep.common.starting') : t('ep.banks.practice') }}</button>
              <span v-if="bank.has_active_exam || bank.deleted" class="bank-manage-locked" :title="bank.deleted ? t('ep.banks.recycle_note') : t('ep.manage.locked_desc')">
                <button
                  type="button"
                  class="btn btn-sm btn-quiet"
                  disabled
                  :aria-label="`${t('ep.banks.manage')} ${bank.name} — ${t('ep.manage.locked_desc')}`"
                >{{ t('ep.banks.manage') }}</button>
              </span>
              <button
                v-else
                type="button"
                class="btn btn-sm btn-quiet"
                :aria-label="`${t('ep.banks.manage')} ${bank.name}`"
                @click.stop="router.push(`/banks/${bank.id}/manage`)"
              >{{ t('ep.banks.manage') }}</button>
            </span>
            <span class="bank-menu-wrap" @keydown.escape.stop.prevent="closeMenuAndRestore">
              <button
                type="button"
                class="icon-btn bank-menu-trigger"
                :aria-label="`${t('ep.banks.menu_label')} ${bank.name}`"
                :aria-expanded="openMenuId === bank.id"
                :aria-controls="openMenuId === bank.id ? `bank-menu-${bank.id}` : null"
                data-testid="bank-menu-trigger"
                @click.stop="toggleMenu(bank.id)"
              >
                <LinearIcon name="more" :size="16" />
              </button>
              <div v-if="openMenuId === bank.id" :id="`bank-menu-${bank.id}`" class="bank-menu-pop" data-testid="bank-menu" @click.stop>
                <button
                  type="button"
                  class="bank-menu-item"
                  :disabled="!isAdmin(bank)"
                  :title="isAdmin(bank) ? null : t('ep.common.owner_only_action')"
                  @click="openEdit(bank)"
                >{{ t('ep.banks.edit_meta') }}</button>
                <button type="button" class="bank-menu-item" @click="exportBankFile(bank, 'json')">{{ t('ep.banks.export_json') }}</button>
                <button type="button" class="bank-menu-item" @click="exportBankFile(bank, 'csv')">{{ t('ep.banks.export_csv') }}</button>
                <button
                  type="button"
                  class="bank-menu-item danger"
                  :disabled="!isAdmin(bank)"
                  :title="isAdmin(bank) ? null : t('ep.common.owner_only_action')"
                  @click="archiveBank(bank)"
                >{{ t('ep.banks.action_archive') }}</button>
              </div>
            </span>
          </template>
        </span>
      </div>
    </div>

    <div v-else-if="banks.length" class="empty" data-testid="bank-no-match">
      <div class="empty-title">{{ t('ep.banks.no_match') }}</div>
      <div class="empty-desc">{{ t('ep.banks.no_match_hint') }}</div>
      <div class="empty-actions">
        <button type="button" class="btn" data-testid="bank-clear-filters" @click="clearFilters">
          {{ t('ep.common.clear_filters') }}
        </button>
      </div>
    </div>

    <div v-else class="empty">
      <div class="empty-title">{{ showRecycle ? t('ep.banks.recycle_empty') : t('ep.banks.empty') }}</div>
      <div class="empty-desc">{{ showRecycle ? t('ep.banks.recycle_empty_hint') : t('ep.banks.empty_hint') }}</div>
      <div v-if="!showRecycle" class="empty-actions">
        <button type="button" class="btn btn-primary" @click="openCreate">{{ t('ep.today.create_bank') }}</button>
        <button type="button" class="btn" @click="router.push('/import')">{{ t('ep.common.import') }}</button>
      </div>
      <div v-else class="empty-actions">
        <button type="button" class="btn" @click="setView(false)">{{ t('ep.banks.back_to_active') }}</button>
      </div>
    </div>

    <AppDialog
      :open="showCreate"
      :title="t('ep.today.create_bank')"
      initial-focus="#bank-create-name"
      :close-on-backdrop="!createDirty"
      data-testid="bank-create-dialog"
      @close="requestCloseCreate"
    >
      <form id="bank-create-form" class="form-grid" @submit.prevent="createBank">
        <label class="field"><span class="label">{{ t('home.bank_name') }}</span>
          <input id="bank-create-name" v-model.trim="form.name" class="input" type="text" :placeholder="t('home.bank_name_placeholder')" required />
        </label>
        <label class="field"><span class="label">{{ t('home.category') }}</span>
          <input v-model.trim="form.category" class="input" type="text" :placeholder="t('home.category_placeholder')" />
        </label>
        <label class="field"><span class="label">{{ t('home.description') }}</span>
          <textarea v-model.trim="form.description" class="textarea" :placeholder="t('home.description_placeholder')" rows="3"></textarea>
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
      </form>
      <template #foot>
        <button type="button" class="btn btn-quiet" @click="requestCloseCreate">{{ t('common.cancel') }}</button>
        <button type="submit" class="btn btn-primary" form="bank-create-form" :disabled="creating">{{ t('ep.today.create_bank') }}</button>
      </template>
    </AppDialog>

    <AppDialog
      :open="showEdit"
      :title="t('ep.banks.edit_meta')"
      initial-focus="#bank-edit-name"
      :close-on-backdrop="!editDirty"
      @close="requestCloseEdit"
    >
      <form id="bank-edit-form" class="form-grid" @submit.prevent="saveBankMeta">
        <label class="field"><span class="label">{{ t('home.bank_name') }}</span>
          <input id="bank-edit-name" v-model.trim="editForm.name" class="input" type="text" required />
        </label>
        <label class="field"><span class="label">{{ t('home.category') }}</span>
          <input v-model.trim="editForm.category" class="input" type="text" :placeholder="t('home.category_placeholder')" />
        </label>
        <p class="hint">{{ t('ep.manage.category_keep_hint') }}</p>
        <label class="field"><span class="label">{{ t('home.description') }}</span>
          <textarea v-model.trim="editForm.description" class="textarea" rows="3"></textarea>
        </label>
        <p v-if="editError" class="error">{{ editError }}</p>
      </form>
      <template #foot>
        <button type="button" class="btn btn-quiet" @click="requestCloseEdit">{{ t('common.cancel') }}</button>
        <button type="submit" class="btn btn-primary" form="bank-edit-form" :disabled="editSaving">{{ t('common.save') }}</button>
      </template>
    </AppDialog>

    <AppDialog
      :open="discardPromptOpen"
      :title="t('ep.common.unsaved_title')"
      panel-class="discard-prompt-dialog"
      style="--app-dialog-width: 420px"
      initial-focus=".discard-cancel"
      @close="confirmDiscardCancel"
    >
      <p class="hint">{{ t('ep.common.unsaved_desc') }}</p>
      <template #foot>
        <button type="button" class="btn btn-quiet discard-cancel" @click="confirmDiscardCancel">{{ t('ep.common.keep_editing') }}</button>
        <button type="button" class="btn btn-primary discard-discard" @click="confirmDiscardAccept">{{ t('ep.common.discard') }}</button>
      </template>
    </AppDialog>

    <AppDialog
      :open="showCategories"
      :title="t('ep.banks.category_manage')"
      @close="showCategories = false"
    >
      <div class="category-list">
        <form v-for="row in categoryRows" :key="row.name" class="category-row" @submit.prevent="renameCategory(row)">
          <input v-model.trim="row.draft" class="input" :aria-label="t('ep.banks.category_rename')" />
          <span class="mono small dim">{{ row.count }}</span>
          <button type="submit" class="btn btn-sm" :disabled="!row.draft || row.draft === row.name">
            {{ t('ep.banks.category_rename') }}
          </button>
          <button type="button" class="btn btn-sm btn-danger" @click="removeCategory(row)">{{ t('ep.banks.category_delete') }}</button>
        </form>
        <p v-if="!categoryRows.length" class="hint">{{ t('ep.common.none') }}</p>
        <p v-if="categoryError" class="error">{{ categoryError }}</p>
      </div>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import AppDialog from '../components/AppDialog.vue'
import { useLocale } from '../composables/useLocale.js'
import { useDirtyGuard } from '../composables/useDirtyGuard.js'
import {
  listBanks,
  createBank as createBankApi,
  updateBank,
  deleteBank,
  restoreBank,
  batchBanks,
  listBankCategories,
  renameBankCategory,
  deleteBankCategory,
  downloadBankExport,
} from '../api/banks'
import { startSession } from '../api/practice'
import { triggerSyncEvent } from '../api/sync'
import { filterBankList, sortBankList } from '../domain/bankManage'
import {
  normalizeBankListQuery,
  readStoredBankListQuery,
  storeBankListQuery,
} from '../utils/bankListQuery'

const props = defineProps({ token: { type: String, required: true } })
const route = useRoute()
const router = useRouter()
const { t } = useLocale()

const banks = ref([])
// Ownership is a property of the user's banks, not of the current view. The
// recycle view only lists soft-deleted rows, so keep the last successful
// active-bank list to answer role questions there. It stays null until an
// active list has actually loaded; ownership is never invented.
const activeBanks = ref(null)
const loading = ref(true)
const query = ref('')
const category = ref('')
const sortKey = ref('recent')
const showRecycle = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const pageError = ref('')
const successToast = ref('')
const form = ref({ name: '', description: '', category: '' })

// The URL is the source of truth. When the layout's in-app back control returns
// to /banks without a query, replay the last list state kept in sessionStorage.
const routeSeed = normalizeBankListQuery(route?.query)
const seed = Object.keys(routeSeed).length ? routeSeed : readStoredBankListQuery()
query.value = seed.q || ''
sortKey.value = seed.sort || 'recent'
showRecycle.value = seed.view === 'recycle'
category.value = seed.category || ''

const openMenuId = ref('')
const selectedIds = ref(new Set())
const batchCategory = ref('')
const batchBusy = ref(false)
// The handler behind a retryable page error (batch / archive / restore).
const retryAction = ref(null)

const showEdit = ref(false)
const editSaving = ref(false)
const editError = ref('')
const editBankId = ref('')
const editForm = ref({ name: '', category: '', description: '' })
const editBaseline = ref('')

const startingId = ref('')

const showCategories = ref(false)
const categoryRows = ref([])
const categoryError = ref('')
let toastTimer = null

const createDirty = computed(() => Boolean(
  form.value.name || form.value.category || form.value.description,
))

const editDirty = computed(() => Boolean(editBaseline.value)
  && JSON.stringify(editForm.value) !== editBaseline.value)

const {
  confirmDiscard,
  discardPromptOpen,
  confirmDiscardAccept,
  confirmDiscardCancel,
} = useDirtyGuard(
  () => (showCreate.value ? createDirty.value : editDirty.value),
  (target) => {
    if (target === 'create') showCreate.value = false
    else if (target === 'edit') showEdit.value = false
  },
)

const categories = computed(() => [...new Set(banks.value.map(b => b.category).filter(Boolean))])

const filteredBanks = computed(() => sortBankList(
  filterBankList(banks.value, { query: query.value, category: category.value }),
  sortKey.value,
))

const hasAdminBank = computed(() => {
  const known = activeBanks.value ? [...activeBanks.value, ...banks.value] : banks.value
  return known.some(b => b.role === 'ADMIN')
})

const selectedBanks = computed(() => banks.value.filter(b => selectedIds.value.has(b.id)))

const batchAllAdmin = computed(() => selectedBanks.value.length > 0
  && selectedBanks.value.every(b => b.role === 'ADMIN'))

function isAdmin(bank) {
  return bank?.role === 'ADMIN'
}

function roleLabel(role) {
  if (role === 'EDITOR') return t('ep.banks.editor')
  return t('ep.banks.member')
}

function flash(text) {
  successToast.value = text
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { successToast.value = '' }, 4000)
}

function clearPageError() {
  pageError.value = ''
  retryAction.value = null
}

// Action failures stay visible until dismissed; retryable ones (batch /
// archive / restore) also offer to re-run the exact handler.
function showPageError(message, retry = null) {
  pageError.value = message
  retryAction.value = retry
}

function dismissPageError() {
  clearPageError()
}

async function retryPageAction() {
  const retry = retryAction.value
  clearPageError()
  if (retry) await retry()
}

// The URL echoes every state this view writes, and Back/Forward also arrives as
// a route.query change. Keys written by this view are remembered until their
// echo arrives; anything else is history navigation and is applied to the refs.
let applyingRoute = false
const pendingWrites = new Set()

function queryKey(query) {
  const normalized = normalizeBankListQuery(query)
  return Object.keys(normalized).sort().map(key => `${key}=${normalized[key]}`).join('&')
}

function currentListQuery() {
  return normalizeBankListQuery({
    q: query.value,
    // The category filter applies to both views; dropping it in recycle would
    // let reload / Back silently lose the user's filter.
    category: category.value,
    sort: sortKey.value === 'recent' ? '' : sortKey.value,
    view: showRecycle.value ? 'recycle' : '',
  })
}

function sameQuery(a, b) {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  for (const key of keys) {
    if (a[key] !== b[key]) return false
  }
  return true
}

function writeListQuery() {
  if (applyingRoute) return
  const next = currentListQuery()
  storeBankListQuery(next)
  if (sameQuery(next, normalizeBankListQuery(route?.query))) return
  // A superseded replace never echoes; bound the set so it cannot grow forever.
  if (pendingWrites.size > 20) pendingWrites.clear()
  pendingWrites.add(queryKey(next))
  router.replace({ query: next })
}

function applyRouteQuery(raw) {
  const next = normalizeBankListQuery(raw)
  const key = queryKey(next)
  // An echo repeats the state the refs already hold. Anything else — including
  // a Back/Forward to a state written earlier — must be applied.
  if (pendingWrites.has(key) && sameQuery(next, currentListQuery())) {
    pendingWrites.delete(key)
    return
  }
  pendingWrites.clear()
  const nextRecycle = next.view === 'recycle'
  const viewChanged = nextRecycle !== showRecycle.value
  applyingRoute = true
  query.value = next.q || ''
  sortKey.value = next.sort || 'recent'
  showRecycle.value = nextRecycle
  category.value = next.category || ''
  applyingRoute = false
  storeBankListQuery(currentListQuery())
  if (viewChanged) {
    clearSelection()
    openMenuId.value = ''
    load()
  }
}

async function load() {
  loading.value = true
  clearPageError()
  try {
    const res = await listBanks(props.token, { deleted: showRecycle.value })
    const list = Array.isArray(res) ? res : (res?.banks || [])
    banks.value = list
    if (!showRecycle.value) activeBanks.value = list
    // A filter naming a category the loaded rows no longer carry would hide
    // everything (and, in recycle, an option that is not in the select at all).
    // Fall back to "all categories" instead of keeping a dead filter.
    if (category.value && !list.some(b => (b.category || '') === category.value)) {
      category.value = ''
    }
    // Batch actions must never reach rows that are no longer in the list.
    if (selectedIds.value.size) {
      const visible = new Set(banks.value.map(b => b.id))
      const pruned = [...selectedIds.value].filter(id => visible.has(id))
      if (pruned.length !== selectedIds.value.size) selectedIds.value = new Set(pruned)
    }
  } catch (err) {
    banks.value = []
    showPageError(err.detail || err.message)
  } finally {
    loading.value = false
  }
}

function setView(recycle) {
  if (showRecycle.value === recycle) return
  showRecycle.value = recycle
  // Keep the category filter across views; load() resets it only when the
  // loaded rows do not contain that category.
  clearSelection()
  openMenuId.value = ''
  load()
}

function toggleMenu(bankId) {
  openMenuId.value = openMenuId.value === bankId ? '' : bankId
}

function closeMenu() {
  openMenuId.value = ''
}

function closeMenuAndRestore(event) {
  const trigger = event.currentTarget?.querySelector('.bank-menu-trigger')
  closeMenu()
  trigger?.focus()
}

function toggleBankSelection(bankId) {
  const next = new Set(selectedIds.value)
  if (next.has(bankId)) next.delete(bankId)
  else next.add(bankId)
  selectedIds.value = next
}

function clearSelection() {
  selectedIds.value = new Set()
}

async function runBatch(operation) {
  if (!selectedIds.value.size) return
  if (!batchAllAdmin.value) return
  if (operation === 'archive'
    && !window.confirm(t('ep.banks.batch_archive_confirm', { count: selectedIds.value.size }))) {
    return
  }
  batchBusy.value = true
  clearPageError()
  try {
    await batchBanks(props.token, {
      bank_ids: [...selectedIds.value],
      operation,
      ...(operation === 'set_category' ? { category: batchCategory.value } : {}),
    })
    clearSelection()
    batchCategory.value = ''
    await load()
    flash(operation === 'archive' ? t('ep.manage.audit_bank_deleted') : t('ep.banks.saved'))
  } catch (err) {
    showPageError(err.detail || err.message, () => runBatch(operation))
  } finally {
    batchBusy.value = false
  }
}

function openCreate() {
  form.value = { name: '', description: '', category: '' }
  createError.value = ''
  showCreate.value = true
}

function requestCloseCreate() {
  confirmDiscard('create')
}

function clearFilters() {
  query.value = ''
  category.value = ''
}

async function createBank() {
  if (!form.value.name) return
  creating.value = true
  createError.value = ''
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
    }
    // A blank category means "backend default"; never persist a localized label.
    if (form.value.category) payload.category = form.value.category
    const created = await createBankApi(props.token, payload)
    triggerSyncEvent('BANK_CREATED', 'BANK', created.id, { name: created.name })
    showCreate.value = false
    await load()
    router.push(`/banks/${created.id}`)
  } catch (err) {
    createError.value = err.detail || err.message
  } finally {
    creating.value = false
  }
}

function openEdit(bank) {
  closeMenu()
  if (!isAdmin(bank)) return
  editBankId.value = bank.id
  editForm.value = { name: bank.name || '', category: bank.category || '', description: bank.description || '' }
  editBaseline.value = JSON.stringify(editForm.value)
  editError.value = ''
  showEdit.value = true
}

function requestCloseEdit() {
  confirmDiscard('edit')
}

async function saveBankMeta() {
  if (!editForm.value.name) return
  editSaving.value = true
  editError.value = ''
  try {
    const payload = {
      name: editForm.value.name,
      description: editForm.value.description,
    }
    // Blank keeps the existing category on the server.
    if (editForm.value.category) payload.category = editForm.value.category
    await updateBank(props.token, editBankId.value, payload)
    showEdit.value = false
    await load()
    flash(t('ep.banks.saved'))
  } catch (err) {
    editError.value = err.detail || err.message
  } finally {
    editSaving.value = false
  }
}

async function archiveBank(bank) {
  closeMenu()
  if (!isAdmin(bank)) return
  if (!window.confirm(t('ep.banks.archive_confirm', { name: bank.name }))) return
  clearPageError()
  try {
    await deleteBank(props.token, bank.id)
    await load()
    flash(t('ep.manage.audit_bank_deleted'))
  } catch (err) {
    showPageError(err.detail || err.message, () => archiveBank(bank))
  }
}

async function restoreBankRow(bank) {
  closeMenu()
  clearPageError()
  try {
    await restoreBank(props.token, bank.id)
    await load()
    flash(t('ep.banks.restore_done', { name: bank.name }))
  } catch (err) {
    showPageError(err.detail || err.message, () => restoreBankRow(bank))
  }
}

async function exportBankFile(bank, format) {
  closeMenu()
  clearPageError()
  try {
    await downloadBankExport(props.token, bank.id, format)
  } catch (err) {
    showPageError(err.detail || err.message)
  }
}

async function refreshCategoryRows() {
  categoryError.value = ''
  try {
    const res = await listBankCategories(props.token)
    categoryRows.value = (Array.isArray(res) ? res : []).map(row => ({ ...row, draft: row.name }))
  } catch (err) {
    categoryRows.value = categories.value.map(name => ({ name, count: 0, draft: name }))
    categoryError.value = err.detail || err.message
  }
}

function openCategoryManager() {
  if (!hasAdminBank.value) return
  showCategories.value = true
  refreshCategoryRows()
}

async function renameCategory(row) {
  if (!row.draft || row.draft === row.name) return
  categoryError.value = ''
  const oldName = row.name
  const newName = row.draft
  try {
    await renameBankCategory(props.token, oldName, newName)
    if (category.value === oldName) category.value = newName
    await load()
    await refreshCategoryRows()
    flash(t('ep.banks.saved'))
  } catch (err) {
    categoryError.value = err.detail || err.message
  }
}

async function removeCategory(row) {
  if (!window.confirm(t('ep.banks.category_delete_confirm', { name: row.name }))) return
  categoryError.value = ''
  try {
    await deleteBankCategory(props.token, row.name)
    if (category.value === row.name) category.value = ''
    await load()
    await refreshCategoryRows()
    flash(t('ep.banks.saved'))
  } catch (err) {
    categoryError.value = err.detail || err.message
  }
}

async function startPractice(bank) {
  if (startingId.value) return
  startingId.value = bank.id
  clearPageError()
  try {
    const session = await startSession(props.token, { bank_id: bank.id, mode: 'PRACTICE' })
    router.push(`/practice/${session.id}`)
  } catch (err) {
    showPageError(t('ep.banks.practice_start_failed', { message: err.detail || err.message }))
  } finally {
    startingId.value = ''
  }
}

function onDocumentClick() {
  closeMenu()
}

// Every list-state change is mirrored into the URL and sessionStorage.
watch([query, category, sortKey, showRecycle], writeListQuery)

// Back/Forward restores the view from the URL.
watch(() => route?.query, (value) => {
  applyRouteQuery(value)
}, { deep: true })

// Selection only drops rows a filter change hides; rows still visible stay
// selected, so refining a search does not throw away a multi-bank batch.
function pruneSelectionToVisible() {
  if (!selectedIds.value.size) return
  const visible = new Set(filteredBanks.value.map(b => b.id))
  const next = new Set([...selectedIds.value].filter(id => visible.has(id)))
  if (next.size !== selectedIds.value.size) selectedIds.value = next
}

watch([query, category], pruneSelectionToVisible)

onMounted(() => {
  writeListQuery()
  load()
  document.addEventListener('click', onDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style scoped>
.banks-page { padding-top: 0; }
.banks-toolbar { flex-wrap: wrap; }
.toolbar-field { display: inline-flex; align-items: center; gap: 6px; flex: none; }
.toolbar-field-label { font-size: 12px; color: var(--muted); white-space: nowrap; }
.banks-view-switch {
  display: inline-flex;
  align-items: stretch;
  flex: none;
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  overflow: hidden;
}
.banks-view-switch .btn { border: 0; border-radius: 0; }
.banks-view-switch .btn + .btn { border-left: 1px solid var(--line-strong); }
.banks-view-switch .btn.is-on { background: var(--brand); color: var(--brand-contrast); }
.banks-row {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) 88px auto;
  gap: 16px;
  align-items: center;
  transition: background .12s var(--ease);
}
.banks-row.recycle-row { grid-template-columns: minmax(0, 1fr) 88px auto; }
.banks-row:focus-within { background: var(--surface-2); }
@media (hover: hover) {
  .banks-row:hover { background: var(--surface-2); }
}
.bank-select-cell {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 32px; cursor: pointer;
}
.bank-select-cell input { width: 15px; height: 15px; cursor: pointer; }
.bank-open {
  display: flex; align-items: center; min-width: 0; width: 100%;
  padding: 0; border: 0; background: none; color: inherit;
  text-align: left; cursor: pointer;
}
.bank-open > .od-stack { flex: 1 1 auto; min-width: 0; }
.bank-open:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.bank-static { display: flex; align-items: center; min-width: 0; }
.bank-static > .od-stack { flex: 1 1 auto; min-width: 0; }
.practice-notice, .recycle-notice { margin-top: 16px; }
.practice-notice-text { flex: 1 1 auto; min-width: 0; }
.practice-notice-actions { margin-left: auto; flex: none; display: inline-flex; align-items: center; gap: 4px; }
.practice-notice-actions .btn { height: 24px; }
.recycle-notice .btn { margin-left: auto; flex: none; }
.bank-manage-locked { display: inline-flex; }
.bank-name { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
.bank-name-text {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.bank-name .tag { flex: none; }
.bank-meta { display: flex; flex-wrap: wrap; gap: 6px 12px; min-width: 0; }
.bank-meta .od-truncate { max-width: min(420px, 100%); }
.bank-count { display: flex; align-items: baseline; gap: 5px; justify-content: flex-end; }
.bank-count strong { font-family: var(--font-mono); font-size: 17px; font-weight: 500; }
.bank-count span { font-size: 12px; color: var(--ink-3); }
.bank-action-cluster {
  display: flex; align-items: center; justify-content: flex-end;
  gap: 8px; justify-self: end; min-width: 0;
}
.bank-actions-cell { display: flex; align-items: center; gap: 8px; color: var(--ink-4); flex-wrap: nowrap; }
.bank-menu-wrap { position: relative; display: flex; justify-content: flex-end; flex: none; }
.bank-menu-trigger { color: var(--ink-3); }
.bank-menu-trigger:hover,
.bank-menu-trigger[aria-expanded="true"] { color: var(--ink); background: var(--surface-2); }
.bank-menu-pop {
  position: absolute; right: 0; top: calc(100% + 4px); z-index: 20;
  min-width: 168px; padding: 6px 0;
  border: 1px solid var(--line-strong); background: var(--surface);
  box-shadow: none;
}
.bank-menu-item {
  display: block; width: 100%; padding: 8px 14px;
  border: 0; background: none; color: var(--ink-2);
  font-size: 12.5px; text-align: left; cursor: pointer;
}
.bank-menu-item:hover { background: var(--surface-2); color: var(--ink); }
.bank-menu-item:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
.bank-menu-item:disabled { color: var(--ink-4); cursor: not-allowed; }
.bank-menu-item:disabled:hover { background: none; color: var(--ink-4); }
.bank-menu-item.danger { color: var(--bad); }
.bank-menu-item.danger:disabled { color: var(--ink-4); }
.bank-batch-bar { margin-top: 16px; }
.batch-bar {
  display: flex; flex-direction: column; gap: 10px;
  padding: 12px 14px; border: 1px solid var(--line-strong); background: var(--surface-2);
}
.batch-bar-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.batch-title { font-size: 12.5px; font-weight: 600; color: var(--ink); }
.batch-controls { display: flex; align-items: center; gap: 10px 16px; flex-wrap: wrap; }
.batch-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.batch-group .input { width: 190px; max-width: 100%; }
.category-list { display: flex; flex-direction: column; gap: 8px; }
.category-row { display: grid; grid-template-columns: minmax(0, 1fr) 40px auto auto; gap: 8px; align-items: center; margin: 0; }
.category-row .small { text-align: right; }
.small { font-size: 12px; }
@media (max-width: 900px) {
  .banks-row { grid-template-columns: 20px minmax(0, 1fr) auto; gap: 12px; }
  .banks-row.recycle-row { grid-template-columns: minmax(0, 1fr) auto; }
  .bank-count { display: none; }
}
@media (max-width: 640px) {
  .banks-page { overflow-x: hidden; }
  .page-head .page-actions { width: 100%; flex-wrap: wrap; }
  .page-head .page-actions .btn { flex: 1 1 auto; justify-content: center; }
  .banks-toolbar { gap: 8px; }
  .banks-toolbar .search-box { flex: 1 1 100%; min-width: 0; max-width: none; }
  .banks-toolbar .select { flex: 1 1 128px; min-width: 0; }
  .banks-toolbar .toolbar-field { flex: 1 1 150px; min-width: 0; }
  .banks-toolbar .toolbar-field .select { flex: 1 1 auto; width: 100%; }
  .banks-toolbar .toolbar-field-label { flex: none; }
  .banks-toolbar .btn { flex: 1 1 auto; min-height: 32px; }
  .banks-toolbar .input,
  .banks-toolbar .select { min-height: 34px; }
  .banks-toolbar .spacer { display: none; }
  .banks-toolbar > .small { margin-left: auto; }
  .banks-view-switch { display: flex; flex: 1 1 100%; width: 100%; }
  .banks-view-switch .btn { flex: 1 1 0; min-width: 0; }
  .banks-row {
    grid-template-columns: 32px minmax(0, 1fr);
    gap: 8px 12px;
    align-items: start;
    padding: 8px 0 6px;
  }
  .banks-row.recycle-row { grid-template-columns: minmax(0, 1fr); }
  .bank-select-cell { width: 32px; height: 32px; justify-content: flex-start; }
  .bank-select-cell input { width: 18px; height: 18px; }
  .bank-action-cluster {
    grid-column: 1 / -1;
    grid-row: 2;
    width: 100%;
    justify-self: stretch;
    padding-top: 8px;
    border-top: 1px solid var(--line);
  }
  .bank-actions-cell .btn { min-height: 32px; }
  .bank-batch-bar .btn { min-height: 32px; }
  .bank-menu-trigger { width: 32px; height: 32px; }
  .bank-menu-item { min-height: 40px; padding-top: 10px; padding-bottom: 10px; }
  .bank-meta .od-truncate { max-width: 100%; }
  .category-row { grid-template-columns: minmax(0, 1fr) 32px; }
  .category-row .btn { grid-column: span 1; min-height: 32px; }
}
</style>
