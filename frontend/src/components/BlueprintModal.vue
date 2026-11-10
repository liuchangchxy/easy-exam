<template>
  <div class="exam-setup-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <section class="exam-setup-dialog blueprint-dialog" role="dialog" aria-modal="true" aria-labelledby="blueprint-title">
      <div class="dialog-header-flex">
        <div>
          <div class="rule-label">{{ t('ep.exam.blueprint') }}</div>
          <h2 id="blueprint-title">{{ t('ui.k0215') }}</h2>
        </div>
        <div class="seg-control">
          <button type="button" class="seg" :class="{ 'is-on': blueprintMode === 'simple' }" @click="blueprintMode = 'simple'">
            {{ t('blueprint.mode_simple') }}
          </button>
          <button type="button" class="seg" :class="{ 'is-on': blueprintMode === 'advanced' }" @click="blueprintMode = 'advanced'">
            {{ t('blueprint.mode_advanced') }}
          </button>
        </div>
        <button type="button" class="btn-close-icon" :aria-label="t('ep.common.close')" @click="$emit('close')">
          <LinearIcon name="x" size="16" />
        </button>
      </div>

      <div v-if="!hideBlueprintGuide" class="blueprint-guide">
        <LinearIcon name="blueprint" :size="16" />
        <div class="guide-body">
          <strong>{{ t('ui.k0216') }}</strong>
          <p>{{ t('blueprint.guide_banner') }}</p>
          <div class="guide-templates">
            <span class="guide-label">{{ t('ui.k0218') }}</span>
            <button type="button" class="btn btn-sm btn-quiet" @click="applyBlueprintTemplate('STANDARD_50')">{{ t('ui.k0219') }}</button>
            <button type="button" class="btn btn-sm btn-quiet" @click="applyBlueprintTemplate('OBJECTIVE_30')">{{ t('ui.k0220') }}</button>
            <button type="button" class="btn btn-sm btn-quiet" @click="applyBlueprintTemplate('ADVANCED_SPRINT')">{{ t('ui.k0221') }}</button>
            <button type="button" class="btn btn-sm btn-quiet" @click="applyBlueprintTemplate('BASIC_25')">{{ t('ui.k0222') }}</button>
          </div>
        </div>
        <button type="button" class="icon-btn guide-dismiss" :aria-label="t('blueprint.hide_guide')" @click="dismissBlueprintGuide">
          <LinearIcon name="x" :size="13" />
        </button>
      </div>
      <button v-else type="button" class="link-btn guide-restore" @click="hideBlueprintGuide = false">
        {{ t('blueprint.show_guide') }}
      </button>

      <div class="blueprint-profile-row">
        <label class="field">
          <span class="label">{{ t('ep.exam.profile_pick') }}</span>
          <select v-model="activeBlueprintProfileId" class="select" @change="loadProfileBlueprint">
            <option value="">{{ t('ui.k0223') }}</option>
            <option v-for="p in examProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </label>
        <button type="button" class="btn btn-sm" @click="showCreateProfileBox = !showCreateProfileBox">{{ t('ui.k0224') }}</button>
      </div>

      <form v-if="showCreateProfileBox" class="blueprint-create" @submit.prevent="handleCreateExamProfile">
        <div class="create-row">
          <input v-model.trim="newProfileName" class="input" :placeholder="t('ui.k0225')" required />
          <button type="submit" class="btn btn-sm" :disabled="creatingProfile">{{ creatingProfile ? t('ui.k0680') : t('ui.k0681') }}</button>
        </div>
        <input v-model.trim="newProfileDesc" class="input" :placeholder="t('ui.k0226')" />
      </form>

      <section v-if="activeBlueprintProfileId" class="blueprint-editor">
        <header class="editor-head">
          <h3>{{ t('ui.k0227') }}</h3>
          <span class="editor-count mono">
            {{ t('ui.k0228') }} {{ blueprintConfig.sections.length }} {{ t('ui.k0229') }} · {{ computedBlueprintTotal }} {{ t('ui.k0230') }}
          </span>
        </header>

        <div v-if="blueprintMode === 'simple'" class="simple-panel">
          <p class="hint">{{ t('blueprint.simple_desc') }}</p>
          <div class="simple-grid">
            <label class="field">
              <span class="label">{{ t('blueprint.sec_single') }}</span>
              <input v-model.number="simpleBlueprint.single_count" class="input" type="number" min="0" max="500" @input="syncFromSimpleMode" />
            </label>
            <label class="field">
              <span class="label">{{ t('blueprint.sec_multi') }}</span>
              <input v-model.number="simpleBlueprint.multi_count" class="input" type="number" min="0" max="500" @input="syncFromSimpleMode" />
            </label>
            <label class="field">
              <span class="label">{{ t('blueprint.sec_judge') }}</span>
              <input v-model.number="simpleBlueprint.judge_count" class="input" type="number" min="0" max="500" @input="syncFromSimpleMode" />
            </label>
            <label class="field">
              <span class="label">{{ t('blueprint.sec_essay') }}</span>
              <input v-model.number="simpleBlueprint.essay_count" class="input" type="number" min="0" max="500" @input="syncFromSimpleMode" />
            </label>
          </div>
          <label class="field simple-difficulty">
            <span class="label">{{ t('blueprint.uniform_difficulty') }}</span>
            <select v-model.number="simpleBlueprint.difficulty" class="select" @change="syncFromSimpleMode">
              <option :value="null">{{ t('blueprint.diff_any') }}</option>
              <option :value="1">{{ t('ui.k0168') }}</option>
              <option :value="2">{{ t('ui.k0169') }}</option>
              <option :value="3">{{ t('ui.k0170') }}</option>
              <option :value="4">{{ t('ui.k0171') }}</option>
              <option :value="5">{{ t('ui.k0172') }}</option>
            </select>
          </label>
        </div>

        <div v-else class="advanced-panel">
          <label class="field negative-field">
            <span class="label">{{ t('ui.k0232') }}</span>
            <span class="negative-input">
              <input v-model.number="blueprintConfig.negative_mark" class="input" type="number" step="0.1" min="0" max="10" />
              <span class="hint">{{ t('ui.k0233') }}</span>
            </span>
          </label>

          <div class="section-bar">
            <span class="rule-label">{{ t('ui.k0234') }}</span>
            <button type="button" class="btn btn-sm btn-quiet" @click="handleAddBlueprintSection">{{ t('ui.k0235') }}</button>
          </div>
          <p v-if="!blueprintConfig.sections.length" class="hint section-empty">{{ t('ui.k0236') }}</p>

          <div v-for="(sec, sIdx) in blueprintConfig.sections" :key="sIdx" class="section-row">
            <div class="section-main">
              <input v-model.trim="sec.name" class="input section-name" :placeholder="t('ui.k0237')" />
              <select v-model="sec.type" class="select section-type">
                <option value="SINGLE">{{ t('ui.k0050') }}</option>
                <option value="MULTI">{{ t('ui.k0051') }}</option>
                <option value="JUDGE">{{ t('ui.k0052') }}</option>
                <option value="ESSAY">{{ t('ui.k0238') }}</option>
              </select>
              <input v-model.number="sec.count" class="input section-count" type="number" min="1" :placeholder="t('ui.k0239')" :title="t('ui.k0240')" />
              <select v-model.number="sec.difficulty" class="select section-diff" :title="t('ui.k0241')">
                <option :value="null">{{ t('ui.k0242') }}</option>
                <option :value="1">{{ t('ui.k0168') }}</option>
                <option :value="2">{{ t('ui.k0169') }}</option>
                <option :value="3">{{ t('ui.k0170') }}</option>
                <option :value="4">{{ t('ui.k0171') }}</option>
                <option :value="5">{{ t('ui.k0172') }}</option>
              </select>
              <button type="button" class="icon-btn section-remove" :title="t('ui.k0243')" :aria-label="t('ui.k0243')" @click="blueprintConfig.sections.splice(sIdx, 1)">
                <LinearIcon name="x" :size="13" />
              </button>
            </div>
            <div class="section-filter">
              <input v-model.trim="sec.chapter_id" class="input" :placeholder="t('ui.k0244')" />
              <input v-model.trim="sec.tags" class="input" :placeholder="t('ui.k0245')" />
            </div>
          </div>
        </div>

        <div class="editor-actions">
          <button type="button" class="btn btn-primary" :disabled="savingBlueprint" @click="handleSaveBlueprint">
            {{ savingBlueprint ? t('ui.k0668') : t('ui.k0682') }}
          </button>
        </div>
      </section>

      <div class="dialog-actions">
        <button type="button" class="btn" @click="$emit('close')">{{ t('ui.k0134') }}</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import LinearIcon from './LinearIcon.vue'
import { listProfiles, createProfile, saveBlueprint, getBlueprint } from '../api/exams'
import { useLocale } from '../composables/useLocale.js'

const { t } = useLocale()

const props = defineProps({
  token: { type: String, required: true },
  initialProfileId: { type: String, default: '' }
})

const emit = defineEmits(['close', 'saved'])

const examProfiles = ref([])
const activeBlueprintProfileId = ref(props.initialProfileId || '')
const showCreateProfileBox = ref(false)
const newProfileName = ref('')
const newProfileDesc = ref('')
const creatingProfile = ref(false)
const savingBlueprint = ref(false)
const blueprintMode = ref('simple')
const hideBlueprintGuide = ref(false)

const blueprintConfig = ref({
  negative_mark: 0,
  sections: [],
})

const simpleBlueprint = ref({
  single_count: 35,
  multi_count: 10,
  judge_count: 5,
  essay_count: 0,
  difficulty: null,
})

const computedBlueprintTotal = computed(() => {
  if (!blueprintConfig.value?.sections?.length) return 0
  return blueprintConfig.value.sections.reduce((acc, s) => acc + (Number(s.count) || 0), 0)
})

onMounted(async () => {
  try {
    hideBlueprintGuide.value = localStorage.getItem('easyexam_hide_blueprint_guide') === 'true'
  } catch (_) {}

  try {
    examProfiles.value = await listProfiles(props.token)
  } catch (_) {
    examProfiles.value = []
  }

  if (examProfiles.value.length > 0 && !activeBlueprintProfileId.value) {
    activeBlueprintProfileId.value = examProfiles.value[0].id
  }
  if (activeBlueprintProfileId.value) {
    await loadProfileBlueprint()
  }
})

function dismissBlueprintGuide() {
  hideBlueprintGuide.value = true
  try {
    localStorage.setItem('easyexam_hide_blueprint_guide', 'true')
  } catch (_) {}
}

async function loadProfileBlueprint() {
  if (!activeBlueprintProfileId.value) return
  try {
    const bp = await getBlueprint(props.token, activeBlueprintProfileId.value)
    if (bp && (bp.sections || bp.negative_mark !== undefined)) {
      blueprintConfig.value = {
        negative_mark: bp.negative_mark || 0,
        sections: bp.sections || [],
      }
    } else {
      blueprintConfig.value = { negative_mark: 0, sections: [] }
    }
  } catch (err) {
    console.error(t('ui.k0288'), err)
    blueprintConfig.value = { negative_mark: 0, sections: [] }
  } finally {
    syncToSimpleMode()
  }
}

function syncToSimpleMode() {
  let single = 0, multi = 0, judge = 0, essay = 0
  let diff = null
  for (const s of (blueprintConfig.value?.sections || [])) {
    if (s.type === 'SINGLE') single += (Number(s.count) || 0)
    else if (s.type === 'MULTI') multi += (Number(s.count) || 0)
    else if (s.type === 'JUDGE') judge += (Number(s.count) || 0)
    else if (s.type === 'ESSAY') essay += (Number(s.count) || 0)
    if (diff === null && s.difficulty) diff = s.difficulty
  }
  simpleBlueprint.value = {
    single_count: single,
    multi_count: multi,
    judge_count: judge,
    essay_count: essay,
    difficulty: diff,
  }
}

function syncFromSimpleMode() {
  const sections = []
  if (simpleBlueprint.value.single_count > 0) {
    sections.push({ name: t('ui.k0317'), type: 'SINGLE', count: Number(simpleBlueprint.value.single_count), difficulty: simpleBlueprint.value.difficulty, chapter_id: '', tags: '' })
  }
  if (simpleBlueprint.value.multi_count > 0) {
    sections.push({ name: t('ui.k0309'), type: 'MULTI', count: Number(simpleBlueprint.value.multi_count), difficulty: simpleBlueprint.value.difficulty, chapter_id: '', tags: '' })
  }
  if (simpleBlueprint.value.judge_count > 0) {
    sections.push({ name: t('ui.k0318'), type: 'JUDGE', count: Number(simpleBlueprint.value.judge_count), difficulty: simpleBlueprint.value.difficulty, chapter_id: '', tags: '' })
  }
  if (simpleBlueprint.value.essay_count > 0) {
    sections.push({ name: t('ui.k0316'), type: 'ESSAY', count: Number(simpleBlueprint.value.essay_count), difficulty: simpleBlueprint.value.difficulty, chapter_id: '', tags: '' })
  }
  blueprintConfig.value.sections = sections
}

function applyBlueprintTemplate(templateKey) {
  if (templateKey === 'STANDARD_50') {
    blueprintConfig.value = {
      negative_mark: 0,
      sections: [
        { name: t('ui.k0308'), type: 'SINGLE', count: 35, difficulty: null, chapter_id: '', tags: '' },
        { name: t('ui.k0309'), type: 'MULTI', count: 10, difficulty: null, chapter_id: '', tags: '' },
        { name: t('ui.k0310'), type: 'JUDGE', count: 5, difficulty: null, chapter_id: '', tags: '' },
      ],
    }
  } else if (templateKey === 'OBJECTIVE_30') {
    blueprintConfig.value = {
      negative_mark: 0,
      sections: [
        { name: t('ui.k0311'), type: 'SINGLE', count: 20, difficulty: null, chapter_id: '', tags: '' },
        { name: t('ui.k0312'), type: 'MULTI', count: 10, difficulty: null, chapter_id: '', tags: '' },
      ],
    }
  } else if (templateKey === 'ADVANCED_SPRINT') {
    blueprintConfig.value = {
      negative_mark: 0.5,
      sections: [
        { name: t('ui.k0313'), type: 'SINGLE', count: 30, difficulty: 2, chapter_id: '', tags: '' },
        { name: t('ui.k0314'), type: 'SINGLE', count: 20, difficulty: 4, chapter_id: '', tags: '' },
        { name: t('ui.k0315'), type: 'MULTI', count: 15, difficulty: 3, chapter_id: '', tags: '' },
        { name: t('ui.k0316'), type: 'ESSAY', count: 10, difficulty: null, chapter_id: '', tags: '' },
      ],
    }
  } else if (templateKey === 'BASIC_25') {
    blueprintConfig.value = {
      negative_mark: 0,
      sections: [
        { name: t('ui.k0317'), type: 'SINGLE', count: 20, difficulty: 1, chapter_id: '', tags: '' },
        { name: t('ui.k0318'), type: 'JUDGE', count: 5, difficulty: 1, chapter_id: '', tags: '' },
      ],
    }
  }
  syncToSimpleMode()
}

async function handleCreateExamProfile() {
  if (!newProfileName.value.trim()) return
  creatingProfile.value = true
  try {
    const profile = await createProfile(props.token, {
      name: newProfileName.value.trim(),
      description: newProfileDesc.value.trim(),
    })
    examProfiles.value.push(profile)
    activeBlueprintProfileId.value = profile.id
    showCreateProfileBox.value = false
    newProfileName.value = ''
    newProfileDesc.value = ''
    blueprintConfig.value = { negative_mark: 0, sections: [] }
  } catch (err) {
    alert(`${t('ui.k0289')}${err.detail || err.message}`)
  } finally {
    creatingProfile.value = false
  }
}

function handleAddBlueprintSection() {
  blueprintConfig.value.sections.push({
    name: `${t('ui.k0290')} ${blueprintConfig.value.sections.length + 1}`,
    type: 'SINGLE',
    count: 10,
    difficulty: null,
  })
}

async function handleSaveBlueprint() {
  if (!activeBlueprintProfileId.value) return
  savingBlueprint.value = true
  try {
    await saveBlueprint(props.token, activeBlueprintProfileId.value, {
      negative_mark: blueprintConfig.value.negative_mark,
      sections: blueprintConfig.value.sections,
    })
    alert(t('ui.k0291'))
    examProfiles.value = await listProfiles(props.token)
    emit('saved')
  } catch (err) {
    alert(`${t('ui.k0292')}${err.detail || err.message}`)
  } finally {
    savingBlueprint.value = false
  }
}
</script>

<style scoped>
.blueprint-dialog { width: min(100%, 660px); gap: 0; }
.blueprint-dialog h2 { margin: 3px 0 0; }
.seg-control {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: var(--r-xs);
  margin-left: auto;
}
.seg {
  border: 0;
  background: transparent;
  color: var(--ink-3);
  font-family: var(--font-sans);
  font-size: 11.5px;
  padding: 5px 10px;
  cursor: pointer;
}
.seg + .seg { border-left: 1px solid var(--line); }
.seg.is-on { background: var(--ink); color: var(--paper); }
.blueprint-guide {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-top: 18px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--ink-3);
}
.guide-body { flex: 1; min-width: 0; }
.guide-body strong { font-family: var(--font-sans); font-size: 12px; color: var(--ink); }
.guide-body p { margin: 3px 0 8px; font-size: 12px; line-height: 1.6; color: var(--ink-3); }
.guide-templates { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.guide-label { font-family: var(--font-sans); font-size: 11px; font-weight: 600; color: var(--ink-2); }
.guide-dismiss { flex-shrink: 0; width: 24px; height: 24px; }
.guide-restore { align-self: flex-end; margin-top: 10px; font-size: 11px; }
.link-btn {
  border: 0;
  background: transparent;
  color: var(--brand);
  font-family: var(--font-sans);
  font-size: 11.5px;
  padding: 0;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.blueprint-profile-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  margin-top: 16px;
}
.blueprint-profile-row .field { flex: 1; }
.blueprint-profile-row .btn { flex-shrink: 0; height: 34px; }
.blueprint-create {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 10px;
  padding: 12px;
  border: 1px solid var(--line);
  background: var(--surface-2);
}
.create-row { display: flex; gap: 7px; }
.create-row .input { flex: 1; }
.blueprint-editor {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.editor-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.editor-head h3 { margin: 0; font-family: var(--font-sans); font-size: 13px; font-weight: 650; }
.editor-count { font-size: 10.5px; color: var(--ink-3); }
.simple-panel .hint { margin: 0 0 10px; }
.simple-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.simple-difficulty { margin-top: 10px; max-width: 240px; }
.advanced-panel { display: flex; flex-direction: column; gap: 10px; }
.negative-field { max-width: 300px; }
.negative-input { display: flex; align-items: center; gap: 8px; }
.negative-input .input { width: 90px; }
.negative-input .hint { white-space: nowrap; }
.section-bar { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
.section-empty { padding: 14px; text-align: center; border: 1px solid var(--line); }
.section-row {
  padding: 10px;
  border: 1px solid var(--line);
  background: var(--surface-2);
}
.section-main { display: flex; align-items: center; gap: 6px; }
.section-name { width: 150px; }
.section-type { width: 84px; }
.section-count { width: 64px; }
.section-diff { width: 80px; }
.section-remove { color: var(--bad); flex-shrink: 0; }
.section-filter { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }
.section-filter .input { font-size: 11.5px; }
.editor-actions { display: flex; justify-content: flex-end; margin-top: 12px; }
.blueprint-dialog .dialog-actions { margin-top: 4px; padding-top: 14px; border-top: 1px solid var(--line); }
@media (max-width: 640px) {
  .simple-grid { grid-template-columns: 1fr 1fr; }
  .section-main { flex-wrap: wrap; }
  .section-name { flex: 1; min-width: 120px; }
  .section-filter { grid-template-columns: 1fr; }
  .seg-control { margin-left: 0; }
}
</style>
