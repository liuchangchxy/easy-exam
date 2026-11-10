<template>
  <div class="exam-center">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">{{ t('ep.nav.study') }}</div>
        <h1 class="page-title">{{ t('ep.exam.title') }}</h1>
        <p class="page-sub">{{ t('ep.exam.sub') }}</p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn" @click="openCreatePaper">
          <LinearIcon name="plus" :size="14" />{{ t('ep.exam.new_paper') }}
        </button>
        <button type="button" class="btn btn-primary" :disabled="!banks.length" @click="openSetup()">
          <LinearIcon name="play" :size="14" />{{ t('ep.exam.start') }}
        </button>
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

    <div v-else class="exam-layout">
      <div class="exam-main">
        <section class="panel">
          <div class="panel-head">
            <span class="panel-title">{{ t('ep.exam.papers') }}</span>
            <span class="section-note">{{ t('ep.common.count', { count: profiles.length }) }}</span>
          </div>

          <div v-if="profiles.length" class="list">
            <div v-for="profile in profiles" :key="profile.id" class="list-row paper-row">
              <span class="list-main">
                <span class="list-title">{{ profile.name }}</span>
                <span class="list-meta">
                  <span v-if="blueprintOf(profile)">{{ t('ep.exam.blueprint_sections', { count: blueprintOf(profile).sections?.length || 0 }) }}</span>
                  <span v-if="blueprintOf(profile)">{{ blueprintTotal(profile) }} {{ t('ep.practice.index') }}</span>
                  <span v-if="Number(blueprintOf(profile)?.negative_mark) > 0">{{ t('ep.exam.negative', { points: blueprintOf(profile).negative_mark }) }}</span>
                  <span v-if="profile.description" class="od-truncate">{{ profile.description }}</span>
                </span>
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
              <button type="button" class="btn btn-primary" :disabled="!banks.length" @click="openSetup()">{{ t('ep.exam.start') }}</button>
            </div>
          </div>
        </section>

        <section class="panel" style="margin-top: 28px">
          <div class="panel-head">
            <span class="panel-title">{{ t('ep.exam.start_from_bank') }}</span>
            <span class="section-note">{{ t('ep.exam.start_hint') }}</span>
          </div>
          <div v-if="banks.length" class="list">
            <div v-for="bank in banks" :key="bank.id" class="list-row">
              <span class="list-main">
                <span class="list-title">{{ bank.name }}</span>
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

      <aside class="exam-rail">
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
    <div v-if="showCreate" class="exam-setup-backdrop" @click.self="showCreate = false">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" @submit.prevent="createPaper">
        <h2>{{ t('ep.exam.new_paper') }}</h2>
        <label>{{ t('ep.exam.paper_name') }}
          <input v-model.trim="paperForm.name" type="text" :placeholder="t('ep.exam.paper_name_placeholder')" required />
        </label>
        <label>{{ t('ep.exam.paper_desc') }}
          <input v-model.trim="paperForm.description" type="text" :placeholder="t('ep.exam.paper_desc_placeholder')" />
        </label>
        <div class="bank-actions">
          <button type="button" @click="showCreate = false">{{ t('ep.common.cancel') }}</button>
          <button type="submit" class="primary" :disabled="creating || !paperForm.name">{{ t('ep.exam.create_paper') }}</button>
        </div>
      </form>
    </div>

    <!-- Start exam -->
    <div v-if="showSetup" class="exam-setup-backdrop" @click.self="showSetup = false">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" @submit.prevent="beginExam">
        <h2>{{ t('ep.exam.setup') }}</h2>
        <label>{{ t('ep.exam.bank_pick') }}
          <select v-model="setup.bankId" @change="onSetupBankChange">
            <option v-for="bank in examBanks" :key="bank.id" :value="bank.id">{{ bank.name }} · {{ t('ep.banks.questions', { count: bank.question_count || 0 }) }}</option>
          </select>
        </label>
        <label>{{ t('ep.exam.profile_pick') }}
          <select v-model="setup.profileId" @change="onSetupProfileChange">
            <option value="">{{ t('ep.exam.direct') }}</option>
            <option v-for="profile in blueprintProfiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
          </select>
        </label>
        <p class="hint">{{ t('ep.exam.profile_note') }}</p>
        <label>{{ t('ep.exam.questions') }}
          <input v-model.number="setup.total" type="number" min="1" :max="setupMax" />
        </label>
        <label>{{ t('ep.exam.time') }}
          <input v-model.number="setup.minutes" type="number" min="1" max="600" />
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
    </div>

    <!-- Blueprint drawer -->
    <div v-if="editingProfile" class="drawer-scrim" @click="closeBlueprint"></div>
    <aside v-if="editingProfile" class="drawer" role="dialog" aria-modal="true">
      <div class="drawer-head">
        <div style="flex: 1; min-width: 0">
          <div class="drawer-title">{{ t('ep.exam.blueprint') }}</div>
          <div class="drawer-sub">{{ editingProfile.name }} · v{{ editingProfile.latest_blueprint?.version_number || 0 }}</div>
        </div>
        <button type="button" class="icon-btn" :aria-label="t('ep.common.close')" @click="closeBlueprint">
          <LinearIcon name="x" :size="17" />
        </button>
      </div>
      <div class="drawer-body">
        <div class="bp-total">
          <div class="stat">
            <div class="stat-num">{{ bpTotal }}<span class="unit">{{ t('ep.practice.index') }}</span></div>
            <div class="stat-cap">{{ t('ep.exam.blueprint_total') }}</div>
          </div>
          <label class="field bp-negative">
            <span class="label">{{ t('ep.exam.blueprint_negative') }}</span>
            <input v-model.number="bpForm.negative_mark" class="input" type="number" min="0" max="5" step="0.5" />
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
      <div class="drawer-foot">
        <button type="button" class="btn btn-primary" :disabled="savingBp" @click="saveBp">
          {{ savingBp ? t('ep.common.loading') : t('ep.exam.blueprint_save') }}
        </button>
        <span class="spacer"></span>
        <button type="button" class="btn btn-quiet" @click="closeBlueprint">{{ t('ep.common.cancel') }}</button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
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
const bpError = ref('')
const savingBp = ref(false)

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
  return !!setup.value.bankId && n >= 1 && n <= setupMax.value && Number(setup.value.minutes) > 0
})

const bpTotal = computed(() => bpForm.value.sections.reduce((sum, s) => sum + (Number(s.count) || 0), 0))

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
  notice.value = ''
  const [bankRes, profileRes, sessionRes] = await Promise.allSettled([
    listBanks(props.token),
    listProfiles(props.token),
    listActiveSessions(props.token, 'EXAM'),
  ])
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
  if (bank) setup.value.total = Math.min(Number(setup.value.total) || bank.question_count, bank.question_count)
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
    setupError.value = t('ep.exam.invalid_count', { max: setupMax.value })
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
  editingProfile.value = profile
  bpError.value = ''
  bpForm.value = { negative_mark: 0, sections: [] }
  try {
    const bp = await getBlueprint(props.token, profile.id)
    const data = bp?.blueprint || {}
    bpForm.value = {
      negative_mark: Number(data.negative_mark) || 0,
      sections: (data.sections || []).map(s => ({
        name: s.name || '',
        type: s.type || 'SINGLE',
        count: Number(s.count) || 0,
        difficulty: s.difficulty ?? null,
        chapter_id: s.chapter_id || '',
        tags: s.tags || '',
      })),
    }
  } catch (_) {
    const data = blueprintOf(profile) || {}
    bpForm.value = {
      negative_mark: Number(data.negative_mark) || 0,
      sections: (data.sections || []).map(s => ({
        name: s.name || '',
        type: s.type || 'SINGLE',
        count: Number(s.count) || 0,
        difficulty: s.difficulty ?? null,
        chapter_id: s.chapter_id || '',
        tags: s.tags || '',
      })),
    }
  }
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
  if (!editingProfile.value) return
  if (bpTotal.value <= 0) {
    bpError.value = t('ep.exam.blueprint_invalid')
    return
  }
  savingBp.value = true
  bpError.value = ''
  try {
    await saveBlueprint(props.token, editingProfile.value.id, {
      negative_mark: Number(bpForm.value.negative_mark) || 0,
      sections: bpForm.value.sections.map(s => ({
        name: typeName(s.type),
        type: s.type,
        count: Number(s.count) || 0,
        difficulty: s.difficulty ?? null,
        chapter_id: s.chapter_id || '',
        tags: s.tags || '',
      })),
    })
    profiles.value = await listProfiles(props.token)
    const fresh = profiles.value.find(p => p.id === editingProfile.value.id)
    if (fresh) editingProfile.value = fresh
  } catch (err) {
    bpError.value = err.detail || err.message
  } finally {
    savingBp.value = false
  }
}

function closeBlueprint() {
  editingProfile.value = null
  bpError.value = ''
}

onMounted(load)
</script>

<style scoped>
.exam-center { padding-top: 26px; }
.active-exam { margin-top: 20px; }
.exam-layout { display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 40px; margin-top: 20px; align-items: start; }
.exam-main { min-width: 0; }
.exam-rail { border-top: 1px solid var(--line); padding-top: 14px; }
.rail-block + .rail-block { margin-top: 26px; }
.rail-title { font-size: 11px; font-weight: 600; letter-spacing: .06em; color: var(--ink-2); }
.rail-note { margin: 7px 0 10px; font-size: 11.5px; line-height: 1.7; color: var(--ink-3); }
.rail-list { display: flex; flex-direction: column; }
.rail-link { display: flex; justify-content: space-between; gap: 10px; padding: 7px 0; border: 0; background: none; color: var(--ink-2); font-size: 12px; text-align: left; cursor: pointer; border-top: 1px solid var(--line); }
.rail-link:hover { color: var(--brand); }
.rail-link-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.paper-row { align-items: flex-start; }
.bp-total { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; border-top: 1px solid var(--line); padding-top: 12px; }
.bp-negative { width: 140px; }
.bp-sections { display: flex; flex-direction: column; }
.bp-section { display: grid; grid-template-columns: minmax(0, 1fr) 76px minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 7px 0; border-top: 1px solid var(--line); }
.bp-section:first-child { border-top: 0; }
.bp-count { text-align: right; }
.setup-check { display: flex; flex-direction: row; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-2); }
@media (max-width: 900px) {
  .exam-layout { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .exam-rail { display: none; }
}
@media (max-width: 640px) {
  .paper-row { flex-wrap: wrap; }
  .paper-row .list-side { width: 100%; justify-content: flex-end; }
  .bp-section { grid-template-columns: minmax(0, 1fr) 66px; }
  .bp-section .select:nth-of-type(2) { grid-column: 2; }
}
</style>
