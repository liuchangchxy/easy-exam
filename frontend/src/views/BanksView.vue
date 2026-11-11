<template>
  <div class="banks-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.brand.sub') }}</div>
        <h1 class="page-title">{{ t('ep.banks.title') }}</h1>
        <p class="page-sub">{{ t('ep.banks.sub', { count: banks.length }) }}</p>
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

    <div class="toolbar">
      <div class="search-box">
        <LinearIcon name="search" :size="15" />
        <input v-model.trim="query" class="input" :placeholder="t('ep.banks.search')" />
      </div>
      <select v-model="category" class="select">
        <option value="">{{ t('ep.common.all') }}</option>
        <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
      </select>
      <div class="spacer"></div>
      <span class="small dim">{{ t('ep.common.count', { count: filteredBanks.length }) }}</span>
    </div>

    <div v-if="loading" class="skeleton-rows">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </div>

    <div v-else-if="filteredBanks.length" class="bank-list">
      <div
        v-for="bank in filteredBanks"
        :key="bank.id"
        class="banks-row"
        role="button"
        tabindex="0"
        @click="router.push(`/banks/${bank.id}`)"
        @keydown.enter.prevent="router.push(`/banks/${bank.id}`)"
        @keydown.space.prevent="router.push(`/banks/${bank.id}`)"
      >
        <span class="od-stack" style="--od-gap:2px;text-align:left;min-width:0">
          <span class="bank-name">
            {{ bank.name }}
            <span class="tag">{{ roleLabel(bank.role) }}</span>
            <span v-if="bank.has_active_exam" class="tag warn" :title="t('ep.manage.locked_desc')">{{ t('ep.today.active_badge') }}</span>
          </span>
          <span class="bank-meta">
            <span>{{ bank.category || t('ep.nav.banks') }}</span>
            <span v-if="bank.description" class="od-truncate">{{ bank.description }}</span>
          </span>
        </span>
        <span class="bank-count">
          <strong>{{ bank.question_count || 0 }}</strong>
          <span>{{ t('ui.k0101') }}</span>
        </span>
        <span class="bank-actions-cell">
          <button type="button" class="btn btn-sm" @click.stop="startPractice(bank)">{{ t('ep.banks.practice') }}</button>
          <button
            type="button"
            class="btn btn-sm btn-quiet"
            :title="bank.has_active_exam ? t('ep.manage.locked_desc') : ''"
            @click.stop="router.push(`/banks/${bank.id}/manage`)"
          >{{ t('ep.banks.manage') }}</button>
          <span class="bank-go"><LinearIcon name="chevron-right" :size="16" /></span>
        </span>
      </div>
    </div>

    <div v-else class="empty">
      <div class="empty-title">{{ t('ep.banks.empty') }}</div>
      <div class="empty-desc">{{ t('ep.banks.empty_hint') }}</div>
      <div class="empty-actions">
        <button type="button" class="btn btn-primary" @click="openCreate">{{ t('ep.today.create_bank') }}</button>
        <button type="button" class="btn" @click="router.push('/import')">{{ t('ep.common.import') }}</button>
      </div>
    </div>

    <div v-if="showCreate" class="exam-setup-backdrop" @click.self="showCreate = false" @keydown.esc="showCreate = false">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" @submit.prevent="createBank">
        <h2>{{ t('ep.today.create_bank') }}</h2>
        <label>{{ t('home.bank_name') }}
          <input v-model.trim="form.name" type="text" :placeholder="t('home.bank_name_placeholder')" required />
        </label>
        <label>{{ t('home.category') }}
          <input v-model.trim="form.category" type="text" :placeholder="t('home.category_placeholder')" />
        </label>
        <label>{{ t('home.description') }}
          <textarea v-model.trim="form.description" :placeholder="t('home.description_placeholder')" rows="3"></textarea>
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showCreate = false">{{ t('common.cancel') }}</button>
          <button type="submit" class="primary" :disabled="creating">{{ t('ep.today.create_bank') }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import { listBanks, createBank as createBankApi } from '../api/banks'
import { startSession } from '../api/practice'
import { triggerSyncEvent } from '../api/sync'

const props = defineProps({ token: { type: String, required: true } })
const router = useRouter()
const { t } = useLocale()

const banks = ref([])
const loading = ref(true)
const query = ref('')
const category = ref('')
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const form = ref({ name: '', description: '', category: '' })

const categories = computed(() => [...new Set(banks.value.map(b => b.category).filter(Boolean))])

const filteredBanks = computed(() => {
  let list = banks.value.slice()
  const q = query.value.trim().toLowerCase()
  if (q) list = list.filter(b => `${b.name} ${b.description || ''} ${b.category || ''}`.toLowerCase().includes(q))
  if (category.value) list = list.filter(b => b.category === category.value)
  return list
})

function roleLabel(role) {
  if (role === 'ADMIN') return t('ep.banks.owner')
  if (role === 'EDITOR') return t('ep.banks.editor')
  return t('ep.banks.member')
}

async function load() {
  loading.value = true
  try {
    const res = await listBanks(props.token)
    banks.value = Array.isArray(res) ? res : (res?.banks || [])
  } catch (_) {
    banks.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { name: '', description: '', category: '' }
  createError.value = ''
  showCreate.value = true
}

async function createBank() {
  if (!form.value.name) return
  creating.value = true
  createError.value = ''
  try {
    const created = await createBankApi(props.token, {
      name: form.value.name,
      description: form.value.description,
      category: form.value.category || t('ep.nav.banks'),
    })
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

async function startPractice(bank) {
  try {
    const session = await startSession(props.token, { bank_id: bank.id, mode: 'PRACTICE' })
    router.push(`/practice/${session.id}`)
  } catch (err) {
    createError.value = err.detail || err.message
  }
}

onMounted(load)
</script>

<style scoped>
.banks-page { padding-top: 0; }
.banks-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 88px auto 14px;
  gap: 20px;
  align-items: center;
  cursor: pointer;
}
.banks-row:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.bank-name { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
.bank-meta { display: flex; flex-wrap: wrap; gap: 6px 12px; min-width: 0; }
.bank-meta .od-truncate { max-width: min(420px, 100%); }
.bank-count { display: flex; align-items: baseline; gap: 5px; justify-content: flex-end; }
.bank-count strong { font-family: var(--font-mono); font-size: 17px; font-weight: 500; }
.bank-count span { font-size: 12px; color: var(--ink-3); }
.bank-go { display: flex; justify-content: flex-end; color: var(--ink-4); }
.bank-actions-cell { display: flex; align-items: center; gap: 8px; color: var(--ink-4); flex-wrap: wrap; }
.small { font-size: 12px; }
@media (max-width: 900px) {
  .banks-row { grid-template-columns: minmax(0, 1fr) auto 14px; gap: 14px; }
  .bank-count { display: none; }
}
@media (max-width: 640px) {
  .banks-page { overflow-x: hidden; }
  .page-head .page-actions { width: 100%; flex-wrap: wrap; }
  .page-head .page-actions .btn { flex: 1 1 auto; justify-content: center; }
  .toolbar { flex-wrap: wrap; }
  .toolbar .search-box { flex: 1 1 100%; min-width: 0; }
  .banks-row { grid-template-columns: minmax(0, 1fr) 14px; }
  .bank-actions-cell { grid-column: 1 / -1; grid-row: 2; width: 100%; justify-content: flex-end; }
  .bank-go { grid-column: 2; grid-row: 1; }
  .bank-meta .od-truncate { max-width: 100%; }
}
</style>
