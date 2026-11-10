<template>
  <div class="bank-detail-page">
    <div class="page-head">
      <div class="page-head-main">
        <div class="page-eyebrow">
          <button type="button" class="link-btn" @click="router.push('/banks')">{{ t('ep.banks.title') }}</button>
          <span aria-hidden="true">/</span>
        </div>
        <h1 class="page-title">{{ bank?.name || t('ep.common.loading') }}</h1>
        <p class="page-sub bank-sub">
          <span>{{ roleLabel(bank?.role) }}</span>
          <span v-if="bank?.category">{{ bank.category }}</span>
          <span>{{ t('ep.banks.questions', { count: questions.length }) }}</span>
          <span>{{ t('ep.banks.chapters', { count: chapters.length }) }}</span>
        </p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn" @click="router.push(`/banks/${bankId}/manage`)">
          <LinearIcon name="columns" :size="14" />{{ t('ep.banks.manage') }}
        </button>
        <button type="button" class="btn" @click="router.push(`/import?bankId=${bankId}`)">
          <LinearIcon name="upload" :size="14" />{{ t('ep.common.import') }}
        </button>
        <button type="button" class="btn btn-primary" :disabled="!questions.length" @click="startPractice">
          <LinearIcon name="play" :size="14" />{{ t('ep.banks.practice') }}
        </button>
      </div>
    </div>

    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key" type="button" class="tab" :class="{ 'is-active': activeTab === tab.key }" @click="activeTab = tab.key">
        {{ t(tab.label) }}<span v-if="tab.count != null" class="count">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="loading" class="skeleton-rows"><div class="skeleton"></div><div class="skeleton"></div></div>

    <template v-else>
      <section v-if="activeTab === 'questions'" class="bank-questions-layout">
        <aside class="bank-chapter-rail">
          <div class="rule-label">{{ t('ep.banks.structure') }}</div>
          <button type="button" class="chapter-item" :class="{ 'is-active': chapterFilter === '' }" @click="chapterFilter = ''">
            <span>{{ t('ep.banks.chapter_all') }}</span><span class="count">{{ questions.length }}</span>
          </button>
          <button v-for="ch in chapters" :key="ch.id" type="button" class="chapter-item" :class="{ 'is-active': chapterFilter === ch.id }" @click="chapterFilter = ch.id">
            <span class="od-truncate">{{ ch.name }}</span><span class="count">{{ chapterCount(ch.id) }}</span>
          </button>
          <div v-if="!chapters.length" class="tiny dim">{{ t('ep.banks.chapter_empty') }}</div>
        </aside>

        <div class="bank-question-main">
          <div class="toolbar bank-toolbar">
            <div class="search-box">
              <LinearIcon name="search" :size="15" />
              <input v-model.trim="query" class="input" :placeholder="t('ep.banks.search_questions')" />
            </div>
            <div class="spacer"></div>
            <span class="small dim">{{ t('ep.common.count', { count: filteredQuestions.length }) }}</span>
          </div>

          <div v-if="filteredQuestions.length" class="qlist">
            <button v-for="(q, index) in filteredQuestions" :key="q.id" type="button" class="qrow bank-qrow" @click="selectedQuestion = q">
              <span class="qrow-num mono">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="qrow-main">
                <span class="qrow-stem">{{ stripHtml(q.stem) }}</span>
                <span class="qrow-meta">
                  <span>{{ typeLabel(q.type) }}</span>
                  <span>{{ chapterName(q.chapter_id) }}</span>
                  <span>v{{ q.version_number }}</span>
                  <span v-if="q.locked_by_active_exam" class="tag warn">{{ t('ep.today.active_badge') }}</span>
                </span>
              </span>
              <span class="qrow-side">{{ difficultyLabel(q.difficulty) }}</span>
            </button>
          </div>
          <div v-else class="empty">
            <div class="empty-title">{{ t('ep.banks.no_questions') }}</div>
            <div class="empty-desc">{{ t('ep.banks.no_questions_hint') }}</div>
            <div class="empty-actions">
              <button type="button" class="btn" @click="router.push(`/banks/${bankId}/manage`)">{{ t('ep.banks.manage') }}</button>
            </div>
          </div>
        </div>
      </section>

      <section v-else-if="activeTab === 'structure'" class="bank-structure">
        <div class="panel">
          <div class="panel-head">
            <span class="panel-title">{{ t('ep.banks.structure') }}</span>
            <span class="section-note">{{ t('ep.banks.chapters', { count: chapters.length }) }}</span>
          </div>
          <div class="list">
            <div v-for="ch in chapters" :key="ch.id" class="list-row">
              <span class="list-main">
                <span class="list-title">{{ ch.name }}</span>
                <span class="list-meta">{{ t('ep.banks.questions', { count: chapterCount(ch.id) }) }}</span>
              </span>
            </div>
            <div v-if="!chapters.length" class="empty" style="padding: 20px 0">
              <div class="empty-desc">{{ t('ep.banks.chapter_empty') }}</div>
            </div>
          </div>
        </div>
      </section>

      <section v-else class="bank-members">
        <div class="panel">
          <div class="panel-head">
            <span class="panel-title">{{ t('ep.banks.member_tab') }}</span>
            <span class="section-note">{{ t('ep.banks.members_note') }}</span>
          </div>
          <div class="list">
            <div v-for="m in members" :key="m.user_id" class="list-row">
              <span class="avatar sm">{{ (m.username || '?').charAt(0).toUpperCase() }}</span>
              <span class="list-main">
                <span class="list-title">{{ m.username }}</span>
                <span class="list-meta">{{ roleLabel(m.role) }}</span>
              </span>
            </div>
            <div v-if="!members.length" class="empty" style="padding: 20px 0">
              <div class="empty-desc">{{ t('ep.common.none') }}</div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <div v-if="selectedQuestion" class="drawer-scrim" @click="selectedQuestion = null"></div>
    <aside v-if="selectedQuestion" class="drawer" role="dialog" aria-modal="true">
      <div class="drawer-head">
        <div style="flex: 1; min-width: 0">
          <div class="drawer-title">{{ t('ep.banks.detail') }}</div>
          <div class="drawer-sub">
            {{ selectedQuestion.id.toUpperCase() }} · v{{ selectedQuestion.version_number }} · {{ typeLabel(selectedQuestion.type) }}
          </div>
        </div>
        <button type="button" class="icon-btn" :aria-label="t('ep.common.close')" @click="selectedQuestion = null">
          <LinearIcon name="x" :size="17" />
        </button>
      </div>
      <div class="drawer-body">
        <div class="q-sheet reading-page" style="box-shadow: none; padding: 0">
          <div class="q-meta">
            <span>{{ chapterName(selectedQuestion.chapter_id) }}</span>
            <span>{{ difficultyLabel(selectedQuestion.difficulty) }}</span>
          </div>
          <div class="q-stem" v-html="renderStem(selectedQuestion.stem)"></div>
          <div v-if="selectedQuestion.options?.length" class="opt-list">
            <div v-for="opt in selectedQuestion.options" :key="opt.key" class="opt" :class="{ 'is-correct': isCorrectOption(selectedQuestion, opt.key) }">
              <span class="opt-key">{{ opt.key }}</span>
              <span class="opt-text">{{ opt.text || opt.content }}</span>
              <span v-if="isCorrectOption(selectedQuestion, opt.key)" class="opt-mark"><LinearIcon name="check" :size="14" /></span>
            </div>
          </div>
          <div class="answer-line">
            <LinearIcon name="check" :size="15" />
            <span>{{ t('ep.banks.answer') }}</span>
            <span class="ans">{{ selectedQuestion.answer || t('ep.banks.answer_none') }}</span>
          </div>
          <div class="explain-body" v-html="renderBody(selectedQuestion.explanation) || `<p>${t('ep.exam.no_analysis')}</p>`"></div>
          <div class="kv" style="margin-top: 20px">
            <div><span class="k">{{ t('ep.banks.type') }}</span><span class="v">{{ typeLabel(selectedQuestion.type) }}</span></div>
            <div><span class="k">{{ t('ep.banks.chapter') }}</span><span class="v">{{ chapterName(selectedQuestion.chapter_id) }}</span></div>
            <div><span class="k">{{ t('ep.banks.difficulty') }}</span><span class="v">{{ difficultyLabel(selectedQuestion.difficulty) }}</span></div>
            <div><span class="k">{{ t('ep.banks.version') }}</span><span class="v">v{{ selectedQuestion.version_number }}</span></div>
          </div>
          <div class="notice info" style="margin-top: 18px">
            <LinearIcon name="info" :size="15" />
            <span>{{ t('ep.banks.version_note') }}</span>
          </div>
        </div>
      </div>
      <div class="drawer-foot">
        <button type="button" class="btn btn-primary" @click="practiceOne(selectedQuestion)">
          <LinearIcon name="play" :size="14" />{{ t('ep.banks.practice_one') }}
        </button>
        <span class="spacer"></span>
        <button type="button" class="btn btn-quiet" @click="router.push(`/banks/${bankId}/manage`)">{{ t('ep.banks.manage') }}</button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import { useLocale } from '../composables/useLocale.js'
import { getBank, listBankQuestionsContent, listChapters, listBankMembers } from '../api/banks'
import { startSession } from '../api/practice'

const props = defineProps({ token: { type: String, required: true }, bankId: { type: String, required: true } })
const router = useRouter()
const { t } = useLocale()

const bank = ref(null)
const questions = ref([])
const chapters = ref([])
const members = ref([])
const loading = ref(true)
const activeTab = ref('questions')
const query = ref('')
const chapterFilter = ref('')
const selectedQuestion = ref(null)

const tabs = computed(() => [
  { key: 'questions', label: 'ep.banks.question_browse', count: questions.value.length },
  { key: 'structure', label: 'ep.banks.structure', count: chapters.value.length },
  { key: 'members', label: 'ep.banks.member_tab', count: members.value.length },
])

const filteredQuestions = computed(() => {
  let list = questions.value
  if (chapterFilter.value) list = list.filter(q => q.chapter_id === chapterFilter.value)
  const q = query.value.trim().toLowerCase()
  if (q) list = list.filter(item => `${stripHtml(item.stem)} ${(item.tags || []).join(' ')}`.toLowerCase().includes(q))
  return list
})

function stripHtml(html) {
  return String(html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

function renderStem(text) {
  return String(text || '').replace(/\n/g, '<br>')
}

function renderBody(text) {
  return text || ''
}

function roleLabel(role) {
  if (role === 'ADMIN') return t('ep.banks.owner')
  if (role === 'EDITOR') return t('ep.banks.editor')
  return t('ep.banks.member')
}

function typeLabel(type) {
  const key = String(type || '').toLowerCase()
  const map = { single: 'single', multi: 'multi', judge: 'judge', fill: 'fill', essay: 'essay', qa: 'essay', short_answer: 'essay', subjective: 'essay' }
  return t('ep.question_types.' + (map[key] || 'single'))
}

function difficultyLabel(value) {
  const n = Number(value)
  if (!n) return t('ep.difficulty.unrated')
  return t('ep.difficulty.' + Math.max(1, Math.min(5, n)))
}

function chapterName(id) {
  return chapters.value.find(c => c.id === id)?.name || t('ep.common.none')
}

function chapterCount(id) {
  return questions.value.filter(q => q.chapter_id === id).length
}

function isCorrectOption(question, key) {
  return String(question.answer || '').toUpperCase().includes(String(key).toUpperCase())
}

async function load() {
  loading.value = true
  const [bankRes, qRes, chRes, membersRes] = await Promise.allSettled([
    getBank(props.token, props.bankId),
    listBankQuestionsContent(props.token, props.bankId),
    listChapters(props.token, props.bankId),
    listBankMembers(props.token, props.bankId),
  ])
  bank.value = bankRes.status === 'fulfilled' ? bankRes.value : null
  questions.value = qRes.status === 'fulfilled' && Array.isArray(qRes.value) ? qRes.value : []
  chapters.value = chRes.status === 'fulfilled' && Array.isArray(chRes.value) ? chRes.value : []
  members.value = membersRes.status === 'fulfilled' && Array.isArray(membersRes.value) ? membersRes.value : []
  loading.value = false
}

async function startPractice() {
  try {
    const session = await startSession(props.token, { bank_id: props.bankId, mode: 'PRACTICE' })
    router.push(`/practice/${session.id}`)
  } catch (_) {}
}

async function practiceOne(question) {
  try {
    const session = await startSession(props.token, {
      bank_id: props.bankId,
      mode: 'PRACTICE',
      question_ids: [question.id],
      total_questions: 1,
    })
    router.push(`/practice/${session.id}`)
  } catch (_) {}
}

onMounted(load)
</script>

<style scoped>
.bank-detail-page { padding-top: 26px; }
.bank-sub { display: flex; flex-wrap: wrap; gap: 14px; }
.bank-questions-layout { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 32px; margin-top: 18px; align-items: start; }
.bank-chapter-rail { border-top: 1px solid var(--line); padding-top: 10px; }
.chapter-item {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  width: 100%; min-height: 34px; padding: 0 8px; border: 0; background: none;
  color: var(--ink-2); font-size: 12.5px; text-align: left; cursor: pointer;
}
.chapter-item:hover { background: var(--surface-2); color: var(--ink); }
.chapter-item.is-active { color: var(--brand); font-weight: 600; }
.chapter-item .count { font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-4); }
.bank-toolbar { margin-top: 0; border-top: 0; }
.bank-qrow { width: 100%; }
.qrow-side { font-size: 11.5px; color: var(--ink-3); }
.qrow-meta { display: flex; flex-wrap: wrap; gap: 10px; }
.small { font-size: 12px; }
@media (max-width: 900px) {
  .bank-questions-layout { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .bank-chapter-rail { display: flex; gap: 4px; overflow-x: auto; border-top: 0; padding-top: 0; }
  .chapter-item { width: auto; white-space: nowrap; min-height: 32px; }
}
</style>
