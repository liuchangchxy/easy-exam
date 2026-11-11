<template>
  <div class="manage-page">
    <div class="page-head manage-head">
      <div class="page-head-main">
        <div class="page-eyebrow">
          <button type="button" class="link-btn" @click="router.push('/banks')">{{ t('ep.banks.title') }}</button>
          <span aria-hidden="true">/</span>
          <span class="mono">{{ t('ep.manage.tab_settings') }}</span>
        </div>
        <h1 class="page-title">{{ bank?.name || t('ep.common.loading') }}</h1>
        <p class="page-sub bank-sub">
          <span>{{ formatRole(bank?.role) }}</span>
          <span v-if="bank?.category">{{ bank.category }}</span>
          <span>{{ t('ep.banks.questions', { count: questions.length }) }}</span>
          <span>{{ t('ep.banks.chapters', { count: chapters.length }) }}</span>
        </p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn" @click="router.push(`/banks/${bankId}`)">
          <LinearIcon name="book" :size="14" />{{ t('ep.banks.open') }}
        </button>
        <button type="button" class="btn" @click="router.push(`/import?bankId=${bankId}`)">
          <LinearIcon name="upload" :size="14" />{{ t('ep.common.import') }}
        </button>
        <button type="button" class="btn btn-primary" :disabled="!canEdit" :title="canEdit ? '' : t('ep.manage.readonly_note')" @click="openCreate">
          <LinearIcon name="plus" :size="14" />{{ t('ep.manage.new_question') }}
        </button>
      </div>
    </div>

    <div v-if="hasActiveExam" class="notice warn manage-notice">
      <LinearIcon name="lock" :size="15" />
      <span><strong>{{ t('ep.manage.locked_title') }}</strong> {{ t('ep.manage.locked_desc') }}</span>
    </div>
    <div v-if="showArchived" class="notice info manage-notice">
      <LinearIcon name="archive" :size="15" />
      <span>{{ t('ep.manage.archived_note') }}</span>
    </div>
    <div v-else-if="bank && !canEdit" class="notice info manage-notice">
      <LinearIcon name="info" :size="15" />
      <span>{{ t('ep.manage.readonly_note') }}</span>
    </div>
    <div v-if="successToast" class="notice ok manage-notice">
      <LinearIcon name="check" :size="15" /><span>{{ successToast }}</span>
    </div>
    <div v-if="conflictAlert" class="notice warn manage-notice">
      <LinearIcon name="alert" :size="15" /><span>{{ conflictAlert }}</span>
      <button type="button" class="btn btn-sm btn-quiet" @click="loadData">{{ t('ep.common.retry') }}</button>
    </div>
    <div v-if="error" class="notice bad manage-notice">
      <LinearIcon name="alert" :size="15" /><span>{{ error }}</span>
    </div>

    <div class="tabs manage-tabs">
      <button v-for="tab in tabs" :key="tab.key" type="button" class="tab" :class="{ 'is-active': activeTab === tab.key }" @click="activeTab = tab.key">
        {{ t(tab.label) }}<span v-if="tab.count != null" class="count">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="loading" class="skeleton-rows"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>

    <template v-else>
      <!-- Questions workspace -->
      <section v-if="activeTab === 'questions'" class="manage-workspace">
        <div class="manage-toolbar bank-manage-toolbar">
          <div class="search-box">
            <LinearIcon name="search" :size="15" />
            <input v-model.trim="filters.keyword" class="input" :placeholder="t('ep.manage.search')" />
          </div>
          <select v-model="filters.type" class="select">
            <option value="">{{ t('ep.manage.filter_type') }}</option>
            <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
            <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
            <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
            <option value="ESSAY">{{ t('ep.question_types.essay') }}</option>
          </select>
          <select v-if="chapters.length" v-model="filters.chapterId" class="select">
            <option value="">{{ t('ep.manage.filter_chapter') }}</option>
            <option v-for="c in chapters" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-model="filters.difficulty" class="select">
            <option value="">{{ t('ep.manage.filter_difficulty') }}</option>
            <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <select v-if="allTags.length" v-model="filters.tag" class="select">
            <option value="">{{ t('ep.manage.filter_tag') }}</option>
            <option v-for="tag in allTags" :key="tag" :value="tag">{{ tag }}</option>
          </select>
          <button v-if="hasActiveFilters" type="button" class="btn btn-sm btn-quiet" @click="resetFilters">{{ t('ep.manage.reset') }}</button>
          <div class="spacer"></div>
          <label class="archived-toggle">
            <input v-model="showArchived" type="checkbox" data-testid="show-archived" @change="onArchivedToggle" />
            <span>{{ t(showArchived ? 'ep.manage.hide_archived' : 'ep.manage.show_archived') }}</span>
          </label>
          <span class="small dim mono">{{ t('ep.manage.shown', { shown: filteredQuestions.length, total: questions.length }) }}</span>
        </div>

        <div v-if="canEdit && selectedIds.size" class="batch-bar">
          <div class="batch-bar-head">
            <span class="batch-title">{{ t('ep.manage.batch_title') }}</span>
            <span class="small dim">{{ t('ep.manage.selected_count', { count: selectedIds.size }) }}</span>
            <button type="button" class="btn btn-sm btn-quiet" @click="clearSelection">{{ t('ep.manage.clear_selection') }}</button>
          </div>
          <div class="batch-controls">
            <div class="batch-group">
              <select v-model="batchChapterId" class="select" data-testid="batch-chapter" :disabled="batchBusy || batchBlocked">
                <option value="">{{ t('ep.manage.batch_chapter_clear') }}</option>
                <option v-for="c in chapters" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
              <button type="button" class="btn btn-sm" data-testid="batch-apply-chapter" :disabled="batchBusy || batchBlocked" @click="runBatch('chapter')">
                {{ t('ep.manage.batch_apply_chapter') }}
              </button>
            </div>
            <div class="batch-group">
              <input v-model.trim="batchTags" class="input" data-testid="batch-tags" :placeholder="t('ep.manage.batch_tags_placeholder')" :disabled="batchBusy || batchBlocked" />
              <button type="button" class="btn btn-sm" data-testid="batch-add-tags" :disabled="batchBusy || batchBlocked || !batchTags" @click="runBatch('add_tags')">
                {{ t('ep.manage.batch_add_tags') }}
              </button>
              <button type="button" class="btn btn-sm btn-quiet" data-testid="batch-remove-tags" :disabled="batchBusy || batchBlocked || !batchTags" @click="runBatch('remove_tags')">
                {{ t('ep.manage.batch_remove_tags') }}
              </button>
            </div>
            <div v-if="batchTargets.length" class="batch-group">
              <select v-model="batchTargetBankId" class="select" data-testid="batch-target" :disabled="batchBusy || batchBlocked">
                <option value="" disabled>{{ t('ep.manage.batch_target_placeholder') }}</option>
                <option v-for="b in batchTargets" :key="b.id" :value="b.id">{{ b.name }}</option>
              </select>
              <button type="button" class="btn btn-sm" data-testid="batch-move" :disabled="batchBusy || batchBlocked || !batchTargetBankId" @click="runBatch('move')">
                {{ t('ep.manage.batch_move_label') }}
              </button>
              <button type="button" class="btn btn-sm" data-testid="batch-copy" :disabled="batchBusy || batchBlocked || !batchTargetBankId" @click="runBatch('copy')">
                {{ t('ep.manage.batch_copy_label') }}
              </button>
            </div>
            <span v-else class="small dim">{{ t('ep.manage.batch_no_target') }}</span>
            <button v-if="!showArchived" type="button" class="btn btn-sm btn-quiet" data-testid="batch-archive" :disabled="batchBusy || batchBlocked" @click="archiveSelected">
              {{ t('ep.manage.batch_archive') }}
            </button>
            <button v-else type="button" class="btn btn-sm" data-testid="batch-restore" :disabled="batchBusy || batchBlocked" @click="restoreSelected">
              {{ t('ep.manage.batch_restore') }}
            </button>
          </div>
          <p v-if="batchBlocked" class="hint bad-text">{{ t('ep.manage.batch_locked_hint') }}</p>
          <p v-if="batchError" class="error">{{ batchError }}</p>
        </div>

        <div v-if="filteredQuestions.length" class="mtable-wrap">
          <table class="mtable bank-manage-table">
            <thead>
              <tr>
                <th v-if="canEdit" class="select-cell">
                  <input
                    type="checkbox"
                    data-testid="select-all"
                    :checked="allVisibleSelected"
                    :aria-label="t('ep.manage.select_all')"
                    @change="toggleSelectAll($event.target.checked)"
                  />
                </th>
                <th class="bank-manage-col-id">{{ t('ep.manage.col_no') }}</th>
                <th class="bank-manage-col-stem">{{ t('ep.manage.col_stem') }}</th>
                <th class="bank-manage-col-type">{{ t('ep.manage.col_type') }}</th>
                <th class="bank-manage-col-chapter">{{ t('ep.manage.col_chapter') }}</th>
                <th class="bank-manage-col-difficulty">{{ t('ep.manage.col_difficulty') }}</th>
                <th class="bank-manage-col-version">{{ t('ep.manage.col_version') }}</th>
                <th class="bank-manage-col-actions">{{ t('ep.manage.col_actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in filteredQuestions" :key="q.id" class="mtable-row" :class="{ 'is-archived': q.archived }" @click="openEdit(q)">
                <td v-if="canEdit" class="select-cell" @click.stop>
                  <input
                    type="checkbox"
                    class="row-select"
                    :data-question-id="q.id"
                    :checked="selectedIds.has(q.id)"
                    :aria-label="t('ep.manage.select_question')"
                    @change="toggleRowSelection(q.id)"
                  />
                </td>
                <td class="mono id-cell bank-manage-col-id">{{ questionCode(q.id) }}</td>
                <td class="stem-cell bank-manage-col-stem">
                  <span class="stem-text">{{ stripHtml(q.stem) }}</span>
                  <span v-if="q.tags?.length" class="row-tags">
                    <span v-for="tag in q.tags" :key="tag" class="tag">{{ tag }}</span>
                  </span>
                  <span v-if="q.archived" class="tag">{{ t('ep.manage.archived_badge') }}</span>
                  <span v-if="q.locked_by_active_exam" class="tag warn">{{ t('ep.manage.active_exam_badge') }}</span>
                </td>
                <td class="bank-manage-col-type">{{ formatTypeName(q.type) }}</td>
                <td class="dim-cell bank-manage-col-chapter">{{ getChapterName(q.chapter_id) }}</td>
                <td class="bank-manage-col-difficulty">{{ difficultyLabel(q.difficulty) }}</td>
                <td class="mono dim-cell bank-manage-col-version">{{ t('ep.manage.version_value', { version: q.version_number || 1 }) }}</td>
                <td class="bank-manage-col-actions">
                  <button type="button" class="btn btn-sm btn-quiet" @click.stop="openEdit(q)">
                    {{ rowEditable(q) ? t('ep.manage.edit') : t('ep.manage.view') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-else class="empty">
          <div class="empty-mark"><LinearIcon name="layers" :size="24" /></div>
          <div class="empty-title">{{ questions.length ? t('ep.manage.no_match') : t('ep.manage.empty_bank') }}</div>
          <div class="empty-desc">{{ questions.length ? t('ep.manage.no_match_hint') : t('ep.manage.empty_bank_hint') }}</div>
          <div class="empty-actions">
            <button v-if="canEdit" type="button" class="btn" @click="openCreate">{{ t('ep.manage.new_question') }}</button>
            <button type="button" class="btn" @click="router.push(`/import?bankId=${bankId}`)">{{ t('ep.common.import') }}</button>
            <button v-if="hasActiveFilters" type="button" class="btn btn-quiet" @click="resetFilters">{{ t('ep.manage.reset') }}</button>
          </div>
        </div>
      </section>

      <!-- Structure -->
      <section v-else-if="activeTab === 'structure'" class="manage-single">
        <div class="section-note" style="margin-bottom: 12px">{{ t('ep.manage.structure_note') }}</div>
        <div class="panel">
          <div v-if="chapters.length" class="list">
            <div v-for="c in chapters" :key="c.id" class="list-row chapter-row">
              <template v-if="editingChapterId === c.id">
                <input v-model.trim="chapterDraft" class="input chapter-input" :placeholder="t('ep.manage.chapter_name_placeholder')" />
                <span class="list-side">
                  <button type="button" class="btn btn-sm" :disabled="chapterSaving || !chapterDraft" @click="saveChapter(c)">{{ t('ep.common.save') }}</button>
                  <button type="button" class="btn btn-sm btn-quiet" @click="cancelChapterEdit">{{ t('ep.common.cancel') }}</button>
                </span>
              </template>
              <template v-else>
                <span class="list-main">
                  <span class="list-title">{{ c.name }}</span>
                  <span class="list-meta">{{ t('ep.manage.chapter_count', { count: chapterCount(c.id) }) }}</span>
                </span>
                <span v-if="canEdit" class="list-side">
                  <button type="button" class="btn btn-sm btn-quiet" @click="startChapterEdit(c)">{{ t('ep.banks.chapter_rename') }}</button>
                  <button type="button" class="btn btn-sm btn-quiet" @click="removeChapter(c)">{{ t('ep.manage.chapter_delete') }}</button>
                </span>
              </template>
            </div>
          </div>
          <div v-else class="empty" style="padding: 26px 0">
            <div class="empty-desc">{{ t('ep.banks.chapter_empty') }}</div>
          </div>
          <form v-if="canEdit" class="chapter-add" @submit.prevent="addChapter">
            <input v-model.trim="newChapterName" class="input" :placeholder="t('ep.manage.chapter_name_placeholder')" />
            <button type="submit" class="btn btn-sm" :disabled="chapterSaving || !newChapterName">{{ t('ep.banks.chapter_add') }}</button>
          </form>
        </div>
        <div v-if="allTags.length" class="panel" style="margin-top: 24px">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.col_tags') }}</span></div>
          <div class="tag-cloud">
            <span v-for="tag in allTags" :key="tag" class="tag">{{ tag }}<span class="tag-count mono">{{ tagCount(tag) }}</span></span>
          </div>
        </div>
      </section>

      <!-- Members -->
      <section v-else-if="activeTab === 'members'" class="manage-single">
        <div class="section-note" style="margin-bottom: 12px">{{ t('ep.manage.members_note') }}</div>
        <div class="panel">
          <div class="list">
            <div v-for="m in members" :key="m.user_id" class="list-row">
              <span class="avatar sm">{{ (m.username || '?').charAt(0).toUpperCase() }}</span>
              <span class="list-main">
                <span class="list-title">{{ m.username }}</span>
                <span class="list-meta">{{ formatRole(m.role) }}</span>
              </span>
              <span v-if="isOwner && m.role !== 'ADMIN'" class="list-side">
                <button type="button" class="btn btn-sm btn-quiet" @click="removeMember(m)">{{ t('ep.manage.remove_member') }}</button>
              </span>
            </div>
            <div v-if="!members.length" class="empty" style="padding: 24px 0">
              <div class="empty-desc">{{ t('ep.common.none') }}</div>
            </div>
          </div>
        </div>

        <div v-if="isOwner" class="member-add panel" style="margin-top: 24px">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.add_member') }}</span></div>
          <form class="member-form" @submit.prevent="addMember">
            <input v-model.trim="memberForm.username" class="input" :placeholder="t('ep.manage.username_placeholder')" required />
            <select v-model="memberForm.role" class="select">
              <option value="EDITOR">{{ t('ep.banks.editor') }}</option>
              <option value="MEMBER">{{ t('ep.banks.member') }}</option>
            </select>
            <button type="submit" class="btn" :disabled="memberSaving || !memberForm.username">{{ t('ep.manage.add') }}</button>
          </form>
          <div class="hint" style="margin-top: 8px">{{ t('ep.manage.owner_only') }}</div>
        </div>
      </section>

      <!-- Imports -->
      <section v-else-if="activeTab === 'imports'" class="manage-single">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.tab_imports') }}</span></div>
          <p class="section-note">{{ t('ep.manage.imports_note') }}</p>
          <p class="section-note" style="margin-top: 6px">{{ t('ep.manage.formats_note') }}</p>
          <div class="empty-actions" style="justify-content: flex-start; margin-top: 18px">
            <button type="button" class="btn btn-primary" @click="router.push(`/import?bankId=${bankId}`)">
              <LinearIcon name="upload" :size="14" />{{ t('ep.manage.go_import') }}
            </button>
          </div>
        </div>
      </section>

      <!-- AI drafts -->
      <section v-else-if="activeTab === 'drafts'" class="manage-single">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.tab_drafts') }}</span></div>
          <p class="section-note">{{ t('ep.manage.drafts_note') }}</p>
          <div class="empty-actions" style="justify-content: flex-start; margin-top: 18px">
            <button type="button" class="btn" @click="openDialog('drafts')">{{ t('ep.manage.open_drafts') }}</button>
            <button type="button" class="btn btn-quiet" @click="openDialog('ai')">{{ t('ep.manage.ai_configure') }}</button>
          </div>
        </div>
      </section>

      <!-- Bank settings -->
      <section v-else class="manage-single">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.tab_settings') }}</span></div>
          <p class="section-note">{{ t('ep.manage.settings_note') }}</p>
          <div class="kv" style="margin-top: 12px">
            <div class="kv-row"><span class="kv-key">{{ t('ep.manage.name_label') }}</span><span class="kv-val">{{ bank?.name }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.manage.category_label') }}</span><span class="kv-val">{{ bank?.category || t('ep.common.none') }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.manage.description_label') }}</span><span class="kv-val">{{ bank?.description || t('ep.common.none') }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.manage.permission_label') }}</span><span class="kv-val">{{ formatRole(bank?.role) }}</span></div>
            <div class="kv-row"><span class="kv-key">{{ t('ep.manage.locked_meta') }}</span><span class="kv-val">{{ hasActiveExam ? t('ep.manage.locked_title') : t('ep.common.none') }}</span></div>
          </div>
        </div>
      </section>
    </template>

    <!-- Create question -->
    <div v-if="showCreate" class="exam-setup-backdrop" @click.self="showCreate = false">
      <form class="exam-setup-dialog manage-create" role="dialog" aria-modal="true" @submit.prevent="saveQuestion">
        <h2>{{ t('ep.manage.create_title') }}</h2>
        <p class="hint">{{ t('ep.manage.create_desc') }}</p>

        <label>{{ t('ep.manage.stem') }}
          <textarea v-model.trim="createForm.stem" rows="3" :placeholder="t('ep.manage.stem_placeholder')" required></textarea>
        </label>
        <div class="create-grid">
          <label>{{ t('ep.manage.type') }}
            <select v-model="createForm.type" @change="onTypeChange">
              <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
              <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
              <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
              <option value="ESSAY">{{ t('ep.question_types.essay') }}</option>
            </select>
          </label>
          <label>{{ t('ep.manage.difficulty') }}
            <select v-model.number="createForm.difficulty">
              <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label>{{ t('ep.manage.chapter') }}
            <select v-model="createForm.chapter_id">
              <option value="">{{ t('ep.common.none') }}</option>
              <option v-for="c in chapters" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </label>
        </div>

        <div v-if="createForm.type !== 'ESSAY'" class="create-options">
          <div class="create-options-head">
            <span class="label">{{ t('ep.manage.options') }}</span>
            <button v-if="createForm.type !== 'JUDGE'" type="button" class="btn btn-sm btn-quiet" @click="addOption">{{ t('ep.manage.add_option') }}</button>
          </div>
          <div v-for="(opt, idx) in createForm.options" :key="idx" class="create-opt-row">
            <button
              type="button"
              class="opt-key-btn mono"
              :class="{ 'is-on': isAnswerKey(opt.key) }"
              @click="toggleAnswer(opt.key)"
            >{{ opt.key }}</button>
            <input v-model="opt.content" class="input" :placeholder="t('ep.manage.option_text')" />
            <button v-if="createForm.type !== 'JUDGE' && createForm.options.length > 2" type="button" class="icon-btn" :aria-label="t('ep.manage.remove_member')" @click="removeOption(idx)">
              <LinearIcon name="x" :size="13" />
            </button>
          </div>
        </div>

        <div class="create-grid">
          <label>{{ t('ep.manage.answer') }}
            <input v-model.trim="createForm.answer" :placeholder="t('ep.manage.answer_placeholder')" required />
            <span class="hint">{{ t('ep.manage.answer_hint') }}</span>
          </label>
          <label>{{ t('ep.manage.tags') }}
            <input v-model.trim="createForm.tags" :placeholder="t('ep.manage.tags_placeholder')" />
          </label>
        </div>

        <label>{{ t('ep.manage.explanation') }}
          <textarea v-model.trim="createForm.explanation" rows="2" :placeholder="t('ep.manage.explanation_placeholder')"></textarea>
        </label>

        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showCreate = false">{{ t('ep.manage.cancel') }}</button>
          <button type="submit" class="primary" :disabled="creating || !createForm.stem || !createForm.answer">
            {{ creating ? t('ep.manage.saving') : t('ep.manage.save_question') }}
          </button>
        </div>
      </form>
    </div>

    <QuestionEditModal
      :show="Boolean(activeModalQuestion)"
      :question="activeModalQuestion"
      :chapters="chapters"
      :read-only="modalReadOnly"
      :token="token"
      @close="activeModalQuestion = null"
      @saved="handleQuestionSaved"
      @reloaded="handleQuestionReloaded"
      @conflict="handleConflictDetected"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import QuestionEditModal from '../components/QuestionEditModal.vue'
import {
  getBank,
  listBanks,
  listBankQuestionsContent,
  listChapters,
  listBankMembers,
  addBankMember,
  removeBankMember,
  createChapter,
  updateChapter,
  deleteChapter,
  createQuestion,
  batchBankQuestions,
} from '../api/banks'
import { useLocale } from '../composables/useLocale'
import {
  createEmptyBankFilters,
  isFilterActive,
  canEditQuestionInBank,
  isQuestionLocked,
  createSelection,
  toggleSelection,
  toggleVisibleSelection,
  isAllVisibleSelected,
  buildBatchRequest,
  filterBankQuestions,
  adaptOptionsOnTypeChange,
  adaptAnswerOnTypeChange,
  validateQuestionEdit,
} from '../domain/bankManage'

const props = defineProps({
  token: { type: String, required: true },
  user: { type: Object, default: null },
})

const route = useRoute()
const router = useRouter()
const { t } = useLocale()

const bankId = computed(() => route.params.bankId)

const bank = ref(null)
const questions = ref([])
const chapters = ref([])
const members = ref([])
const banks = ref([])
const hasActiveExam = ref(false)
const loading = ref(true)
const error = ref('')
const successToast = ref('')
const conflictAlert = ref('')
const activeTab = ref('questions')

const filters = ref(createEmptyBankFilters())
const activeModalQuestion = ref(null)

const showArchived = ref(false)
const selectedIds = ref(createSelection())
const batchChapterId = ref('')
const batchTags = ref('')
const batchTargetBankId = ref('')
const batchBusy = ref(false)
const batchError = ref('')

const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = ref(emptyForm())

const memberForm = ref({ username: '', role: 'EDITOR' })
const memberSaving = ref(false)

const newChapterName = ref('')
const editingChapterId = ref('')
const chapterDraft = ref('')
const chapterSaving = ref(false)

const longTimer = ref(null)

const tabs = computed(() => [
  { key: 'questions', label: 'ep.manage.tab_questions', count: questions.value.length },
  { key: 'structure', label: 'ep.manage.tab_structure', count: chapters.value.length },
  { key: 'members', label: 'ep.manage.tab_members', count: members.value.length },
  { key: 'imports', label: 'ep.manage.tab_imports', count: null },
  { key: 'drafts', label: 'ep.manage.tab_drafts', count: null },
  { key: 'settings', label: 'ep.manage.tab_settings', count: null },
])

const difficultyOptions = computed(() => [1, 2, 3, 4, 5].map(value => ({ value, label: t('ep.difficulty.' + value) })))

const hasActiveFilters = computed(() => isFilterActive(filters.value))

const allTags = computed(() => {
  const set = new Set()
  for (const q of questions.value) {
    if (Array.isArray(q.tags)) {
      for (const tag of q.tags) {
        if (tag) set.add(tag)
      }
    }
  }
  return Array.from(set).sort()
})

const filteredQuestions = computed(() => filterBankQuestions(questions.value, filters.value))

const canEdit = computed(() => canEditQuestionInBank({
  role: bank.value?.role,
  hasActiveExam: hasActiveExam.value,
}))

const modalReadOnly = computed(() => !activeModalQuestion.value || !rowEditable(activeModalQuestion.value))

const batchTargets = computed(() => banks.value.filter(item => {
  if (item.id === bankId.value) return false
  return ['ADMIN', 'EDITOR'].includes(String(item.role || '').toUpperCase())
}))

const visibleQuestionIds = computed(() => filteredQuestions.value.map(q => q.id))

const allVisibleSelected = computed(() => isAllVisibleSelected(selectedIds.value, visibleQuestionIds.value))

const selectedQuestions = computed(() => questions.value.filter(q => selectedIds.value.has(q.id)))

const selectedLockedCount = computed(() => selectedQuestions.value.filter(q => isQuestionLocked(q)).length)

const batchBlocked = computed(() => selectedLockedCount.value > 0)

const isOwner = computed(() => String(bank.value?.role || '').toUpperCase() === 'ADMIN')

function rowEditable(question) {
  return canEdit.value && !isQuestionLocked(question) && !question?.archived
}

function toggleRowSelection(questionId) {
  selectedIds.value = toggleSelection(selectedIds.value, questionId)
}

function toggleSelectAll(checked) {
  selectedIds.value = toggleVisibleSelection(selectedIds.value, visibleQuestionIds.value, checked)
}

function clearSelection() {
  selectedIds.value = createSelection()
}

function onArchivedToggle() {
  clearSelection()
  loadData()
}

async function runBatch(operation) {
  if (!canEdit.value || batchBlocked.value) return
  let extras = {}
  if (operation === 'chapter') {
    extras = { chapterId: batchChapterId.value }
  } else if (operation === 'add_tags' || operation === 'remove_tags') {
    extras = { tags: batchTags.value.split(/[,，\s]+/).filter(Boolean) }
  } else if (operation === 'move' || operation === 'copy') {
    extras = { targetBankId: batchTargetBankId.value }
  }
  const built = buildBatchRequest(operation, selectedQuestions.value.map(q => q.id), extras)
  if (built.error) {
    batchError.value = t('ep.manage.batch_failed')
    return
  }
  await sendBatch(built.payload)
}

async function archiveSelected() {
  if (!canEdit.value || batchBlocked.value || !selectedQuestions.value.length) return
  if (!window.confirm(t('ep.manage.batch_archive_confirm', { count: selectedQuestions.value.length }))) return
  await sendBatch({ question_ids: selectedQuestions.value.map(q => q.id), operation: 'archive' })
}

async function restoreSelected() {
  if (!canEdit.value || batchBlocked.value || !selectedQuestions.value.length) return
  await sendBatch({ question_ids: selectedQuestions.value.map(q => q.id), operation: 'restore' })
}

async function sendBatch(payload) {
  batchBusy.value = true
  batchError.value = ''
  try {
    await batchBankQuestions(props.token, bankId.value, payload)
    clearSelection()
    batchChapterId.value = ''
    batchTags.value = ''
    await loadData()
    flashSuccess(t('ep.manage.batch_done'))
  } catch (err) {
    batchError.value = err.detail || err.message || t('ep.manage.batch_failed')
  } finally {
    batchBusy.value = false
  }
}

function emptyForm() {
  return {
    stem: '',
    type: 'SINGLE',
    difficulty: 3,
    chapter_id: '',
    options: [
      { key: 'A', content: '' },
      { key: 'B', content: '' },
      { key: 'C', content: '' },
      { key: 'D', content: '' },
    ],
    answer: '',
    explanation: '',
    tags: '',
  }
}

function formatRole(role) {
  if (!role) return ''
  const upper = String(role).toUpperCase()
  if (upper === 'ADMIN') return t('ep.banks.owner')
  if (upper === 'EDITOR') return t('ep.banks.editor')
  return t('ep.banks.member')
}

function formatTypeName(type) {
  const upper = String(type || 'SINGLE').toUpperCase()
  if (upper === 'MULTI') return t('ep.question_types.multi')
  if (upper === 'JUDGE') return t('ep.question_types.judge')
  if (upper === 'ESSAY') return t('ep.question_types.essay')
  if (upper === 'FILL') return t('ep.question_types.fill')
  return t('ep.question_types.single')
}

function difficultyLabel(value) {
  const n = Number(value)
  if (!n) return t('ep.difficulty.unrated')
  return t('ep.difficulty.' + Math.max(1, Math.min(5, n)))
}

function getChapterName(chapId) {
  if (!chapId) return '—'
  return chapters.value.find(item => item.id === chapId)?.name || '—'
}

function chapterCount(id) {
  return questions.value.filter(q => q.chapter_id === id).length
}

function tagCount(tag) {
  return questions.value.filter(q => Array.isArray(q.tags) && q.tags.includes(tag)).length
}

function questionCode(id) {
  return String(id || '').replace(/^q/i, '').slice(0, 8).toUpperCase()
}

function stripHtml(html) {
  return String(html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

function resetFilters() {
  filters.value = createEmptyBankFilters()
}

function openEdit(q) {
  activeModalQuestion.value = q
}

function handleQuestionSaved(updatedQ) {
  if (!updatedQ) return
  const idx = questions.value.findIndex(item => item.id === updatedQ.id)
  if (idx !== -1) questions.value[idx] = updatedQ
  else questions.value.unshift(updatedQ)
  if (updatedQ.conflict) {
    conflictAlert.value = t('bank_manage.conflict_detected')
    successToast.value = ''
  } else {
    conflictAlert.value = ''
    flashSuccess(t('bank_manage.save_success'))
  }
}

function handleQuestionReloaded(latestQ) {
  if (!latestQ) return
  const idx = questions.value.findIndex(item => item.id === latestQ.id)
  if (idx !== -1) questions.value[idx] = latestQ
}

function handleConflictDetected() {
  conflictAlert.value = t('bank_manage.conflict_detected')
  successToast.value = ''
}

function flashSuccess(text) {
  successToast.value = text
  if (longTimer.value) clearTimeout(longTimer.value)
  longTimer.value = setTimeout(() => { successToast.value = '' }, 4000)
}

function openCreate() {
  createForm.value = emptyForm()
  createError.value = ''
  showCreate.value = true
}

function onTypeChange() {
  createForm.value.options = adaptOptionsOnTypeChange(createForm.value.type, createForm.value.options, t)
  createForm.value.answer = adaptAnswerOnTypeChange(createForm.value.type, createForm.value.answer, createForm.value.options)
}

function addOption() {
  const letters = 'ABCDEFGH'
  const nextKey = letters[createForm.value.options.length] || String(createForm.value.options.length + 1)
  createForm.value.options.push({ key: nextKey, content: '' })
}

function removeOption(idx) {
  createForm.value.options.splice(idx, 1)
}

function isAnswerKey(key) {
  return String(createForm.value.answer || '').toUpperCase().includes(String(key).toUpperCase())
}

function toggleAnswer(key) {
  if (createForm.value.type === 'MULTI') {
    const parts = new Set(String(createForm.value.answer || '').split(/[\s,;]+/).filter(Boolean))
    if (parts.has(key)) parts.delete(key)
    else parts.add(key)
    createForm.value.answer = Array.from(parts).join('')
  } else {
    createForm.value.answer = key
  }
}

async function saveQuestion() {
  const validation = validateQuestionEdit(createForm.value.type, createForm.value.options, createForm.value.answer)
  if (!validation.valid) {
    createError.value = validation.error === 'invalid_options' ? t('bank_manage.options_label') : t('bank_manage.answer_label')
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const tags = createForm.value.tags ? createForm.value.tags.split(/[,，\s]+/).filter(Boolean) : []
    const created = await createQuestion(props.token, bankId.value, {
      stem: createForm.value.stem.trim(),
      type: createForm.value.type,
      options: createForm.value.options.map(o => ({ key: o.key, text: o.content, content: o.content })),
      answer: createForm.value.answer.trim(),
      explanation: createForm.value.explanation.trim(),
      difficulty: createForm.value.difficulty,
      tags,
      chapter_id: createForm.value.chapter_id || '',
    })
    questions.value.unshift(created)
    showCreate.value = false
    flashSuccess(t('ep.manage.created'))
  } catch (err) {
    createError.value = err.detail || err.message
  } finally {
    creating.value = false
  }
}

async function addMember() {
  if (!memberForm.value.username) return
  memberSaving.value = true
  error.value = ''
  try {
    await addBankMember(props.token, bankId.value, memberForm.value.username, memberForm.value.role)
    memberForm.value = { username: '', role: 'EDITOR' }
    members.value = await listBankMembers(props.token, bankId.value).catch(() => members.value)
    flashSuccess(t('ep.manage.member_added'))
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    memberSaving.value = false
  }
}

async function removeMember(member) {
  if (!window.confirm(t('ep.manage.remove_member_confirm', { name: member.username }))) return
  error.value = ''
  try {
    await removeBankMember(props.token, bankId.value, member.user_id)
    members.value = members.value.filter(m => m.user_id !== member.user_id)
  } catch (err) {
    error.value = err.detail || err.message
  }
}

function openDialog(dialog) {
  window.dispatchEvent(new CustomEvent('easyexam:open-dialog', { detail: dialog }))
}

async function addChapter() {
  if (!newChapterName.value) return
  chapterSaving.value = true
  error.value = ''
  try {
    const created = await createChapter(props.token, bankId.value, { name: newChapterName.value })
    chapters.value.push(created)
    newChapterName.value = ''
    flashSuccess(t('ep.manage.chapter_added'))
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    chapterSaving.value = false
  }
}

function startChapterEdit(chapter) {
  editingChapterId.value = chapter.id
  chapterDraft.value = chapter.name
}

function cancelChapterEdit() {
  editingChapterId.value = ''
  chapterDraft.value = ''
}

async function saveChapter(chapter) {
  if (!chapterDraft.value) return
  chapterSaving.value = true
  error.value = ''
  try {
    const updated = await updateChapter(props.token, bankId.value, chapter.id, {
      name: chapterDraft.value,
      parent_id: chapter.parent_id ?? null,
    })
    const idx = chapters.value.findIndex(c => c.id === chapter.id)
    if (idx !== -1) chapters.value[idx] = { ...chapters.value[idx], ...updated }
    cancelChapterEdit()
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    chapterSaving.value = false
  }
}

async function removeChapter(chapter) {
  if (!window.confirm(t('ep.manage.chapter_delete_confirm', { name: chapter.name }))) return
  error.value = ''
  try {
    await deleteChapter(props.token, bankId.value, chapter.id)
    chapters.value = chapters.value.filter(c => c.id !== chapter.id)
    for (const q of questions.value) {
      if (q.chapter_id === chapter.id) q.chapter_id = ''
    }
    if (filters.value.chapterId === chapter.id) filters.value.chapterId = ''
  } catch (err) {
    error.value = err.detail || err.message
  }
}

async function loadData() {
  if (!bankId.value) return
  loading.value = true
  error.value = ''
  try {
    const [bankRes, questionsRes, chaptersRes, membersRes, banksRes] = await Promise.all([
      getBank(props.token, bankId.value),
      listBankQuestionsContent(props.token, bankId.value, { includeArchived: showArchived.value }),
      listChapters(props.token, bankId.value).catch(() => []),
      listBankMembers(props.token, bankId.value).catch(() => []),
      listBanks(props.token).catch(() => []),
    ])
    bank.value = bankRes
    questions.value = Array.isArray(questionsRes) ? questionsRes : []
    chapters.value = Array.isArray(chaptersRes) ? chaptersRes : []
    members.value = Array.isArray(membersRes) ? membersRes : []
    banks.value = Array.isArray(banksRes) ? banksRes : (banksRes?.banks || [])
    hasActiveExam.value = Boolean(bankRes?.locked_by_active_exam || bankRes?.has_active_exam || questions.value.some(q => q.locked_by_active_exam))
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.manage-page { padding-top: 24px; }
.link-btn { border: 0; background: none; padding: 0; color: var(--ink-3); font: inherit; cursor: pointer; }
.link-btn:hover { color: var(--brand); }
.bank-sub { display: flex; flex-wrap: wrap; gap: 14px; }
.manage-notice { margin-top: 14px; }
.manage-tabs { margin-top: 18px; }
.manage-workspace { margin-top: 0; }
.manage-toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 0; border-bottom: 1px solid var(--line);
}
.bank-manage-toolbar { border-top: 1px solid var(--ink); }
.manage-toolbar .search-box { min-width: 220px; flex: 1 1 260px; }
.manage-toolbar .select { height: 32px; font-size: 12px; }
.small { font-size: 12px; }
.bad-text { color: var(--bad); }
.archived-toggle { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-3); cursor: pointer; }

.batch-bar {
  display: flex; flex-direction: column; gap: 10px;
  margin-top: 12px; padding: 12px 14px;
  border: 1px solid var(--line-strong); background: var(--surface-2);
  min-width: 0;
}
.batch-bar-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.batch-title { font-size: 12.5px; font-weight: 600; color: var(--ink); }
.batch-controls { display: flex; align-items: center; gap: 10px 16px; flex-wrap: wrap; }
.batch-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-width: 0; }
.batch-group .select { max-width: 180px; }
.batch-group .input { width: 190px; max-width: 100%; }

.mtable-wrap { overflow-x: auto; }
.mtable { width: 100%; border-collapse: collapse; table-layout: fixed; }
.mtable th.select-cell,
.mtable td.select-cell { width: 36px; padding: 0 4px; text-align: center; }
.mtable th.select-cell input,
.mtable td.select-cell input { width: 14px; height: 14px; cursor: pointer; }
.mtable-row.is-archived { opacity: .68; }
.mtable th {
  padding: 9px 10px; text-align: left;
  font-size: 12px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase;
  color: var(--ink-3); border-bottom: 1px solid var(--line); white-space: nowrap;
}
.mtable td { padding: 0 10px; height: 44px; border-bottom: 1px solid var(--line); font-size: 12px; color: var(--ink-2); vertical-align: middle; }
.mtable-row { cursor: pointer; }
.mtable-row:hover { background: var(--surface-2); }
.bank-manage-table .bank-manage-col-id { width: 78px; }
.bank-manage-table .bank-manage-col-stem { width: auto; }
.bank-manage-table .bank-manage-col-type { width: 88px; }
.bank-manage-table .bank-manage-col-chapter { width: 136px; }
.bank-manage-table .bank-manage-col-difficulty { width: 86px; }
.bank-manage-table .bank-manage-col-version { width: 62px; }
.bank-manage-table .bank-manage-col-actions { width: 76px; }
.id-cell { color: var(--ink-4); font-size: 12px; letter-spacing: .02em; white-space: nowrap; }
.stem-cell { line-height: 1.5; }
.stem-text { display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; color: var(--ink); }
.row-tags { display: inline-flex; gap: 4px; margin-left: 8px; vertical-align: middle; }
.row-tags .tag { font-size: 12px; height: 17px; padding: 0 5px; }
.dim-cell { color: var(--ink-3); }
.small.dim { white-space: nowrap; }

.manage-single { max-width: 860px; }
.tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 0 4px; }
.tag-count { margin-left: 5px; color: var(--ink-4); font-size: 12px; }
.chapter-add { display: flex; gap: 8px; padding: 12px 0 2px; border-top: 1px solid var(--line); }
.chapter-add .input { max-width: 280px; }
.chapter-row .chapter-input { max-width: 320px; }
.member-form { display: flex; gap: 8px; padding: 4px 0 2px; }
.member-form .input { flex: 1; }
.member-form .select { width: 140px; }

.manage-create { width: min(100%, 640px); }
.create-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.create-options { margin: 4px 0 8px; }
.create-options-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.create-opt-row { display: flex; align-items: center; gap: 7px; margin-top: 6px; }
.opt-key-btn {
  width: 30px; height: 30px; flex: none; border: 1px solid var(--line-strong);
  background: none; color: var(--ink-2); cursor: pointer; font-size: 12px;
}
.opt-key-btn.is-on { background: var(--brand); border-color: var(--brand); color: var(--brand-contrast); }

@media (max-width: 900px) {
  .mtable { min-width: 800px; }
  .create-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 1180px) {
  .bank-manage-table .bank-manage-col-id { width: 62px; }
  .bank-manage-table .bank-manage-col-type { width: 76px; }
  .bank-manage-table .bank-manage-col-chapter { width: 112px; }
  .bank-manage-table .bank-manage-col-difficulty { width: 72px; }
  .bank-manage-table .bank-manage-col-version { width: 56px; }
  .bank-manage-table .bank-manage-col-actions { width: 64px; }
  .bank-manage-table th,
  .bank-manage-table td { padding-left: 8px; padding-right: 8px; }
  .bank-manage-table .stem-text { font-size: 12.5px; }
}
@media (max-width: 640px) {
  .manage-head .page-actions { width: 100%; }
  .manage-head .page-actions .btn { flex: 1 1 auto; justify-content: center; }
  .manage-tabs { gap: 16px; overflow-x: auto; flex-wrap: nowrap; }
  .manage-tabs .tab { white-space: nowrap; }
  .manage-toolbar .search-box { flex-basis: 100%; }
  .archived-toggle { flex-basis: 100%; }
  .batch-controls { flex-direction: column; align-items: stretch; }
  .batch-group { width: 100%; }
  .batch-group .select,
  .batch-group .input { flex: 1 1 auto; width: auto; max-width: none; }
  .batch-group .btn { flex: 0 0 auto; }
  .member-form { flex-wrap: wrap; }
  .member-form .input { flex-basis: 100%; }
  .create-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
