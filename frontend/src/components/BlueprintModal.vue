<template>
  <div class="exam-setup-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 44rem); max-height: 85vh; overflow-y: auto;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
        <h2 style="margin: 0;">{{ t('ui.k0215') }}</h2>
        <!-- 模式切换开关 -->
        <div style="display: flex; gap: 0.25rem; background: var(--bg-subtle); padding: 0.2rem; border-radius: 6px; border: 1px solid var(--border);">
          <button
            type="button"
            style="padding: 0.25rem 0.65rem; font-size: 0.78rem; border-radius: 4px; cursor: pointer; border: none; transition: all 120ms ease;"
            :style="blueprintMode === 'simple' ? 'background: var(--primary); color: #fff; font-weight: 600;' : 'background: transparent; color: var(--text-muted);'"
            @click="blueprintMode = 'simple'"
          >
            {{ t('blueprint.mode_simple') }}
          </button>
          <button
            type="button"
            style="padding: 0.25rem 0.65rem; font-size: 0.78rem; border-radius: 4px; cursor: pointer; border: none; transition: all 120ms ease;"
            :style="blueprintMode === 'advanced' ? 'background: var(--primary); color: #fff; font-weight: 600;' : 'background: transparent; color: var(--text-muted);'"
            @click="blueprintMode = 'advanced'"
          >
            {{ t('blueprint.mode_advanced') }}
          </button>
        </div>
      </div>

      <!-- 蓝图引导卡片 (轻量指引，支持不再提示) -->
      <div v-if="!hideBlueprintGuide" style="background: var(--linear-bg-subtle); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; position: relative;">
        <button
          type="button"
          style="position: absolute; top: 0.5rem; right: 0.5rem; border: none; background: none; color: var(--text-tertiary); font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 0.25rem;"
          @click="dismissBlueprintGuide"
        >
          <span>{{ t('blueprint.hide_guide') }}</span> ✕
        </button>
        <div style="display: flex; gap: 0.5rem; align-items: flex-start;">
          <LinearIcon name="blueprint" size="20" style="color: var(--primary); margin-top: 2px;" />
          <div style="font-size: 0.85rem; color: var(--text-main); line-height: 1.5; padding-right: 4.5rem;">
            <strong>{{ t('ui.k0216') }}</strong>
            <p style="margin: 0.2rem 0 0.4rem; color: var(--text-muted);">
              {{ t('blueprint.guide_banner') }}
            </p>
            <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
              <span style="font-weight: 600; color: var(--primary);">{{ t('ui.k0218') }}</span>
              <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('STANDARD_50')">
                {{ t('ui.k0219') }}
              </button>
              <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('OBJECTIVE_30')">
                {{ t('ui.k0220') }}
              </button>
              <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('ADVANCED_SPRINT')">
                {{ t('ui.k0221') }}
              </button>
              <button type="button" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; background: var(--primary-light); border: 1px solid var(--primary-border); border-radius: 4px; cursor: pointer;" @click="applyBlueprintTemplate('BASIC_25')">
                {{ t('ui.k0222') }}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div v-else style="display: flex; justify-content: flex-end; margin-bottom: 0.5rem;">
        <button type="button" style="border: none; background: none; font-size: 0.75rem; color: var(--text-tertiary); cursor: pointer; text-decoration: underline;" @click="hideBlueprintGuide = false">
          {{ t('blueprint.show_guide') }}
        </button>
      </div>

      <!-- 档案选择与新建 -->
      <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 1rem;">
        <select v-model="activeBlueprintProfileId" style="flex: 1;" @change="loadProfileBlueprint">
          <option value="">{{ t('ui.k0223') }}</option>
          <option v-for="p in examProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button type="button" @click="showCreateProfileBox = !showCreateProfileBox">{{ t('ui.k0224') }}</button>
      </div>

      <form v-if="showCreateProfileBox" style="background: var(--bg-subtle); padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem;" @submit.prevent="handleCreateExamProfile">
        <div style="display: flex; gap: 0.5rem; margin-bottom: 0.4rem;">
          <input v-model.trim="newProfileName" style="flex: 1;" :placeholder="t('ui.k0225')" required />
          <button type="submit" :disabled="creatingProfile">{{ creatingProfile ? t('ui.k0680') : t('ui.k0681') }}</button>
        </div>
        <input v-model.trim="newProfileDesc" :placeholder="t('ui.k0226')" />
      </form>

      <div v-if="activeBlueprintProfileId" style="border: 1px solid var(--border); border-radius: 8px; padding: 1rem; background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);">
          <h3 style="font-size: 0.95rem; margin: 0; color: var(--text-main);">{{ t('ui.k0227') }}</h3>
          <span style="font-size: 0.8rem; background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 4px; padding: 0.2rem 0.5rem; color: var(--text-muted); font-family: var(--linear-mono);">
            {{ t('ui.k0228') }} {{ blueprintConfig.sections.length }} {{ t('ui.k0229') }} <strong>{{ computedBlueprintTotal }}</strong> {{ t('ui.k0230') }} {{ Math.round(computedBlueprintTotal * 1.5) }} {{ t('ui.k0231') }}
          </span>
        </div>

        <!-- 简易模式配置面板 -->
        <div v-if="blueprintMode === 'simple'" class="simple-blueprint-panel" style="display: grid; gap: 0.75rem; margin-bottom: 1rem;">
          <p style="font-size: 0.8rem; color: var(--text-muted); margin: 0;">{{ t('blueprint.simple_desc') }}</p>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr)); gap: 0.65rem;">
            <div style="background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px; padding: 0.65rem 0.75rem;">
              <label style="font-size: 0.78rem; font-weight: 600; display: block; margin-bottom: 0.35rem;">{{ t('blueprint.sec_single') }}</label>
              <input v-model.number="simpleBlueprint.single_count" type="number" min="0" max="500" style="width: 100%; font-size: 0.9rem;" @input="syncFromSimpleMode" />
            </div>
            <div style="background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px; padding: 0.65rem 0.75rem;">
              <label style="font-size: 0.78rem; font-weight: 600; display: block; margin-bottom: 0.35rem;">{{ t('blueprint.sec_multi') }}</label>
              <input v-model.number="simpleBlueprint.multi_count" type="number" min="0" max="500" style="width: 100%; font-size: 0.9rem;" @input="syncFromSimpleMode" />
            </div>
            <div style="background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px; padding: 0.65rem 0.75rem;">
              <label style="font-size: 0.78rem; font-weight: 600; display: block; margin-bottom: 0.35rem;">{{ t('blueprint.sec_judge') }}</label>
              <input v-model.number="simpleBlueprint.judge_count" type="number" min="0" max="500" style="width: 100%; font-size: 0.9rem;" @input="syncFromSimpleMode" />
            </div>
            <div style="background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px; padding: 0.65rem 0.75rem;">
              <label style="font-size: 0.78rem; font-weight: 600; display: block; margin-bottom: 0.35rem;">{{ t('blueprint.sec_essay') }}</label>
              <input v-model.number="simpleBlueprint.essay_count" type="number" min="0" max="500" style="width: 100%; font-size: 0.9rem;" @input="syncFromSimpleMode" />
            </div>
          </div>
          <div style="display: flex; gap: 0.75rem; align-items: center; background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem 0.75rem;">
            <label style="font-size: 0.8rem; font-weight: 500; white-space: nowrap;">{{ t('blueprint.uniform_difficulty') }}：</label>
            <select v-model.number="simpleBlueprint.difficulty" style="flex: 1; font-size: 0.8rem;" @change="syncFromSimpleMode">
              <option :value="null">{{ t('blueprint.diff_any') }}</option>
              <option :value="1">{{ t('ui.k0168') }}</option>
              <option :value="2">{{ t('ui.k0169') }}</option>
              <option :value="3">{{ t('ui.k0170') }}</option>
              <option :value="4">{{ t('ui.k0171') }}</option>
              <option :value="5">{{ t('ui.k0172') }}</option>
            </select>
          </div>
        </div>

        <!-- 高级模式配置面板 -->
        <div v-else style="margin-bottom: 0.75rem;">
          <label style="font-size: 0.85rem; margin-bottom: 0.75rem; color: var(--text-main); display: block;">{{ t('ui.k0232') }}
            <input v-model.number="blueprintConfig.negative_mark" type="number" step="0.1" min="0" max="10" style="width: 8rem; margin-left: 0.5rem;" />
            <span style="font-size: 0.75rem; color: var(--text-tertiary); font-weight: normal; margin-left: 0.5rem;">{{ t('ui.k0233') }}</span>
          </label>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
            <span style="font-size: 0.85rem; font-weight: 600; color: var(--text-main);">{{ t('ui.k0234') }}</span>
            <button type="button" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;" @click="handleAddBlueprintSection">{{ t('ui.k0235') }}</button>
          </div>
          <div v-if="!blueprintConfig.sections.length" style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem; background: var(--bg-subtle); border-radius: 4px; text-align: center;">
            {{ t('ui.k0236') }}
          </div>
          <div v-for="(sec, sIdx) in blueprintConfig.sections" :key="sIdx" style="display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.5rem; padding: 0.6rem; background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px;">
            <div style="display: flex; gap: 0.4rem; align-items: center;">
              <input v-model.trim="sec.name" :placeholder="t('ui.k0237')" style="width: 10rem; font-size: 0.8rem;" />
              <select v-model="sec.type" style="width: 6.5rem; font-size: 0.8rem;">
                <option value="SINGLE">{{ t('ui.k0050') }}</option>
                <option value="MULTI">{{ t('ui.k0051') }}</option>
                <option value="JUDGE">{{ t('ui.k0052') }}</option>
                <option value="ESSAY">{{ t('ui.k0238') }}</option>
              </select>
              <input v-model.number="sec.count" type="number" min="1" :placeholder="t('ui.k0239')" style="width: 4.5rem; font-size: 0.8rem;" :title="t('ui.k0240')" />
              <select v-model.number="sec.difficulty" style="width: 5.5rem; font-size: 0.8rem;" :title="t('ui.k0241')">
                <option :value="null">{{ t('ui.k0242') }}</option>
                <option :value="1">{{ t('ui.k0168') }}</option>
                <option :value="2">{{ t('ui.k0169') }}</option>
                <option :value="3">{{ t('ui.k0170') }}</option>
                <option :value="4">{{ t('ui.k0171') }}</option>
                <option :value="5">{{ t('ui.k0172') }}</option>
              </select>
              <button type="button" style="color: var(--danger); border: none; background: none; cursor: pointer; padding: 0 0.3rem;" :title="t('ui.k0243')" @click="blueprintConfig.sections.splice(sIdx, 1)">✕</button>
            </div>
            <div style="display: flex; gap: 0.4rem; align-items: center; font-size: 0.75rem;">
              <input v-model.trim="sec.chapter_id" :placeholder="t('ui.k0244')" style="flex: 1; font-size: 0.75rem;" />
              <input v-model.trim="sec.tags" :placeholder="t('ui.k0245')" style="flex: 1; font-size: 0.75rem;" />
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.6rem;">
          <button type="button" class="primary" :disabled="savingBlueprint" @click="handleSaveBlueprint">
            {{ savingBlueprint ? t('ui.k0668') : t('ui.k0682') }}
          </button>
        </div>
      </div>

      <div class="bank-actions" style="margin-top: 1rem;">
        <button type="button" @click="$emit('close')">{{ t('ui.k0134') }}</button>
      </div>
    </div>
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
