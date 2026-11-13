<template>
  <div class="exam-center">
    <div class="page-head exam-center-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.nav.study') }}</div>
        <h1 class="page-title">{{ t('ep.exam.title') }}</h1>
        <p class="page-sub">{{ t('ep.exam.sub') }}</p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn" @click="openCreatePaper">
          <LinearIcon name="plus" :size="14" />{{ t('ep.exam.new_paper') }}
        </button>
        <span class="action-with-reason">
          <span v-if="!banks.length" class="action-reason">{{ t('ep.exam.start_requires_bank') }}</span>
          <button type="button" class="btn btn-primary" :disabled="!banks.length" @click="openSetup()">
            <LinearIcon name="play" :size="14" />{{ t('ep.exam.start') }}
          </button>
        </span>
      </div>
    </div>

    <div v-if="notice" class="notice bad" style="margin-top: 16px">
      <LinearIcon name="alert" :size="15" /><span>{{ notice }}</span>
    </div>

    <section v-if="activeSessions.length" class="active-exam panel">
      <div class="panel-head">
        <span class="panel-title">{{ t('ep.exam.active_title') }}</span>
        <span class="section-note">{{ t('ep.exam.active_desc') }}</span>
      </div>
      <div class="list">
        <div v-for="session in activeSessions" :key="session.id" class="list-row">
          <span class="list-main">
            <span class="list-title">{{ bankName(session.bank_id) }}</span>
            <span class="list-meta">
              <span>{{ t('ep.practice.progress', { current: session.answered_count || 0, total: session.total_questions || 0 }) }}</span>
              <span class="mono">{{ session.mode }}</span>
            </span>
          </span>
          <span class="list-side">
            <button type="button" class="btn btn-sm btn-primary" @click="$emit('resume-session', session)">
              {{ t('ep.exam.resume') }}
            </button>
            <button type="button" class="btn btn-sm btn-quiet" @click="abandon(session)">
              {{ t('ep.exam.abandon') }}
            </button>
          </span>
        </div>
      </div>
    </section>

    <div v-if="loading" class="skeleton-rows">
      <div class="skeleton"></div><div class="skeleton"></div>
    </div>

    <div v-else-if="loadError" class="notice bad exam-load-error" style="margin-top: 16px" role="alert">
      <LinearIcon name="alert" :size="15" />
      <span>{{ t('ep.common.load_failed') }}</span>
      <button type="button" class="btn btn-sm" @click="load">{{ t('ep.common.retry') }}</button>
    </div>

    <div v-else class="exam-layout exam-center-grid">
      <div class="exam-main">
        <section class="panel">
          <div class="panel-head">
            <span class="panel-title">{{ t('ep.exam.papers') }}</span>
            <span class="section-note">{{ t('ep.common.count', { count: profiles.length }) }}</span>
          </div>

          <div v-if="profiles.length" class="list">
            <div v-for="profile in profiles" :key="profile.id" class="list-row paper-row exam-paper-row">
              <span class="list-main exam-paper-main">
                <span class="list-title exam-paper-title">{{ profile.name }}</span>
                <span class="list-meta exam-paper-sub">
                  <span v-if="blueprintOf(profile)">{{ t('ep.exam.blueprint_sections', { count: blueprintOf(profile).sections?.length || 0 }) }}</span>
                  <span v-if="blueprintOf(profile)">{{ blueprintTotal(profile) }} {{ t('ep.practice.index') }}</span>
                  <span v-if="Number(blueprintOf(profile)?.negative_mark) > 0">{{ t('ep.exam.negative', { points: blueprintOf(profile).negative_mark }) }}</span>
                </span>
                <span v-if="profile.description" class="exam-paper-desc">{{ profile.description }}</span>
              </span>
              <span class="list-side">
                <button type="button" class="btn btn-sm btn-quiet" @click="openBlueprint(profile)">
                  {{ t('ep.exam.blueprint_edit') }}
                </button>
                <button type="button" class="btn btn-sm" :disabled="!banks.length" @click="openSetup(profile)">
                  {{ t('ep.exam.start') }}
                </button>
              </span>
            </div>
          </div>

          <div v-else class="empty" style="padding: 44px 0">
            <div class="empty-mark"><LinearIcon name="blueprint" :size="26" /></div>
            <div class="empty-title">{{ t('ep.exam.papers_empty') }}</div>
            <div class="empty-desc">{{ t('ep.exam.papers_empty_hint') }}</div>
            <div class="empty-actions">
              <button type="button" class="btn" @click="openCreatePaper">{{ t('ep.exam.new_paper') }}</button>
              <span class="action-with-reason">
                <span v-if="!banks.length" class="action-reason">{{ t('ep.exam.start_requires_bank') }}</span>
                <button type="button" class="btn btn-primary" :disabled="!banks.length" @click="openSetup()">{{ t('ep.exam.start') }}</button>
              </span>
            </div>
          </div>
        </section>

        <section class="panel" style="margin-top: 28px">
          <div class="panel-head">
            <span class="panel-title">{{ t('ep.exam.start_from_bank') }}</span>
            <span class="section-note">{{ t('ep.exam.start_hint') }}</span>
          </div>
          <div v-if="banks.length" class="list">
            <div v-for="bank in banks" :key="bank.id" class="list-row exam-bank-row">
              <span class="list-main">
                <span class="list-title exam-bank-title">{{ bank.name }}</span>
                <span class="list-meta">
                  <span>{{ t('ep.banks.questions', { count: bank.question_count || 0 }) }}</span>
                  <span v-if="bank.has_active_exam" class="tag warn">{{ t('ep.today.active_badge') }}</span>
                </span>
              </span>
              <span class="list-side">
                <button type="button" class="btn btn-sm" :disabled="!bank.question_count" @click="openSetup(null, bank)">
                  {{ t('ep.exam.start') }}
                </button>
              </span>
            </div>
          </div>
          <div v-else class="empty" style="padding: 30px 0">
            <div class="empty-desc">{{ t('ep.exam.no_banks') }}</div>
            <div class="empty-actions">
              <button type="button" class="btn" @click="router.push('/import')">{{ t('ep.common.import') }}</button>
            </div>
          </div>
        </section>
      </div>

      <aside class="exam-rail exam-center-rail">
        <div class="rail-block">
          <div class="rail-title">{{ t('ep.exam.blueprint') }}</div>
          <p class="rail-note">{{ t('ep.exam.profile_note') }}</p>
          <div v-if="profiles.length" class="rail-list">
            <button v-for="profile in profiles" :key="profile.id" type="button" class="rail-link" @click="openBlueprint(profile)">
              <span class="rail-link-title od-truncate">{{ profile.name }}</span>
              <span class="tiny mono">{{ blueprintTotal(profile) }}</span>
            </button>
          </div>
          <div v-else class="tiny dim">{{ t('ep.exam.papers_empty') }}</div>
        </div>
        <div class="rail-block">
          <div class="rail-title">{{ t('ep.exam.report') }}</div>
          <p class="rail-note">{{ t('ep.exam.scores_note') }}</p>
        </div>
      </aside>
    </div>

    <!-- Create paper -->
    <AppDialog
      :open="showCreate"
      :title="t('ep.exam.new_paper')"
      panel-class="exam-setup-dialog"
      style="--app-dialog-width: 520px"
      initial-focus="#paper-name"
      @close="showCreate = false"
    >
      <form class="exam-dialog-form" @submit.prevent="createPaper">
        <label>{{ t('ep.exam.paper_name') }}
          <input id="paper-name" v-model.trim="paperForm.name" type="text" :placeholder="t('ep.exam.paper_name_placeholder')" required />
        </label>
        <label>{{ t('ep.exam.paper_desc') }}
          <input v-model.trim="paperForm.description" type="text" :placeholder="t('ep.exam.paper_desc_placeholder')" />
        </label>
        <div class="bank-actions">
          <button type="button" @click="showCreate = false">{{ t('ep.common.cancel') }}</button>
          <button type="submit" class="primary" :disabled="creating || !paperForm.name">{{ t('ep.exam.create_paper') }}</button>
        </div>
      </form>
    </AppDialog>

    <!-- Start exam -->
    <AppDialog
      :open="showSetup"
      :title="t('ep.exam.setup')"
      panel-class="exam-setup-dialog"
      style="--app-dialog-width: 520px"
      initial-focus="#setup-bank"
      @close="showSetup = false"
    >
      <form class="exam-dialog-form" @submit.prevent="beginExam">
        <label>{{ t('ep.exam.bank_pick') }}
          <select id="setup-bank" v-model="setup.bankId" @change="onSetupBankChange">
            <option v-for="bank in examBanks" :key="bank.id" :value="bank.id">{{ bank.name }} · {{ t('ep.banks.questions', { count: bank.question_count || 0 }) }}</option>
          </select>
        </label>
        <label>{{ t('ep.exam.profile_pick') }}
          <select id="setup-profile" v-model="setup.profileId" @change="onSetupProfileChange">
            <option value="">{{ t('ep.exam.direct') }}</option>
            <option v-for="profile in blueprintProfiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
          </select>
        </label>
        <p class="hint">{{ t('ep.exam.profile_note') }}</p>
        <label>{{ t('ep.exam.questions') }}
          <input id="setup-total" v-model.number="setup.total" type="number" min="1" :max="setupMax" />
        </label>
        <label>{{ t('ep.exam.time') }}
          <input id="setup-minutes" v-model.number="setup.minutes" type="number" min="1" max="600" />
        </label>
        <label class="setup-check">
          <input v-model="setup.recordMistakes" type="checkbox" />
          <span>{{ t('ep.exam.record_mistakes') }}</span>
        </label>
        <p v-if="setupError" class="error">{{ setupError }}</p>
        <p class="hint">{{ t('ep.exam.start_hint') }}</p>
        <div class="bank-actions">
          <button type="button" @click="showSetup = false">{{ t('ep.common.cancel') }}</button>
          <button type="submit" class="primary" :disabled="starting || !setupValid">{{ t('ep.exam.start') }}</button>
        </div>
      </form>
    </AppDialog>

    <!-- Blueprint editor -->
    <AppDialog
      :open="Boolean(editingProfile)"
      :title="t('ep.exam.blueprint')"
      panel-class="drawer exam-blueprint-dialog"
      style="--app-dialog-width: 720px"
      initial-focus="#bp-negative"
      @close="requestBlueprintClose"
    >
      <template #head>
        <div class="drawer-heading">
          <div class="drawer-title">{{ t('ep.exam.blueprint') }}</div>
          <div class="drawer-sub">{{ editingProfile?.name }} · v{{ editingProfile?.latest_blueprint?.version_number || 0 }}</div>
        </div>
      </template>
      <div class="drawer-body">
        <div class="bp-total">
          <div class="stat">
            <div class="stat-num">{{ bpTotal }}<span class="unit">{{ t('ep.practice.index') }}</span></div>
            <div class="stat-cap">{{ t('ep.exam.blueprint_total') }}</div>
          </div>
          <label class="field bp-negative">
            <span class="label">{{ t('ep.exam.blueprint_negative') }}</span>
            <input id="bp-negative" v-model.number="bpForm.negative_mark" class="input" type="number" min="0" max="5" step="0.5" />
          </label>
        </div>

        <div class="rule-label" style="margin: 20px 0 8px">{{ t('ep.exam.blueprint_chapters') }}</div>
        <div v-if="bpForm.sections.length" class="bp-sections">
          <div v-for="(section, idx) in bpForm.sections" :key="idx" class="bp-section">
            <select v-model="section.type" class="select">
              <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
              <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
              <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
              <option value="ESSAY">{{ t('ep.question_types.essay') }}</option>
            </select>
            <input v-model.number="section.count" class="input bp-count" type="number" min="0" :aria-label="t('ep.exam.section_count')" />
            <select v-model="section.difficulty" class="select">
              <option :value="null">{{ t('ep.exam.section_any') }}</option>
              <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <button type="button" class="btn btn-sm btn-quiet" @click="removeSection(idx)">{{ t('ep.common.delete') }}</button>
          </div>
        </div>
        <div v-else class="empty" style="padding: 22px 0">
          <div class="empty-desc">{{ t('ep.exam.blueprint_empty') }}</div>
        </div>
        <button type="button" class="btn btn-sm" style="margin-top: 10px" @click="addSection">
          <LinearIcon name="plus" :size="13" />{{ t('ep.exam.add_section') }}
        </button>

        <p v-if="bpError" class="error" style="margin-top: 12px">{{ bpError }}</p>
        <div class="notice info" style="margin-top: 20px">
          <LinearIcon name="info" :size="15" />
          <span>{{ t('ep.exam.profile_note') }}</span>
        </div>
      </div>
      <template #foot>
        <div class="drawer-foot">
          <button type="button" class="btn btn-primary" :disabled="savingBp || !bpLoaded" @click="saveBp">
            {{ savingBp ? t('ep.common.loading') : t('ep.exam.blueprint_save') }}
          </button>
          <span class="spacer"></span>
          <button type="button" class="btn btn-quiet" @click="requestBlueprintClose">{{ t('ep.common.cancel') }}</button>
        </div>
      </template>
    </AppDialog>

    <AppDialog
      :open="blueprintDiscardOpen"
      :title="t('ep.common.unsaved_title')"
      panel-class="discard-prompt-dialog"
      style="--app-dialog-width: 420px"
      initial-focus=".discard-save"
      @close="cancelBlueprintDiscard"
    >
      <p class="hint">{{ t('ep.common.unsaved_desc') }}</p>
      <template #foot>
        <button type="button" class="btn btn-quiet" @click="cancelBlueprintDiscard">{{ t('ep.common.cancel') }}</button>
        <button type="button" class="btn discard-discard" @click="discardBlueprint">{{ t('ep.common.discard') }}</button>
        <button type="button" class="btn btn-primary discard-save" :disabled="savingBp || !bpLoaded" @click="saveFromBlueprintPrompt">
          {{ t('common.save') }}
        </button>
      </template>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppDialog from '../components/AppDialog.vue'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import { useDirtyGuard } from '../composables/useDirtyGuard.js'
import { listBanks } from '../api/banks'
import { listProfiles, createProfile, getBlueprint, saveBlueprint, startExam } from '../api/exams'
import { listActiveSessions, abandonSession } from '../api/practice'

const props = defineProps({ token: { type: String, required: true } })
const emit = defineEmits(['mock-exam', 'resume-session'])
const router = useRouter()
const { t } = useLocale()

const banks = ref([])
const profiles = ref([])
const activeSessions = ref([])
const loading = ref(true)
const loadError = ref(false)
const notice = ref('')

const showCreate = ref(false)
const creating = ref(false)
const paperForm = ref({ name: '', description: '' })

const showSetup = ref(false)
const starting = ref(false)
const setupError = ref('')
const setup = ref({ bankId: '', profileId: '', total: 50, minutes: 120, recordMistakes: true })

const editingProfile = ref(null)
const bpForm = ref({ negative_mark: 0, sections: [] })
const bpMeta = ref({})
const bpError = ref('')
const bpLoaded = ref(false)
const savingBp = ref(false)
const bpBaseline = ref('')

const examBanks = computed(() => banks.value.filter(b => (b.question_count || 0) > 0))
const difficultyOptions = computed(() => [1, 2, 3, 4, 5].map(value => ({ value, label: t('ep.difficulty.' + value) })))
const blueprintProfiles = computed(() => profiles.value.filter(p => blueprintOf(p)))
const setupBank = computed(() => examBanks.value.find(b => b.id === setup.value.bankId))
const setupMax = computed(() => {
  const bankMax = setupBank.value?.question_count || 1
  const bp = setup.value.profileId ? blueprintOf(profiles.value.find(p => p.id === setup.value.profileId)) : null
  const bpMax = bp ? blueprintTotalValue(bp) : 0
  return bpMax > 0 ? Math.min(bankMax, bpMax) : bankMax
})
const setupValid = computed(() => {
  const n = Number(setup.value.total)
  const minutes = Number(setup.value.minutes)
  return !!setup.value.bankId
    && Number.isInteger(n) && n >= 1 && n <= setupMax.value
    && Number.isInteger(minutes) && minutes >= 1 && minutes <= 600
})

const bpTotal = computed(() => bpForm.value.sections.reduce((sum, s) => sum + (Number(s.count) || 0), 0))

function blueprintSnapshot() {
  return JSON.stringify({
    negative_mark: Number(bpForm.value.negative_mark) || 0,
    sections: bpForm.value.sections.map(section => ({
      name: section.name || '',
      type: section.type || 'SINGLE',
      count: Number(section.count) || 0,
      difficulty: section.difficulty ?? null,
      chapter_id: section.chapter_id || '',
      tags: section.tags || '',
    })),
  })
}

const blueprintDirty = computed(() => Boolean(bpBaseline.value) && blueprintSnapshot() !== bpBaseline.value)

const {
  confirmDiscard: confirmBlueprintDiscard,
  discardPromptOpen: blueprintDiscardOpen,
  confirmDiscardAccept: discardBlueprint,
  confirmDiscardCancel: cancelBlueprintDiscard,
} = useDirtyGuard(() => blueprintDirty.value, closeBlueprintNow)

function blueprintOf(profile) {
  const bp = profile?.latest_blueprint?.blueprint
  if (!bp) return null
  if (!Array.isArray(bp.sections) || !bp.sections.length) return null
  return bp
}

function blueprintTotalValue(bp) {
  return (bp?.sections || []).reduce((sum, s) => sum + (Number(s.count) || 0), 0)
}

function blueprintTotal(profile) {
  return blueprintTotalValue(blueprintOf(profile))
}

function bankName(id) {
  return banks.value.find(b => b.id === id)?.name || t('ep.common.none')
}

async function load() {
  loading.value = true
  loadError.value = false
  notice.value = ''
  const results = await Promise.allSettled([
    listBanks(props.token),
    listProfiles(props.token),
    listActiveSessions(props.token, 'EXAM'),
  ])
  const [bankRes, profileRes, sessionRes] = results
  loadError.value = results.some(result => result.status === 'rejected')
  banks.value = bankRes.status === 'fulfilled' ? (bankRes.value || []) : []
  profiles.value = profileRes.status === 'fulfilled' ? (profileRes.value || []) : []
  activeSessions.value = sessionRes.status === 'fulfilled' ? (sessionRes.value || []) : []
  loading.value = false
}

function openCreatePaper() {
  paperForm.value = { name: '', description: '' }
  showCreate.value = true
}

async function createPaper() {
  if (!paperForm.value.name) return
  creating.value = true
  notice.value = ''
  try {
    const profile = await createProfile(props.token, {
      name: paperForm.value.name,
      description: paperForm.value.description,
    })
    profiles.value.unshift(profile)
    showCreate.value = false
    openBlueprint(profile)
  } catch (err) {
    notice.value = err.detail || err.message
  } finally {
    creating.value = false
  }
}

function openSetup(profile = null, bank = null) {
  const firstBank = bank || examBanks.value[0]
  setup.value = {
    bankId: firstBank?.id || '',
    profileId: profile?.id || '',
    total: firstBank?.question_count || 50,
    minutes: 120,
    recordMistakes: true,
  }
  setupError.value = ''
  onSetupProfileChange()
  showSetup.value = true
}

function onSetupBankChange() {
  const bank = setupBank.value
  if (bank) {
    const requested = Number(setup.value.total) || bank.question_count
    setup.value.total = Math.min(requested, bank.question_count, setupMax.value)
  }
  setupError.value = ''
}

function onSetupProfileChange() {
  const profile = profiles.value.find(p => p.id === setup.value.profileId)
  const bp = blueprintOf(profile)
  if (bp) setup.value.total = Math.min(blueprintTotalValue(bp), setupBank.value?.question_count || blueprintTotalValue(bp))
  setupError.value = ''
}

async function beginExam() {
  if (!setupValid.value) {
    const minutes = Number(setup.value.minutes)
    setupError.value = Number.isInteger(minutes) && minutes >= 1 && minutes <= 600
      ? t('ep.exam.invalid_count', { max: setupMax.value })
      : t('ep.exam.invalid_time')
    return
  }
  starting.value = true
  setupError.value = ''
  try {
    const session = await startExam(props.token, {
      bank_id: setup.value.bankId,
      total_questions: Number(setup.value.total),
      time_limit: Number(setup.value.minutes),
      profile_id: setup.value.profileId || undefined,
      record_mistakes: setup.value.recordMistakes,
    })
    showSetup.value = false
    emit('mock-exam', session)
  } catch (err) {
    setupError.value = err.detail || err.message
  } finally {
    starting.value = false
  }
}

async function abandon(session) {
  if (!window.confirm(t('ep.exam.abandon_confirm'))) return
  try {
    await abandonSession(props.token, session.id)
    activeSessions.value = activeSessions.value.filter(s => s.id !== session.id)
  } catch (err) {
    notice.value = err.detail || err.message
  }
}

async function openBlueprint(profile) {
  bpError.value = ''
  bpLoaded.value = false
  bpBaseline.value = ''
  bpMeta.value = {}
  bpForm.value = { negative_mark: 0, sections: [] }
  try {
    const bp = await getBlueprint(props.token, profile.id)
    const data = bp?.blueprint || {}
    bpMeta.value = blueprintMetaOf(data)
    bpForm.value = { negative_mark: Number(data.negative_mark) || 0, sections: blueprintSections(data) }
    bpLoaded.value = true
    bpBaseline.value = blueprintSnapshot()
  } catch (err) {
    if (err?.status === 404) {
      // A profile without a saved blueprint legitimately starts from empty.
      bpForm.value = { negative_mark: 0, sections: [] }
      bpLoaded.value = true
      bpBaseline.value = blueprintSnapshot()
    } else {
      bpError.value = `${t('ui.k0288')}${err.detail || err.message}`
    }
  }
  // Open only once the draft is populated so the dialog mounts with its data
  // and the initial focus target is not re-rendered straight after focusing.
  editingProfile.value = profile
}

function blueprintMetaOf(blueprint) {
  const { sections: _sections, negative_mark: _negative, ...meta } = blueprint || {}
  return meta
}

function blueprintSections(blueprint) {
  return (blueprint?.sections || []).map(section => ({
    ...section,
    name: section.name || '',
    type: section.type || 'SINGLE',
    count: Number(section.count) || 0,
    difficulty: section.difficulty ?? null,
    chapter_id: section.chapter_id || '',
    tags: section.tags || '',
  }))
}

function addSection() {
  bpForm.value.sections.push({ name: '', type: 'SINGLE', count: 10, difficulty: null, chapter_id: '', tags: '' })
}

function removeSection(idx) {
  bpForm.value.sections.splice(idx, 1)
}

function typeName(type) {
  const key = String(type || '').toLowerCase()
  return t('ep.question_types.' + (['single', 'multi', 'judge', 'essay'].includes(key) ? key : 'single'))
}

async function saveBp() {
  if (!editingProfile.value || !bpLoaded.value) return
  if (bpTotal.value <= 0) {
    bpError.value = t('ep.exam.blueprint_invalid')
    return
  }
  savingBp.value = true
  bpError.value = ''
  try {
    await saveBlueprint(props.token, editingProfile.value.id, {
      ...bpMeta.value,
      negative_mark: Number(bpForm.value.negative_mark) || 0,
      sections: bpForm.value.sections.map(s => ({
        ...s,
        name: String(s.name || '').trim() || typeName(s.type),
        type: s.type,
        count: Number(s.count) || 0,
        difficulty: s.difficulty ?? null,
        chapter_id: s.chapter_id || '',
        tags: s.tags || '',
      })),
    })
    bpBaseline.value = blueprintSnapshot()
    profiles.value = await listProfiles(props.token)
    const fresh = profiles.value.find(p => p.id === editingProfile.value.id)
    if (fresh) editingProfile.value = fresh
  } catch (err) {
    bpError.value = err.detail || err.message
  } finally {
    savingBp.value = false
  }
}

function closeBlueprintNow() {
  editingProfile.value = null
  bpError.value = ''
  bpBaseline.value = ''
}

function requestBlueprintClose() {
  if (savingBp.value) return
  confirmBlueprintDiscard()
}

function saveFromBlueprintPrompt() {
  cancelBlueprintDiscard()
  saveBp()
}

onMounted(load)
</script>

<style scoped>
.exam-center { padding-top: 26px; }
.exam-center-head { padding-bottom: 18px; }
.active-exam { margin-top: 20px; }
.exam-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 48px;
  margin: 26px 0 0;
  padding: 0;
  max-width: none;
  align-items: start;
}
.exam-main { min-width: 0; max-width: none; }
.exam-rail {
  border-top: 0;
  border-left: 1px solid var(--line);
  padding: 4px 0 0 22px;
}
.rail-block + .rail-block {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
}
.rail-title {
  font-size: 12px;
  font-weight: 650;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.rail-note { margin: 8px 0 12px; font-size: 12px; line-height: 1.75; color: var(--ink-3); }
.rail-list { display: flex; flex-direction: column; }
.rail-link {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 0;
  border: 0;
  border-top: 1px solid var(--line);
  background: none;
  color: var(--ink-2);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.rail-link:hover { color: var(--brand); }
.rail-link-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.paper-row { align-items: flex-start; padding: 16px 4px 18px; }
.paper-row:hover .exam-paper-title { color: var(--brand); }
.exam-paper-main { gap: 3px; }
.exam-paper-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 600;
  line-height: 1.4;
  transition: color .14s var(--ease);
}
.exam-paper-sub { gap: 6px 12px; }
.exam-paper-desc {
  margin-top: 4px;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--ink-3);
}
.exam-paper-row .list-side { padding-top: 2px; }
.exam-bank-row .exam-bank-title { font-size: 13.5px; }
.bp-total { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; border-top: 1px solid var(--line); padding-top: 12px; }
.bp-negative { width: 140px; }
.bp-sections { display: flex; flex-direction: column; }
.bp-section { display: grid; grid-template-columns: minmax(0, 1fr) 76px minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 7px 0; border-top: 1px solid var(--line); }
.bp-section:first-child { border-top: 0; }
.bp-count { text-align: right; }
.setup-check { display: flex; flex-direction: row; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-2); }
.action-with-reason { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.action-reason { font-size: 12px; line-height: 1.5; color: var(--ink-3); }
.exam-load-error .btn { margin-left: auto; flex: none; }
.exam-dialog-form { display: flex; flex-direction: column; gap: 14px; }
.drawer-heading { flex: 1; min-width: 0; }
.drawer-body { flex: none; overflow: visible; padding: 0; }
.drawer-foot { width: 100%; padding: 0; border-top: 0; background: transparent; }
/* AppDialog owns the modal chrome; the legacy setup/drawer classes remain on
   the panel only so existing browser selectors keep resolving. */
:global(.app-dialog-panel.exam-setup-dialog) {
  padding: 0;
  gap: 0;
  overflow: visible;
}
:global(.app-dialog-panel.drawer) {
  position: relative;
  top: auto;
  right: auto;
  bottom: auto;
  width: min(100%, 720px);
  max-height: min(88dvh, 960px);
}
@media (max-width: 1280px) {
  .exam-layout { gap: 40px; }
}
@media (max-width: 1100px) {
  .exam-layout { grid-template-columns: minmax(0, 1fr) 236px; gap: 28px; }
}
@media (max-width: 900px) {
  .exam-layout { grid-template-columns: minmax(0, 1fr); gap: 30px; }
  .exam-rail {
    display: block;
    border-left: 0;
    border-top: 1px solid var(--line-strong);
    padding: 20px 0 0;
  }
  .rail-block + .rail-block { margin-top: 24px; }
}
@media (max-width: 640px) {
  .paper-row { flex-wrap: wrap; }
  .paper-row .list-side { width: 100%; justify-content: flex-end; }
  .bp-section { grid-template-columns: minmax(0, 1fr) 66px; }
  .bp-section .select:nth-of-type(2) { grid-column: 2; }
}
</style>
