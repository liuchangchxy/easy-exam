<template>
  <AccessDeniedState v-if="accessError" :kind="accessError" @back="goToBankList" />
  <div v-else class="manage-page">
    <div class="page-head manage-head">
      <div class="page-head-main">
        <h1 class="page-title">{{ bank?.name || (loadFailed ? t('ep.common.load_failed') : t('ep.common.loading')) }}</h1>
        <p class="page-sub bank-sub">
          <span v-if="bank?.category">{{ bank.category }}</span>
          <span>{{ t('ep.banks.questions', { count: questions.length }) }}</span>
        </p>
      </div>
      <div class="page-actions">
        <button
          type="button"
          class="btn btn-primary"
          data-testid="bank-practice"
          :disabled="!practicableCount || startingPractice"
          @click="startPractice"
        >
          <LinearIcon name="play" :size="14" />
          {{ startingPractice ? t('ep.common.starting') : t('ep.banks.practice') }}
        </button>
        <button v-if="canEdit" type="button" class="btn" data-testid="manage-import" @click="router.push(`/import?bankId=${bankId}`)">
          <LinearIcon name="upload" :size="14" />{{ t('ep.common.import') }}
        </button>
        <button type="button" class="btn" data-testid="manage-export" @click="focusExportPanel">
          <LinearIcon name="download" :size="14" />{{ t('ep.manage.export') }}
        </button>
        <button type="button" class="btn" data-testid="manage-create" :disabled="!canEdit" :title="canEdit ? '' : t('ep.manage.readonly_note')" @click="openCreate">
          <LinearIcon name="plus" :size="14" />{{ t('ep.manage.new_question') }}
        </button>
      </div>
    </div>

    <div v-if="practiceError" class="notice bad manage-notice" role="alert">
      <LinearIcon name="alert" :size="15" /><span>{{ practiceError }}</span>
    </div>

    <div v-if="hasActiveExam" class="notice warn manage-notice">
      <LinearIcon name="lock" :size="15" />
      <span><strong>{{ t('ep.manage.locked_title') }}</strong> {{ t('ep.manage.locked_desc') }}</span>
    </div>
    <div v-if="bank && !canEdit" class="notice info manage-notice">
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
    <div v-if="error && !loadFailed" class="notice bad manage-notice">
      <LinearIcon name="alert" :size="15" /><span>{{ error }}</span>
      <button type="button" class="btn btn-sm btn-quiet" data-testid="error-retry" @click="retryLastAction">{{ t('ep.common.retry') }}</button>
    </div>

    <div ref="tabsRef" class="tabs manage-tabs" role="tablist" @keydown="onTabKeydown">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab"
        role="tab"
        :class="{ 'is-active': activeTab === tab.key }"
        :aria-selected="activeTab === tab.key ? 'true' : 'false'"
        :tabindex="activeTab === tab.key ? 0 : -1"
        @click="setActiveTab(tab.key)"
      >
        {{ t(tab.label) }}<span v-if="tab.count != null" class="count">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="loading" class="skeleton-rows"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>

    <div v-else-if="loadFailed" class="empty" data-testid="load-error" role="alert">
      <div class="empty-mark"><LinearIcon name="alert" :size="24" /></div>
      <div class="empty-title">{{ t('ep.common.load_failed') }}</div>
      <div class="empty-desc">{{ error }}</div>
      <div class="empty-actions">
        <button type="button" class="btn" data-testid="load-retry" @click="loadData">{{ t('common.retry') }}</button>
      </div>
    </div>

    <template v-else>
      <!-- Questions workspace -->
      <section v-if="activeTab === 'questions'" class="manage-workspace">
        <div v-if="showArchived" class="notice info manage-archived-note">
          <LinearIcon name="archive" :size="15" />
          <span>{{ t('ep.manage.archived_note') }}</span>
        </div>
        <div class="manage-toolbar bank-manage-toolbar">
          <div class="search-box">
            <LinearIcon name="search" :size="15" />
            <input v-model.trim="filters.keyword" class="input" :placeholder="t('ep.manage.search')" :aria-label="t('ep.manage.search')" />
          </div>
          <select v-model="filters.type" class="select" :aria-label="t('ep.manage.filter_type')">
            <option value="">{{ t('ep.manage.filter_type') }}</option>
            <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
            <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
            <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
            <option value="FILL">{{ t('ep.question_types.fill') }}</option>
            <option value="ESSAY">{{ t('ep.question_types.essay') }}</option>
          </select>
          <select v-if="chapters.length" v-model="filters.chapterId" class="select" :aria-label="t('ep.manage.filter_chapter')">
            <option value="">{{ t('ep.manage.filter_chapter') }}</option>
            <option v-for="c in chapters" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-model="filters.difficulty" class="select" :aria-label="t('ep.manage.filter_difficulty')">
            <option value="">{{ t('ep.manage.filter_difficulty') }}</option>
            <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <select v-if="allTags.length" v-model="filters.tag" class="select" :aria-label="t('ep.manage.filter_tag')">
            <option value="">{{ t('ep.manage.filter_tag') }}</option>
            <option v-for="tag in allTags" :key="tag" :value="tag">{{ tag }}</option>
          </select>
          <span class="toolbar-divider" aria-hidden="true"></span>
          <label class="toolbar-field">
            <span class="toolbar-field-label">{{ t('ep.manage.filter_sort_label') }}</span>
            <select v-model="questionSort" class="select" data-testid="question-sort" :aria-label="t('ep.manage.filter_sort_label')">
              <option value="default">{{ t('ep.manage.sort_default') }}</option>
              <option value="id">{{ t('ep.manage.sort_id') }}</option>
              <option value="difficulty">{{ t('ep.manage.sort_difficulty') }}</option>
              <option value="updated">{{ t('ep.manage.sort_updated') }}</option>
            </select>
          </label>
          <button v-if="hasActiveReset" type="button" class="btn btn-sm btn-quiet" @click="resetFilters">{{ t('ep.manage.reset') }}</button>
          <div class="spacer"></div>
          <label v-if="canEdit" class="select-all-toggle">
            <input
              type="checkbox"
              data-testid="select-all"
              :checked="allVisibleSelected"
              :aria-label="t('ep.manage.select_all')"
              @change="toggleSelectAll($event.target.checked)"
            />
            <span>{{ t('ep.manage.select_all') }}</span>
            <span class="small dim mono">{{ t('ep.manage.select_scope', { total: filteredQuestions.length, selected: selectedIds.size }) }}</span>
          </label>
          <label class="archived-toggle">
            <input v-model="showArchived" type="checkbox" data-testid="show-archived" @change="onArchivedToggle" />
            <span>{{ t('ep.manage.show_archived') }}</span>
          </label>
          <span v-if="questionsLoading" class="small dim">{{ t('ep.manage.archived_updating') }}</span>
          <span class="small dim mono">{{ t('ep.manage.shown', { shown: filteredQuestions.length, total: questions.length }) }}</span>
        </div>

        <div v-if="canEdit && selectedIds.size" class="batch-bar">
          <div class="batch-bar-head">
            <span class="batch-title">{{ t('ep.manage.batch_title') }}</span>
            <span class="small dim">{{ t('ep.manage.selected_count', { count: selectedIds.size }) }}</span>
            <button type="button" class="btn btn-sm btn-quiet" @click="clearSelection">{{ t('ep.manage.clear_selection') }}</button>
          </div>
          <div class="batch-controls">
            <template v-if="!showArchived">
              <div class="batch-group">
                <select v-model="batchChapterId" class="select" data-testid="batch-chapter" :aria-label="t('ep.manage.batch_chapter_label')" :disabled="batchBusy || batchBlocked">
                  <option value="" disabled>{{ t('ep.manage.batch_chapter_placeholder') }}</option>
                  <option v-for="c in chapters" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
                <button type="button" class="btn btn-sm" data-testid="batch-apply-chapter" :disabled="batchBusy || batchBlocked || !batchChapterId" @click="runBatch('chapter')">
                  {{ t('ep.manage.batch_apply_chapter') }}
                </button>
                <button type="button" class="btn btn-sm btn-quiet" data-testid="batch-clear-chapter" :disabled="batchBusy || batchBlocked" @click="clearBatchChapter">
                  {{ t('ep.manage.batch_chapter_clear_action') }}
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
              <div v-else-if="banksError" class="batch-group" data-testid="batch-targets-error" role="alert">
                <span class="small bad-text">{{ t('ep.common.load_failed') }}</span>
                <button type="button" class="btn btn-sm btn-quiet" data-testid="batch-targets-retry" @click="reloadBanks">{{ t('ep.common.retry') }}</button>
              </div>
              <span v-else class="small dim">{{ t('ep.manage.batch_no_target') }}</span>
              <button type="button" class="btn btn-sm btn-quiet" data-testid="batch-archive" :disabled="batchBusy || batchBlocked" @click="archiveSelected">
                {{ t('ep.manage.batch_archive') }}
              </button>
            </template>
            <button v-else type="button" class="btn btn-sm" data-testid="batch-restore" :disabled="batchBusy || batchBlocked" @click="restoreSelected">
              {{ t('ep.manage.batch_restore') }}
            </button>
          </div>
          <p v-if="batchBlocked" class="hint bad-text">{{ t('ep.manage.batch_locked_hint') }}</p>
          <p v-if="batchError" class="error">{{ batchError }}</p>
        </div>

        <div v-if="filteredQuestions.length" class="mtable-wrap" :class="{ 'is-busy': questionsLoading }" :aria-busy="questionsLoading ? 'true' : 'false'">
          <table class="mtable bank-manage-table">
            <thead>
              <tr>
                <th v-if="canEdit" class="select-cell" aria-hidden="true"></th>
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
              <tr v-for="q in pagedQuestions" :key="q.id" class="mtable-row" :class="{ 'is-archived': q.archived }">
                <td v-if="canEdit" class="select-cell" @click.stop>
                  <label class="select-hit">
                    <input
                      type="checkbox"
                      class="row-select"
                      :data-question-id="q.id"
                      :checked="selectedIds.has(q.id)"
                      :aria-label="t('ep.manage.select_question')"
                      @change="toggleRowSelection(q.id)"
                    />
                  </label>
                </td>
                <td class="mono id-cell bank-manage-col-id">{{ questionCode(q.id) }}</td>
                <td class="stem-cell bank-manage-col-stem">
                  <router-link
                    class="stem-text stem-link"
                    :to="{ name: 'question', params: { bankId, questionId: q.id } }"
                  >{{ stripHtml(q.stem) }}</router-link>
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
                  <button type="button" class="btn btn-sm btn-quiet" data-testid="row-edit" @click.stop="openEdit(q)">
                    {{ rowEditable(q) ? t('ep.manage.edit') : t('ep.manage.view') }}
                  </button>
                  <button
                    v-if="canEdit && !q.locked_by_active_exam"
                    type="button"
                    class="btn btn-sm btn-quiet row-archive-btn"
                    data-testid="row-archive"
                    :aria-label="q.archived ? t('ep.manage.restore') : t('ep.manage.archive')"
                    :title="q.archived ? t('ep.manage.restore') : t('ep.manage.archive')"
                    @click.stop="toggleQuestionArchive(q)"
                  >
                    <LinearIcon :name="q.archived ? 'rotate-ccw' : 'archive'" :size="13" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="filteredQuestions.length" class="mtable-foot">
          <span class="small dim mono">{{ pageInfoText }}</span>
          <span class="list-side">
            <label class="page-size">
              <span class="page-size-label">{{ t('ep.manage.page_size') }}</span>
              <select class="select page-size-select" data-testid="page-size" :value="pageSize" @change="changePageSize">
                <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ t('ep.manage.page_size_unit', { size }) }}</option>
              </select>
            </label>
            <button type="button" class="btn btn-sm btn-quiet" :disabled="pageState.page <= 1" @click="goPage(pageState.page - 1)">{{ t('ep.manage.prev_page') }}</button>
            <button type="button" class="btn btn-sm btn-quiet" :disabled="pageState.page >= pageState.pages" @click="goPage(pageState.page + 1)">{{ t('ep.manage.next_page') }}</button>
          </span>
        </div>

        <div v-else class="empty">
          <div class="empty-mark"><LinearIcon name="layers" :size="24" /></div>
          <div class="empty-title">{{ emptyState.title }}</div>
          <div class="empty-desc">{{ emptyState.hint }}</div>
          <div class="empty-actions">
            <button v-if="canEdit" type="button" class="btn" @click="openCreate">{{ t('ep.manage.new_question') }}</button>
            <button v-if="canEdit" type="button" class="btn" @click="router.push(`/import?bankId=${bankId}`)">{{ t('ep.common.import') }}</button>
            <button v-if="hasActiveReset" type="button" class="btn btn-quiet" @click="resetFilters">{{ t('ep.manage.reset') }}</button>
          </div>
        </div>
      </section>

      <!-- Structure -->
      <section v-else-if="activeTab === 'structure'" class="manage-single">
        <div class="section-note" style="margin-bottom: 12px">{{ t('ep.manage.structure_note') }}</div>
        <div class="panel">
          <div v-if="chaptersError && !chapterTree.length" class="empty" style="padding: 26px 0" data-testid="chapters-error" role="alert">
            <div class="empty-title">{{ t('ep.common.load_failed') }}</div>
            <div class="empty-desc">{{ chaptersError }}</div>
            <div class="empty-actions">
              <button type="button" class="btn btn-sm" data-testid="chapters-retry" @click="reloadChapters">{{ t('ep.common.retry') }}</button>
            </div>
          </div>
          <div v-else-if="chapterTree.length" class="list">
            <template v-for="c in chapterTree" :key="c.id">
              <div
                class="list-row chapter-row"
                :style="{ paddingLeft: `${c.depth * 22}px` }"
              >
                <template v-if="editingChapterId === c.id">
                  <input v-model.trim="chapterDraft" class="input chapter-input" :placeholder="t('ep.manage.chapter_name_placeholder')" />
                  <select v-model="chapterParentDraft" class="select">
                    <option value="">{{ t('ep.manage.chapter_root') }}</option>
                    <option v-for="opt in chapterParentOptions(c.id)" :key="opt.id" :value="opt.id">{{ opt.name }}</option>
                  </select>
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
                    <button type="button" class="btn btn-sm btn-quiet" @click="startChildChapter(c)">{{ t('ep.manage.chapter_add_child') }}</button>
                    <button type="button" class="btn btn-sm btn-quiet" :disabled="!canMoveChapter(c, 'up')" @click="moveChapter(c, 'up')">{{ t('ep.manage.move_up') }}</button>
                    <button type="button" class="btn btn-sm btn-quiet" :disabled="!canMoveChapter(c, 'down')" @click="moveChapter(c, 'down')">{{ t('ep.manage.move_down') }}</button>
                    <button type="button" class="btn btn-sm btn-quiet" @click="startChapterEdit(c)">{{ t('ep.banks.chapter_rename') }}</button>
                    <button type="button" class="btn btn-sm btn-danger" @click="removeChapter(c)">{{ t('ep.manage.chapter_delete') }}</button>
                  </span>
                </template>
              </div>
              <form
                v-if="canEdit && childParentId === c.id"
                class="child-chapter-form"
                :style="{ paddingLeft: `${c.depth * 22 + 10}px` }"
                @submit.prevent="addChildChapter"
              >
                <input
                  v-model.trim="childChapterName"
                  class="input"
                  :placeholder="t('ep.manage.chapter_add_child_placeholder')"
                  :aria-label="t('ep.manage.chapter_add_child_placeholder')"
                  @keydown.esc.prevent="cancelChildChapter"
                />
                <button type="submit" class="btn btn-sm" :disabled="chapterSaving || !childChapterName">{{ t('ep.banks.chapter_add') }}</button>
                <button type="button" class="btn btn-sm btn-quiet" @click="cancelChildChapter">{{ t('ep.common.cancel') }}</button>
              </form>
            </template>
          </div>
          <div v-else class="empty" style="padding: 26px 0">
            <div class="empty-desc">{{ t('ep.banks.chapter_empty') }}</div>
          </div>
          <form v-if="canEdit" class="chapter-add" @submit.prevent="addChapter">
            <input v-model.trim="newChapterName" class="input" :placeholder="t('ep.manage.chapter_name_placeholder')" />
            <select v-model="newChapterParentId" class="select">
              <option value="">{{ t('ep.manage.chapter_root') }}</option>
              <option v-for="c in chapterTree" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
            <button type="submit" class="btn btn-sm" :disabled="chapterSaving || !newChapterName">{{ t('ep.banks.chapter_add') }}</button>
          </form>
        </div>

        <div class="panel" style="margin-top: 24px">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.col_tags') }}</span></div>
          <div class="tag-list">
            <div v-for="tag in tagRows" :key="tag.id" class="tag-row">
              <template v-if="editingTagId === tag.id">
                <input
                  v-model.trim="tag.draft"
                  class="input tag-row-input"
                  :aria-label="t('ep.manage.tag_rename')"
                  @keydown.enter.prevent="renameTag(tag)"
                  @keydown.esc.prevent="cancelTagEdit(tag)"
                />
                <span class="tag-count mono">{{ tag.question_count }}</span>
                <button type="button" class="btn btn-sm" data-testid="tag-save" :disabled="!tag.draft || tag.draft === tag.name" @click="renameTag(tag)">{{ t('ep.manage.tag_save') }}</button>
                <button type="button" class="btn btn-sm btn-quiet" @click="cancelTagEdit(tag)">{{ t('ep.common.cancel') }}</button>
                <button type="button" class="btn btn-sm btn-danger" @click="removeTag(tag)">{{ t('ep.manage.tag_delete') }}</button>
              </template>
              <template v-else>
                <span class="tag-name">{{ tag.name }}</span>
                <span class="tag-count mono">{{ tag.question_count }}</span>
                <template v-if="canEdit">
                  <button type="button" class="btn btn-sm btn-quiet" @click="startTagEdit(tag)">{{ t('ep.manage.tag_rename') }}</button>
                  <button type="button" class="btn btn-sm btn-danger" @click="removeTag(tag)">{{ t('ep.manage.tag_delete') }}</button>
                </template>
              </template>
            </div>
            <div v-if="tagsError && !tagRows.length" class="empty" style="padding: 12px 0" data-testid="tags-error" role="alert">
              <div class="empty-desc">{{ tagsError }}</div>
              <div class="empty-actions">
                <button type="button" class="btn btn-sm" data-testid="tags-retry" @click="reloadTags">{{ t('ep.common.retry') }}</button>
              </div>
            </div>
            <p v-else-if="!tagRows.length" class="hint">{{ t('ep.manage.tag_empty') }}</p>
          </div>
          <form v-if="canEdit" class="tag-add" @submit.prevent="addTag">
            <input v-model.trim="newTagName" class="input" :placeholder="t('ep.manage.tag_placeholder')" />
            <button type="submit" class="btn btn-sm" :disabled="!newTagName">{{ t('ep.manage.tag_add') }}</button>
          </form>
        </div>
      </section>

      <!-- Members -->
      <section v-else-if="activeTab === 'members'" class="manage-single">
        <div class="section-note" style="margin-bottom: 12px">{{ t('ep.manage.members_note') }}</div>
        <p v-if="!isOwner" class="hint" data-testid="owner-members-note">{{ t('ep.manage.owner_members_note') }}</p>
        <div class="panel">
          <div class="list">
            <div v-for="m in members" :key="m.user_id" class="list-row member-row">
              <span class="avatar sm">{{ (m.username || '?').charAt(0).toUpperCase() }}</span>
              <span class="list-main">
                <span class="list-title">{{ m.username }}</span>
                <span class="list-meta">{{ formatRole(m.role) }}</span>
              </span>
              <span v-if="isOwner && m.role !== 'ADMIN'" class="list-side member-actions">
                <select :value="m.role" class="select" :aria-label="t('ep.manage.role_label')" @change="changeMemberRole(m, $event.target.value)">
                  <option value="EDITOR">{{ t('ep.banks.editor') }}</option>
                  <option value="MEMBER">{{ t('ep.banks.member') }}</option>
                </select>
                <button type="button" class="btn btn-sm btn-quiet" @click="transferOwnership(m)">{{ t('ep.manage.transfer_ownership') }}</button>
                <button type="button" class="btn btn-sm btn-quiet" @click="removeMember(m)">{{ t('ep.manage.remove_member') }}</button>
              </span>
            </div>
            <div v-if="membersError && !members.length" class="empty" style="padding: 24px 0" data-testid="members-error" role="alert">
              <div class="empty-desc">{{ membersError }}</div>
              <div class="empty-actions">
                <button type="button" class="btn btn-sm" data-testid="members-retry" @click="reloadMembers">{{ t('ep.common.retry') }}</button>
              </div>
            </div>
            <div v-else-if="!members.length" class="empty" style="padding: 24px 0">
              <div class="empty-desc">{{ t('ep.common.none') }}</div>
            </div>
          </div>
          <div v-if="!isOwner && bank" class="member-leave">
            <button type="button" class="btn btn-sm btn-quiet" @click="leaveCurrentBank">{{ t('ep.manage.leave_bank') }}</button>
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
        </div>
      </section>

      <!-- Imports -->
      <section v-else-if="activeTab === 'imports'" class="manage-single">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.tab_imports') }}</span></div>
          <p class="section-note">{{ t('ep.manage.imports_note') }}</p>
          <p class="section-note" style="margin-top: 6px">{{ t('ep.manage.formats_note') }}</p>
          <div v-if="importJobs.length" class="mtable-wrap" style="margin-top: 14px">
            <table class="mtable import-table">
              <thead>
                <tr>
                  <th>{{ t('ep.manage.import_file') }}</th>
                  <th>{{ t('ep.manage.import_format') }}</th>
                  <th>{{ t('ep.manage.import_status') }}</th>
                  <th>{{ t('ep.manage.import_count') }}</th>
                  <th>{{ t('ep.manage.import_time') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in importJobs" :key="job.id" class="mtable-row import-row">
                  <td class="od-truncate">{{ job.filename || '—' }}</td>
                  <td class="mono">{{ job.format }}</td>
                  <td>
                    <span class="tag" :data-status="job.status" :class="{ ok: job.status === 'IMPORTED', bad: job.status === 'FAILED' || job.status === 'PRECHECK_FAILED' }">{{ importStatusLabel(job.status) }}</span>
                    <span v-if="job.reason" class="hint block">{{ job.reason }}</span>
                  </td>
                  <td class="mono">{{ job.imported_count || 0 }}</td>
                  <td class="mono dim">{{ formatDateTime(job.completed_at || job.created_at, locale) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="importsError" class="empty" style="padding: 18px 0" data-testid="imports-error" role="alert">
            <div class="empty-desc">{{ importsError }}</div>
            <div class="empty-actions">
              <button type="button" class="btn btn-sm" data-testid="imports-retry" @click="reloadImports">{{ t('ep.common.retry') }}</button>
            </div>
          </div>
          <p v-else class="hint" style="margin-top: 14px">{{ t('ep.manage.import_empty') }}</p>
          <div class="empty-actions" style="justify-content: flex-start; margin-top: 18px">
            <button v-if="canEdit" type="button" class="btn btn-primary" @click="router.push(`/import?bankId=${bankId}`)">
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
            <button type="button" class="btn" data-testid="open-local-drafts" @click="showDrafts = true">{{ t('ep.manage.open_drafts') }}</button>
            <button type="button" class="btn btn-quiet" :title="t('ep.manage.ai_configure')" @click="openAiSettings">{{ t('ep.manage.ai_configure') }}</button>
          </div>
        </div>
      </section>

      <!-- Bank settings -->
      <section v-else class="manage-single">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.tab_settings') }}</span></div>
          <p class="section-note">{{ t('ep.manage.settings_note') }}</p>
          <p v-if="!isOwner" class="hint" data-testid="owner-settings-note">{{ t('ep.manage.owner_settings_note') }}</p>
          <form class="form-grid settings-form" @submit.prevent="saveBankSettings">
            <label class="field"><span class="label">{{ t('ep.manage.name_label') }}</span>
              <input v-model.trim="settingsForm.name" class="input" :disabled="!isOwner || settingsSaving" required />
            </label>
            <label class="field"><span class="label">{{ t('ep.manage.category_label') }}</span>
              <input v-model.trim="settingsForm.category" class="input" :disabled="!isOwner || settingsSaving" :placeholder="t('ep.manage.default_category')" />
            </label>
            <label class="field"><span class="label">{{ t('ep.manage.description_label') }}</span>
              <textarea v-model.trim="settingsForm.description" class="textarea" rows="3" :disabled="!isOwner || settingsSaving"></textarea>
            </label>
            <div class="kv">
              <div class="kv-row"><span class="kv-key">{{ t('ep.manage.permission_label') }}</span><span class="kv-val">{{ formatRole(bank?.role) }}</span></div>
              <div class="kv-row"><span class="kv-key">{{ t('ep.manage.locked_meta') }}</span><span class="kv-val">{{ hasActiveExam ? t('ep.manage.locked_title') : t('ep.common.none') }}</span></div>
            </div>
            <div v-if="isOwner" class="empty-actions" style="justify-content: flex-start">
              <button type="submit" class="btn btn-primary" :disabled="settingsSaving || !settingsForm.name">{{ settingsSaving ? t('common.loading') : t('common.save') }}</button>
            </div>
          </form>
        </div>

        <div ref="exportPanelRef" class="panel export-panel" data-testid="export-panel" tabindex="-1" style="margin-top: 24px">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.export') }}</span></div>
          <p class="section-note">{{ t('ep.manage.export_note') }}</p>
          <div class="export-actions">
            <button v-for="fmt in exportFormats" :key="fmt" type="button" class="btn btn-sm" :data-testid="`export-${fmt}`" @click="exportBankFile(fmt)">{{ fmt.toUpperCase() }}</button>
            <label class="archived-toggle">
              <input v-model="exportIncludeArchived" type="checkbox" data-testid="export-include-archived" />
              <span>{{ t('ep.manage.export_include_archived') }}</span>
            </label>
          </div>
        </div>

        <div v-if="isOwner" class="panel danger-zone" style="margin-top: 24px">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.danger_zone') }}</span></div>
          <p class="section-note">{{ t('ep.manage.danger_note') }}</p>
          <div class="empty-actions" style="justify-content: flex-start">
            <button type="button" class="btn danger-btn" data-testid="bank-archive" :disabled="hasActiveExam" @click="archiveCurrentBank">{{ t('ep.manage.archive_bank') }}</button>
          </div>
        </div>

        <div class="panel" style="margin-top: 24px">
          <div class="panel-head"><span class="panel-title">{{ t('ep.manage.audit') }}</span></div>
          <p class="section-note">{{ t('ep.manage.audit_note') }}</p>
          <div v-if="isOwner && auditRows.length" class="audit-list">
            <div v-for="row in auditRows" :key="row.id" class="audit-row" :data-action="row.action">
              <span class="mono small dim">{{ formatDateTime(row.created_at, locale) }}</span>
              <span class="mono">{{ auditActionLabel(row.action) }}</span>
              <span class="small dim od-truncate">{{ auditSummary(row) }}</span>
            </div>
          </div>
          <p v-else-if="isOwner" class="hint">{{ t('ep.manage.audit_empty') }}</p>
          <p v-else class="hint" data-testid="audit-owner-note">{{ t('ep.manage.audit_owner_only') }}</p>
        </div>
      </section>
    </template>

    <!-- Create question -->
    <AppDialog
      :open="showCreate"
      :title="t('ep.manage.create_title')"
      panel-class="manage-create"
      :close-on-backdrop="false"
      initial-focus="#create-stem"
      @close="requestCreateClose"
    >
      <p class="hint">{{ t('ep.manage.create_desc') }}</p>
      <form id="manage-create-form" class="create-form" @submit.prevent="saveQuestion">
        <label>{{ t('ep.manage.stem') }}
          <textarea id="create-stem" v-model.trim="createForm.stem" rows="3" :placeholder="t('ep.manage.stem_placeholder')" required></textarea>
        </label>
        <div class="create-grid">
          <label>{{ t('ep.manage.type') }}
            <select v-model="createForm.type" @change="onTypeChange">
              <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
              <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
              <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
              <option value="FILL">{{ t('ep.question_types.fill') }}</option>
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

        <div v-if="!['ESSAY', 'FILL'].includes(createForm.type)" class="create-options">
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
            <button v-if="createForm.type !== 'JUDGE' && createForm.options.length > 2" type="button" class="icon-btn" :aria-label="t('ep.manage.remove_option')" @click="removeOption(idx)">
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
      </form>
      <template #foot>
        <button type="button" class="btn btn-quiet" :disabled="creating" @click="requestCreateClose">{{ t('ep.manage.cancel') }}</button>
        <button type="submit" form="manage-create-form" class="btn btn-primary" :disabled="creating || !createForm.stem || !createForm.answer">
          {{ creating ? t('ep.manage.saving') : t('ep.manage.save_question') }}
        </button>
      </template>
    </AppDialog>

    <AppDialog
      :open="createDiscardOpen"
      :title="t('ep.common.unsaved_title')"
      panel-class="create-discard-dialog"
      style="--app-dialog-width: 420px"
      initial-focus=".create-discard-keep"
      @close="cancelCreateDiscard"
    >
      <p class="hint">{{ t('ep.common.unsaved_desc') }}</p>
      <template #foot>
        <button type="button" class="btn btn-quiet create-discard-keep" @click="cancelCreateDiscard">{{ t('ep.common.keep_editing') }}</button>
        <button type="button" class="btn create-discard-accept" @click="acceptCreateDiscard">{{ t('ep.common.discard') }}</button>
      </template>
    </AppDialog>

    <AiDraftsModal
      v-if="showDrafts"
      :token="token"
      :bank-id="bankId"
      @close="showDrafts = false"
    />

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

    <StartStudyPanel
      :show="showStartStudyPanel"
      :sessions="startStudySessions"
      :busy="startingPractice"
      @continue="handleStartStudyContinue"
      @end-and-start="handleStartStudyEndAndStart"
      @cancel="handleStartStudyCancel"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import AppDialog from '../components/AppDialog.vue'
import StartStudyPanel from '../components/StartStudyPanel.vue'
import AiDraftsModal from '../components/AiDraftsModal.vue'
import QuestionEditModal from '../components/QuestionEditModal.vue'
import AccessDeniedState from '../components/AccessDeniedState.vue'
import {
  getBank,
  listBanks,
  listBankQuestionsContent,
  listChapters,
  listBankMembers,
  addBankMember,
  removeBankMember,
  updateBankMemberRole,
  leaveBank,
  transferBankOwnership,
  createChapter,
  updateChapter,
  deleteChapter,
  reorderChapters,
  createQuestion,
  batchBankQuestions,
  updateBank,
  deleteBank,
  listBankAudit,
  listBankImports,
  listTags,
  createTag,
  updateTag,
  deleteTag,
  downloadBankExport,
} from '../api/banks'
import { useLocale } from '../composables/useLocale'
import { useDirtyGuard } from '../composables/useDirtyGuard'
import { useStartStudy } from '../composables/useStartStudy.js'
import { formatDateTime } from '../utils/datetime.js'
import { readStoredBankListQuery } from '../utils/bankListQuery.js'
import { notifyBanksChanged } from '../utils/shellEvents.js'
import { readQueryEnum, readQueryNumber, readQueryString, replaceQueryState } from '../utils/routeQuery.js'
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
  flattenChapterTree,
  buildChapterReorderPayload,
  paginateList,
  sortQuestionList,
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
const { t, locale } = useLocale()

const TAB_KEYS = ['questions', 'structure', 'members', 'imports', 'drafts', 'settings']
const PAGE_SIZE_OPTIONS = [25, 50, 75, 100]
const PAGE_SIZE_STORAGE_KEY = 'easyexam.bankManage.pageSize'
const QUESTION_TYPES = ['SINGLE', 'MULTI', 'JUDGE', 'FILL', 'ESSAY']
const QUESTION_SORTS = ['default', 'id', 'difficulty', 'updated']

// The question list is a view people refresh, bookmark and share, so every
// filter it shows lives in the address. Defaults stay out of the URL.
const WORKSPACE_QUERY_DEFAULTS = {
  q: '',
  type: '',
  difficulty: '',
  tag: '',
  chapter: '',
  sort: 'default',
  page: 1,
}

function readFiltersFromQuery(query) {
  const rawDifficulty = readQueryString(query?.difficulty)
  const difficulty = rawDifficulty ? Math.min(5, Math.max(1, Number(rawDifficulty) || 0)) : ''
  return {
    ...createEmptyBankFilters(),
    keyword: readQueryString(query?.q),
    type: readQueryEnum(query?.type, QUESTION_TYPES, ''),
    difficulty: difficulty || '',
    tag: readQueryString(query?.tag),
    chapterId: readQueryString(query?.chapter),
  }
}

function normalizeSort(value) {
  return readQueryEnum(value, QUESTION_SORTS, 'default')
}

function normalizeTab(value) {
  const raw = Array.isArray(value) ? value[0] : value
  return TAB_KEYS.includes(raw) ? raw : 'questions'
}

function readStoredPageSize() {
  try {
    const parsed = Number(globalThis.localStorage?.getItem(PAGE_SIZE_STORAGE_KEY))
    return PAGE_SIZE_OPTIONS.includes(parsed) ? parsed : PAGE_SIZE_OPTIONS[0]
  } catch {
    return PAGE_SIZE_OPTIONS[0]
  }
}

const bankId = computed(() => route.params.bankId)

function readArchivedQuery(value) {
  const raw = Array.isArray(value) ? value[0] : value
  return raw === '1' || raw === 1 || raw === true || raw === 'true'
}

const bank = ref(null)
const questions = ref([])
const chapters = ref([])
const members = ref([])
const banks = ref([])
const hasActiveExam = ref(false)
const loading = ref(true)
const loadFailed = ref(false)
// 'forbidden' | 'missing' when the bank itself is unreachable (not a member,
// bank gone). Other failures keep the retryable banner.
const accessError = ref('')
const {
  pending: startingPractice,
  error: practiceError,
  clearError: clearPracticeError,
  start: startStudy,
  continueSession: continueStudySession,
  endAndStart: endAndStartStudy,
} = useStartStudy(computed(() => props.token))
const showStartStudyPanel = ref(false)
const startStudySessions = ref([])
const pendingStartStudyPayload = ref(null)
const questionsLoading = ref(false)
const error = ref('')
const successToast = ref('')
const conflictAlert = ref('')
const activeTab = ref(normalizeTab(route.query?.tab))
const tabsRef = ref(null)
const exportPanelRef = ref(null)

const filters = ref(readFiltersFromQuery(route.query))
const activeModalQuestion = ref(null)

const showArchived = ref(readArchivedQuery(route.query?.archived))
const showDrafts = ref(false)
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

const createDirty = computed(() => {
  const form = createForm.value
  if (!form) return false
  return Boolean(
    form.stem
    || form.answer
    || form.explanation
    || form.tags
    || (Array.isArray(form.options) && form.options.some(opt => String(opt.content || '').trim()))
  )
})

const {
  confirmDiscard: requestCreateDiscard,
  discardPromptOpen: createDiscardOpen,
  confirmDiscardAccept: acceptCreateDiscard,
  confirmDiscardCancel: cancelCreateDiscard,
} = useDirtyGuard(() => createDirty.value, () => { showCreate.value = false })

const memberForm = ref({ username: '', role: 'EDITOR' })
const memberSaving = ref(false)

const newChapterName = ref('')
const newChapterParentId = ref('')
const editingChapterId = ref('')
const chapterDraft = ref('')
const chapterParentDraft = ref('')
const chapterSaving = ref(false)
const childParentId = ref('')
const childChapterName = ref('')

const questionSort = ref(normalizeSort(route.query?.sort))
const currentPage = ref(readQueryNumber(route.query?.page, 1, { min: 1, max: 100000 }))
const pageSize = ref(readStoredPageSize())
const pageSizeOptions = PAGE_SIZE_OPTIONS

const tagRows = ref([])
const newTagName = ref('')
const editingTagId = ref('')

const importJobs = ref([])
const auditRows = ref([])

// Per-resource load failures. These secondary resources must never collapse
// into an "empty" state: an empty list is a fact, a failed request is not.
const chaptersError = ref('')
const membersError = ref('')
const tagsError = ref('')
const importsError = ref('')
const banksError = ref('')
// Retry hook for the generic error notice (e.g. a failed archived reload).
const retryAction = ref(null)

const settingsForm = ref({ name: '', category: '', description: '' })
const settingsSaving = ref(false)
const exportIncludeArchived = ref(false)
const exportFormats = ['json', 'csv', 'txt', 'xlsx']

const longTimer = ref(null)
// Monotonic request sequence: a response is only applied when no newer
// request (including a bank switch) has started since.
let loadSeq = 0
// Question-list reloads (archived toggle, retry) get their own sequence. They
// must not borrow `loadSeq`, or a reload started while the page is still
// loading would make `loadData`'s finally see a newer sequence and leave the
// skeleton up forever with valid rows behind it.
let questionsSeq = 0

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

const hasActiveReset = computed(() => hasActiveFilters.value || questionSort.value !== 'default')

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

// Practice draws from active rows only; an archived-only view has nothing to practise.
const practicableCount = computed(() => questions.value.filter(q => !q.archived).length)

const emptyState = computed(() => {
  if (!questions.value.length) {
    return showArchived.value
      ? { title: t('ep.manage.archived_empty'), hint: t('ep.manage.archived_empty_hint') }
      : { title: t('ep.manage.empty_bank'), hint: t('ep.manage.empty_bank_hint') }
  }
  return { title: t('ep.manage.no_match'), hint: t('ep.manage.no_match_hint') }
})

const filteredQuestions = computed(() => filterBankQuestions(questions.value, filters.value))

const sortedQuestions = computed(() => sortQuestionList(filteredQuestions.value, questionSort.value))

const pageState = computed(() => paginateList(sortedQuestions.value, currentPage.value, pageSize.value))

const pageInfoText = computed(() => {
  if (hasActiveFilters.value) {
    return t('ep.manage.page_info_filtered', { total: pageState.value.total })
  }
  return t('ep.manage.page_info', {
    page: pageState.value.page,
    pages: pageState.value.pages,
    total: pageState.value.total,
  })
})

const pagedQuestions = computed(() => pageState.value.items)

const chapterTree = computed(() => flattenChapterTree(chapters.value))

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

function goPage(page) {
  currentPage.value = Math.max(1, Number(page) || 1)
}

function changePageSize(event) {
  const next = Number(event?.target?.value)
  if (!PAGE_SIZE_OPTIONS.includes(next)) return
  pageSize.value = next
  currentPage.value = 1
  try {
    globalThis.localStorage?.setItem(PAGE_SIZE_STORAGE_KEY, String(next))
  } catch {
    // storage unavailable (private mode): keep the in-memory choice
  }
}

function setActiveTab(tabKey) {
  if (!TAB_KEYS.includes(tabKey)) return
  activeTab.value = tabKey
  if (route.query?.tab === tabKey) return
  router.replace({ query: { ...(route.query || {}), tab: tabKey } })
}

function focusTab(index) {
  const buttons = tabsRef.value?.querySelectorAll?.('[role="tab"]')
  const target = buttons?.[index]
  if (target && typeof target.focus === 'function') target.focus()
}

// Roving tabindex: only the active tab is in the tab order, and arrows/Home/End
// move both focus and selection so keyboard users can reach every tab.
function onTabKeydown(event) {
  const { key } = event
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return
  event.preventDefault()
  const current = Math.max(0, TAB_KEYS.indexOf(activeTab.value))
  let next = current
  if (key === 'ArrowLeft') next = (current - 1 + TAB_KEYS.length) % TAB_KEYS.length
  else if (key === 'ArrowRight') next = (current + 1) % TAB_KEYS.length
  else if (key === 'Home') next = 0
  else if (key === 'End') next = TAB_KEYS.length - 1
  setActiveTab(TAB_KEYS[next])
  nextTick(() => focusTab(next))
}

function persistArchivedQuery(enabled) {
  const query = { ...(route.query || {}), tab: activeTab.value }
  if (enabled) query.archived = '1'
  else delete query.archived
  router.replace({ query })
}

function scrollActiveTabIntoView() {
  nextTick(() => {
    const active = tabsRef.value?.querySelector?.('.tab.is-active')
    if (active && typeof active.scrollIntoView === 'function') {
      active.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    }
  })
}

watch(() => route.query?.tab, value => {
  activeTab.value = normalizeTab(value)
  scrollActiveTabIntoView()
})

watch(() => route.query?.archived, value => {
  const next = readArchivedQuery(value)
  if (next === showArchived.value) return
  showArchived.value = next
  clearSelection()
  currentPage.value = 1
  reloadQuestions()
})

// Set while the address is writing the controls, so restoring `page` from a
// URL is not immediately undone by the "a new filter starts at page one" rule.
let applyingRoute = false

watch([filters, questionSort, showArchived], () => {
  if (!applyingRoute) currentPage.value = 1
  // A new filter/sort can hide rows that are still selected; the batch bar
  // must never act on rows the user can no longer see.
  clearSelection()
}, { deep: true })

// The workspace view lives in the URL: refresh, bookmark and "send this list
// to a teammate" must all land on the same rows. Defaults are omitted so the
// bare bank URL stays clean.
function persistWorkspaceQuery() {
  replaceQueryState(router, route.query, {
    q: filters.value.keyword,
    type: filters.value.type,
    difficulty: filters.value.difficulty,
    tag: filters.value.tag,
    chapter: filters.value.chapterId,
    sort: questionSort.value,
    page: currentPage.value > 1 ? currentPage.value : '',
  }, WORKSPACE_QUERY_DEFAULTS)
}

watch([filters, questionSort, currentPage], persistWorkspaceQuery, { deep: true })

// Address → state. Browser back/forward and pasted links must drive the
// controls, not just the other way round.
watch(() => [
  route.query?.q,
  route.query?.type,
  route.query?.difficulty,
  route.query?.tag,
  route.query?.chapter,
  route.query?.sort,
  route.query?.page,
], () => {
  const nextFilters = readFiltersFromQuery(route.query)
  const current = filters.value
  const filtersChanged = Object.keys(nextFilters).some(key => String(nextFilters[key] ?? '') !== String(current?.[key] ?? ''))
  const nextSort = normalizeSort(route.query?.sort)
  const nextPage = readQueryNumber(route.query?.page, 1, { min: 1, max: 100000 })
  applyingRoute = true
  if (filtersChanged) filters.value = nextFilters
  if (nextSort !== questionSort.value) questionSort.value = nextSort
  if (nextPage !== currentPage.value) currentPage.value = nextPage
  nextTick(() => { applyingRoute = false })
})

function resetBankScopedState() {
  // Invalidate anything still in flight for the previous bank.
  loadSeq += 1
  questionsSeq += 1
  activeTab.value = normalizeTab(route.query?.tab)
  showArchived.value = readArchivedQuery(route.query?.archived)
  // The address survives a bank switch; the new bank should open on the same
  // filtered view the link asked for, not on an empty one.
  filters.value = readFiltersFromQuery(route.query)
  questionSort.value = normalizeSort(route.query?.sort)
  currentPage.value = readQueryNumber(route.query?.page, 1, { min: 1, max: 100000 })
  clearSelection()
  batchChapterId.value = ''
  batchTags.value = ''
  batchTargetBankId.value = ''
  batchError.value = ''
  error.value = ''
  accessError.value = ''
  practiceError.value = ''
  startingPractice.value = false
  showStartStudyPanel.value = false
  startStudySessions.value = []
  pendingStartStudyPayload.value = null
  successToast.value = ''
  conflictAlert.value = ''
  createError.value = ''
  showCreate.value = false
  activeModalQuestion.value = null
  showDrafts.value = false
  editingChapterId.value = ''
  chapterDraft.value = ''
  chapterParentDraft.value = ''
  childParentId.value = ''
  childChapterName.value = ''
  editingTagId.value = ''
  chaptersError.value = ''
  membersError.value = ''
  tagsError.value = ''
  importsError.value = ''
  banksError.value = ''
  retryAction.value = null
  bank.value = null
  questions.value = []
  chapters.value = []
  members.value = []
  banks.value = []
  tagRows.value = []
  importJobs.value = []
  auditRows.value = []
  hasActiveExam.value = false
  settingsForm.value = { name: '', category: '', description: '' }
}

// The router reuses this component between /banks/A/manage and
// /banks/B/manage, so every bank-scoped bit of state must be reset explicitly.
watch(() => route.params?.bankId, (nextId, prevId) => {
  if (!nextId || nextId === prevId) return
  resetBankScopedState()
  loadData()
})

function toggleSelectAll(checked) {
  selectedIds.value = toggleVisibleSelection(selectedIds.value, visibleQuestionIds.value, checked)
}

function clearSelection() {
  selectedIds.value = createSelection()
}

function onArchivedToggle() {
  const next = showArchived.value
  return applyArchivedChange(next, !next)
}

async function applyArchivedChange(next, revertTo) {
  showArchived.value = next
  clearSelection()
  currentPage.value = 1
  const result = await reloadQuestions()
  if (result === 'error') {
    // The rows on screen are still the previous view. Never leave the toggle
    // claiming a filter that was never fetched successfully.
    showArchived.value = revertTo
    retryAction.value = () => applyArchivedChange(next, revertTo)
    return result
  }
  // Persist only after the matching rows arrived, so a failed toggle never
  // rewrites the URL to a view that was not loaded.
  if (result === 'ok') persistArchivedQuery(next)
  retryAction.value = null
  return result
}

async function retryLastAction() {
  const action = retryAction.value
  retryAction.value = null
  if (action) await action()
  else await loadData()
}

// A filter whose facet disappeared (chapter deleted, last tagged question
// archived) would keep narrowing the list with no control left to undo it.
// Only prune against facets that actually loaded; a failed chapter request
// knows nothing about which chapters exist.
function pruneStaleFacetFilters() {
  if (filters.value.tag && !allTags.value.includes(filters.value.tag)) {
    filters.value.tag = ''
  }
  if (filters.value.chapterId && !chaptersError.value
      && !chapters.value.some(c => String(c.id) === String(filters.value.chapterId))) {
    filters.value.chapterId = ''
  }
}

async function reloadQuestions() {
  if (!bankId.value) return 'stale'
  const targetBankId = bankId.value
  const requestId = ++questionsSeq
  questionsLoading.value = true
  error.value = ''
  try {
    const res = await listBankQuestionsContent(props.token, targetBankId, { includeArchived: showArchived.value })
    if (requestId !== questionsSeq || bankId.value !== targetBankId) return 'stale'
    questions.value = Array.isArray(res) ? res : []
    pruneStaleFacetFilters()
    return 'ok'
  } catch (err) {
    if (requestId !== questionsSeq) return 'stale'
    error.value = err.detail || err.message
    retryAction.value = reloadQuestions
    return 'error'
  } finally {
    if (requestId === questionsSeq) questionsLoading.value = false
  }
}

async function runBatch(operation) {
  if (!canEdit.value || batchBlocked.value) return
  let extras = {}
  if (operation === 'chapter') {
    if (!batchChapterId.value) return
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

async function clearBatchChapter() {
  if (!canEdit.value || batchBlocked.value || !selectedQuestions.value.length) return
  if (!window.confirm(t('ep.manage.batch_chapter_clear_confirm', { count: selectedQuestions.value.length }))) return
  const built = buildBatchRequest('chapter', selectedQuestions.value.map(q => q.id), { chapterId: '' })
  if (built.error) {
    batchError.value = t('ep.manage.batch_failed')
    return
  }
  await sendBatch(built.payload)
}

function selectedByArchived(archived) {
  return selectedQuestions.value.filter(q => Boolean(q.archived) === archived)
}

async function archiveSelected() {
  const targets = selectedByArchived(false)
  if (!canEdit.value || batchBlocked.value || !targets.length) return
  if (!window.confirm(t('ep.manage.batch_archive_confirm', { count: targets.length }))) return
  await sendBatch({ question_ids: targets.map(q => q.id), operation: 'archive' })
}

async function restoreSelected() {
  // With "show archived" on the list mixes both kinds; restoring the active
  // ones would be a silent no-op the success toast still claims to have done.
  const targets = selectedByArchived(true)
  if (!canEdit.value || batchBlocked.value || !targets.length) return
  await sendBatch({ question_ids: targets.map(q => q.id), operation: 'restore' })
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

async function toggleQuestionArchive(question) {
  if (!canEdit.value || !question || question.locked_by_active_exam) return
  const wasArchived = Boolean(question.archived)
  batchBusy.value = true
  batchError.value = ''
  try {
    await batchBankQuestions(props.token, bankId.value, {
      question_ids: [question.id],
      operation: wasArchived ? 'restore' : 'archive',
    })
    await loadData()
    // Archiving with "show archived" off drops the row from the filtered list;
    // never keep a selected id the user can no longer see.
    pruneSelectionToVisible()
    flashSuccess(t(wasArchived ? 'ep.manage.restore_done' : 'ep.manage.archive_done'))
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

const IMPORT_STATUS_KEYS = {
  PENDING: 'ep.manage.import_status_pending',
  PRECHECK_FAILED: 'ep.manage.import_status_precheck_failed',
  IMPORTED: 'ep.manage.import_status_imported',
  FAILED: 'ep.manage.import_status_failed',
}

const AUDIT_ACTION_KEYS = {
  BANK_CREATED: 'ep.manage.audit_bank_created',
  BANK_UPDATED: 'ep.manage.audit_bank_updated',
  BANK_DELETED: 'ep.manage.audit_bank_deleted',
  BANK_RESTORED: 'ep.manage.audit_bank_restored',
  BANK_BATCH: 'ep.manage.audit_bank_batch',
  BANK_CATEGORY_RENAMED: 'ep.manage.audit_bank_category_renamed',
  BANK_CATEGORY_DELETED: 'ep.manage.audit_bank_category_deleted',
  BANK_MEMBER_ADDED: 'ep.manage.audit_bank_member_added',
  BANK_MEMBER_REMOVED: 'ep.manage.audit_bank_member_removed',
  BANK_MEMBER_LEFT: 'ep.manage.audit_bank_member_left',
  BANK_MEMBER_ROLE_CHANGED: 'ep.manage.audit_bank_member_role_changed',
  BANK_OWNER_TRANSFERRED: 'ep.manage.audit_bank_owner_transferred',
  CHAPTER_CREATED: 'ep.manage.audit_chapter_created',
  CHAPTER_UPDATED: 'ep.manage.audit_chapter_updated',
  CHAPTER_DELETED: 'ep.manage.audit_chapter_deleted',
  CHAPTERS_REORDERED: 'ep.manage.audit_chapters_reordered',
  TAG_CREATED: 'ep.manage.audit_tag_created',
  TAG_RENAMED: 'ep.manage.audit_tag_renamed',
  TAG_DELETED: 'ep.manage.audit_tag_deleted',
  TAG_MERGED: 'ep.manage.audit_tag_merged',
}

function humanizeEnum(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const words = raw.replace(/_/g, ' ').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function importStatusLabel(status) {
  const key = IMPORT_STATUS_KEYS[String(status || '').toUpperCase()]
  return key ? t(key) : humanizeEnum(status)
}

function auditActionLabel(action) {
  const key = AUDIT_ACTION_KEYS[String(action || '').toUpperCase()]
  return key ? t(key) : humanizeEnum(action)
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
  questionSort.value = 'default'
}

function openEdit(q) {
  activeModalQuestion.value = q
}

function handleQuestionSaved(updatedQ) {
  if (!updatedQ) return
  const idx = questions.value.findIndex(item => item.id === updatedQ.id)
  if (idx !== -1) questions.value[idx] = updatedQ
  else questions.value.unshift(updatedQ)
  pruneSelectionToVisible()
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
  pruneSelectionToVisible()
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

function requestCreateClose() {
  if (creating.value) return
  requestCreateDiscard()
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
    createForm.value.answer = Array.from(parts).join(',')
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

async function changeMemberRole(member, role) {
  if (!isOwner.value || member.role === role) return
  error.value = ''
  try {
    await updateBankMemberRole(props.token, bankId.value, member.user_id, role)
    member.role = role
    flashSuccess(t('ep.manage.member_updated'))
  } catch (err) {
    error.value = err.detail || err.message
    await loadData()
  }
}

async function transferOwnership(member) {
  if (!window.confirm(t('ep.manage.transfer_confirm', { name: member.username }))) return
  error.value = ''
  try {
    await transferBankOwnership(props.token, bankId.value, member.username)
    await loadData()
    flashSuccess(t('ep.manage.transfer_done'))
  } catch (err) {
    error.value = err.detail || err.message
  }
}

async function leaveCurrentBank() {
  if (!window.confirm(t('ep.manage.leave_confirm', { name: bank.value?.name || '' }))) return
  error.value = ''
  try {
    await leaveBank(props.token, bankId.value)
    router.push('/banks')
  } catch (err) {
    error.value = err.detail || err.message
  }
}

function focusExportPanel() {
  setActiveTab('settings')
  nextTick(() => {
    const el = exportPanelRef.value
    if (!el) return
    if (typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'center', behavior: 'smooth' })
    if (typeof el.focus === 'function') el.focus()
  })
}

function openAiSettings() {
  router.push({ path: '/settings', query: { section: 'ai' } })
}

async function addChapter() {
  if (!newChapterName.value) return
  chapterSaving.value = true
  error.value = ''
  try {
    const created = await createChapter(props.token, bankId.value, {
      name: newChapterName.value,
      parent_id: newChapterParentId.value || null,
    })
    chapters.value.push(created)
    newChapterName.value = ''
    newChapterParentId.value = ''
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
  chapterParentDraft.value = chapter.parent_id || ''
}

function startChildChapter(chapter) {
  childParentId.value = chapter.id
  childChapterName.value = ''
  nextTick(() => {
    const input = document.querySelector('.child-chapter-form .input')
    if (input && typeof input.focus === 'function') input.focus()
  })
}

function cancelChildChapter() {
  childParentId.value = ''
  childChapterName.value = ''
}

async function addChildChapter() {
  if (!childParentId.value || !childChapterName.value) return
  chapterSaving.value = true
  error.value = ''
  try {
    const created = await createChapter(props.token, bankId.value, {
      name: childChapterName.value,
      parent_id: childParentId.value,
    })
    chapters.value.push(created)
    cancelChildChapter()
    flashSuccess(t('ep.manage.chapter_added'))
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    chapterSaving.value = false
  }
}

function cancelChapterEdit() {
  editingChapterId.value = ''
  chapterDraft.value = ''
  chapterParentDraft.value = ''
}

function chapterParentOptions(chapterId) {
  const blocked = new Set([chapterId])
  let changed = true
  while (changed) {
    changed = false
    for (const chapter of chapters.value) {
      if (chapter.parent_id && blocked.has(chapter.parent_id) && !blocked.has(chapter.id)) {
        blocked.add(chapter.id)
        changed = true
      }
    }
  }
  return chapterTree.value.filter(chapter => !blocked.has(chapter.id))
}

async function saveChapter(chapter) {
  if (!chapterDraft.value) return
  chapterSaving.value = true
  error.value = ''
  try {
    const updated = await updateChapter(props.token, bankId.value, chapter.id, {
      name: chapterDraft.value,
      parent_id: chapterParentDraft.value || null,
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

function canMoveChapter(chapter, direction) {
  const siblings = chapterTree.value.filter(c => (c.parent_id || null) === (chapter.parent_id || null))
  const index = siblings.findIndex(c => c.id === chapter.id)
  return direction === 'up' ? index > 0 : index !== -1 && index < siblings.length - 1
}

async function moveChapter(chapter, direction) {
  const built = buildChapterReorderPayload(chapters.value, chapter.id, direction)
  if (built.error) return
  chapterSaving.value = true
  error.value = ''
  try {
    const updated = await reorderChapters(props.token, bankId.value, built.items)
    if (Array.isArray(updated)) chapters.value = updated
    else await loadData()
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

async function addTag() {
  if (!newTagName.value) return
  error.value = ''
  try {
    const name = newTagName.value
    const created = await createTag(props.token, bankId.value, name)
    newTagName.value = ''
    const row = created && typeof created === 'object'
      ? { ...created, name: created.name || name, draft: created.name || name }
      : { id: `local-${Date.now()}`, name, question_count: 0, draft: name }
    tagRows.value = [...tagRows.value, row]
    flashSuccess(t('ep.manage.tag_added'))
  } catch (err) {
    error.value = err.detail || err.message
  }
}

function startTagEdit(tag) {
  editingTagId.value = tag.id
  tag.draft = tag.name
}

function cancelTagEdit(tag) {
  tag.draft = tag.name
  editingTagId.value = ''
}

async function renameTag(tag) {
  if (!tag.draft || tag.draft === tag.name) return
  error.value = ''
  const nextName = tag.draft
  const target = tagRows.value.find(row => row.id !== tag.id && row.name === nextName)
  if (target && !window.confirm(t('ep.manage.tag_merge_confirm', { name: nextName }))) return
  try {
    const updated = await updateTag(props.token, bankId.value, tag.id, nextName)
    if (target) {
      target.question_count = Number(target.question_count || 0) + Number(tag.question_count || 0)
      tagRows.value = tagRows.value.filter(row => row.id !== tag.id)
    } else {
      const idx = tagRows.value.findIndex(row => row.id === tag.id)
      if (idx !== -1) {
        const resolved = updated && typeof updated === 'object' ? updated : {}
        tagRows.value[idx] = { ...tagRows.value[idx], ...resolved, name: resolved.name || nextName, draft: resolved.name || nextName }
      }
    }
    for (const question of questions.value) {
      if (Array.isArray(question.tags) && question.tags.includes(tag.name)) {
        question.tags = question.tags.map(name => (name === tag.name ? nextName : name))
      }
    }
    editingTagId.value = ''
    flashSuccess(t('ep.manage.tag_renamed'))
  } catch (err) {
    error.value = err.detail || err.message
  }
}

async function removeTag(tag) {
  if (!window.confirm(t('ep.manage.tag_delete_confirm', { name: tag.name, count: tag.question_count ?? tagCount(tag.name) }))) return
  error.value = ''
  try {
    await deleteTag(props.token, bankId.value, tag.id)
    tagRows.value = tagRows.value.filter(row => row.id !== tag.id)
    for (const question of questions.value) {
      if (Array.isArray(question.tags)) question.tags = question.tags.filter(name => name !== tag.name)
    }
    if (editingTagId.value === tag.id) editingTagId.value = ''
    flashSuccess(t('ep.manage.tag_deleted'))
  } catch (err) {
    error.value = err.detail || err.message
  }
}

async function saveBankSettings() {
  if (!isOwner.value || !settingsForm.value.name) return
  settingsSaving.value = true
  error.value = ''
  try {
    const payload = {
      name: settingsForm.value.name,
      description: settingsForm.value.description,
    }
    // A blank category means "leave it alone"; writing the localized label in
    // would stamp UI text from one language into every member's bank record.
    if (settingsForm.value.category) payload.category = settingsForm.value.category
    const updated = await updateBank(props.token, bankId.value, payload)
    bank.value = { ...bank.value, ...updated }
    notifyBanksChanged()
    await loadData()
    flashSuccess(t('ep.manage.settings_saved'))
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    settingsSaving.value = false
  }
}

async function exportBankFile(format) {
  error.value = ''
  try {
    await downloadBankExport(props.token, bankId.value, format, exportIncludeArchived.value)
    flashSuccess(t('ep.manage.export_done'))
  } catch (err) {
    error.value = err.detail || err.message
  }
}

async function archiveCurrentBank() {
  if (!isOwner.value || hasActiveExam.value) return
  if (!window.confirm(t('ep.manage.archive_confirm', { name: bank.value?.name || '' }))) return
  error.value = ''
  try {
    await deleteBank(props.token, bankId.value)
    notifyBanksChanged()
    router.push('/banks')
  } catch (err) {
    error.value = err.detail || err.message
  }
}

function pruneSelectionToVisible() {
  const visible = new Set(visibleQuestionIds.value)
  const next = createSelection()
  let changed = false
  for (const id of selectedIds.value) {
    if (visible.has(id)) next.add(id)
    else changed = true
  }
  if (changed) selectedIds.value = next
}

function auditSummary(row) {
  const details = row?.details
  if (!details || typeof details !== 'object') return '—'
  // Audit payloads may nest a `fields` map (BANK_UPDATED) or be flat. Show the
  // changed field names only: readable, short, and never raw JSON.
  const source = details.fields && typeof details.fields === 'object' ? details.fields : details
  const names = Object.entries(source)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key]) => key)
  return names.join(', ') || '—'
}

function resourceErrorMessage(err) {
  return err?.detail || err?.message || t('ep.common.load_failed')
}

async function reloadChapters() {
  const targetBankId = bankId.value
  if (!targetBankId) return
  try {
    const res = await listChapters(props.token, targetBankId)
    if (bankId.value !== targetBankId) return
    chapters.value = Array.isArray(res) ? res : []
    chaptersError.value = ''
  } catch (err) {
    if (bankId.value !== targetBankId) return
    chaptersError.value = resourceErrorMessage(err)
  }
}

async function reloadMembers() {
  const targetBankId = bankId.value
  if (!targetBankId) return
  try {
    const res = await listBankMembers(props.token, targetBankId)
    if (bankId.value !== targetBankId) return
    members.value = Array.isArray(res) ? res : []
    membersError.value = ''
  } catch (err) {
    if (bankId.value !== targetBankId) return
    membersError.value = resourceErrorMessage(err)
  }
}

async function reloadTags() {
  const targetBankId = bankId.value
  if (!targetBankId) return
  try {
    const res = await listTags(props.token, targetBankId)
    if (bankId.value !== targetBankId) return
    tagRows.value = (Array.isArray(res) ? res : []).map(tag => ({ ...tag, draft: tag.name }))
    tagsError.value = ''
  } catch (err) {
    if (bankId.value !== targetBankId) return
    tagsError.value = resourceErrorMessage(err)
  }
}

async function reloadImports() {
  const targetBankId = bankId.value
  if (!targetBankId) return
  try {
    const res = await listBankImports(props.token, targetBankId)
    if (bankId.value !== targetBankId) return
    importJobs.value = Array.isArray(res) ? res : []
    importsError.value = ''
  } catch (err) {
    if (bankId.value !== targetBankId) return
    importsError.value = resourceErrorMessage(err)
  }
}

async function reloadBanks() {
  try {
    const res = await listBanks(props.token)
    banks.value = Array.isArray(res) ? res : (res?.banks || [])
    banksError.value = ''
  } catch (err) {
    banksError.value = resourceErrorMessage(err)
  }
}

async function loadData() {
  if (!bankId.value) return
  const targetBankId = bankId.value
  const requestId = ++loadSeq
  questionsSeq += 1
  // The row list this request will return belongs to the archived mode it was
  // started with. If the view changed while it was in flight (a back/forward
  // that flips ?archived), its rows describe a view the user already left.
  const archivedRequested = showArchived.value
  loading.value = true
  loadFailed.value = false
  error.value = ''
  retryAction.value = null
  try {
    const [bankRes, questionsRes] = await Promise.all([
      getBank(props.token, targetBankId),
      listBankQuestionsContent(props.token, targetBankId, { includeArchived: showArchived.value }),
    ])
    if (requestId !== loadSeq) return
    bank.value = bankRes
    accessError.value = ''
    if (showArchived.value === archivedRequested) {
      questions.value = Array.isArray(questionsRes) ? questionsRes : []
    } else {
      void reloadQuestions()
    }
    settingsForm.value = {
      name: bankRes?.name || '',
      category: bankRes?.category || '',
      description: bankRes?.description || '',
    }
    hasActiveExam.value = Boolean(bankRes?.locked_by_active_exam || bankRes?.has_active_exam || questions.value.some(q => q.locked_by_active_exam))
    // Secondary resources fail independently: one broken endpoint must not
    // blank the whole page or masquerade as an empty list.
    await Promise.all([reloadChapters(), reloadMembers(), reloadTags(), reloadImports(), reloadBanks()])
    if (requestId !== loadSeq) return
    pruneStaleFacetFilters()
    if (isOwner.value) {
      auditRows.value = await listBankAudit(props.token, targetBankId).catch(() => [])
      if (requestId !== loadSeq) return
      auditRows.value = Array.isArray(auditRows.value) ? auditRows.value : []
    } else {
      auditRows.value = []
    }
  } catch (err) {
    if (requestId !== loadSeq) return
    const status = Number(err?.status)
    if (status === 403 || status === 404) {
      accessError.value = status === 403 ? 'forbidden' : 'missing'
      loadFailed.value = false
      error.value = ''
      return
    }
    loadFailed.value = true
    error.value = err.detail || err.message
  } finally {
    if (requestId === loadSeq) loading.value = false
  }
}

// The workspace owns the one "start practising this bank" action; every other
// entry point (today, review) is a different session source. The composable
// first asks the server whether an unfinished session exists, so a click never
// silently starts a second one behind the user's back.
async function startPractice() {
  if (!practicableCount.value || startingPractice.value) return
  const payload = { bank_id: bankId.value, mode: 'PRACTICE' }
  const result = await startStudy(payload, { navigate: navigateToSession })
  if (result?.blocked?.length) {
    pendingStartStudyPayload.value = payload
    startStudySessions.value = result.blocked
    showStartStudyPanel.value = true
  } else if (!result?.error) {
    closeStartStudyPanel()
  }
}

function navigateToSession(session) {
  if (!session?.id) return
  router.push(session.mode === 'EXAM' ? `/exam/${session.id}` : `/practice/${session.id}`)
}

function closeStartStudyPanel() {
  showStartStudyPanel.value = false
  startStudySessions.value = []
  pendingStartStudyPayload.value = null
}

function handleStartStudyContinue() {
  const session = startStudySessions.value[0]
  closeStartStudyPanel()
  clearPracticeError()
  continueStudySession(session, navigateToSession)
}

async function handleStartStudyEndAndStart() {
  const result = await endAndStartStudy(
    startStudySessions.value,
    pendingStartStudyPayload.value,
    navigateToSession,
  )
  if (!result?.error) closeStartStudyPanel()
}

function handleStartStudyCancel() {
  closeStartStudyPanel()
}

function goToBankList() {
  router.push({ name: 'banks', query: readStoredBankListQuery() })
}

onMounted(async () => {
  await loadData()
  scrollActiveTabIntoView()
})
</script>

<style scoped>
.manage-page { padding-top: 24px; }
.link-btn { border: 0; background: none; padding: 0; color: var(--ink-3); font: inherit; cursor: pointer; }
.link-btn:hover { color: var(--brand); }
.bank-sub { display: flex; flex-wrap: wrap; gap: 14px; }
.manage-notice { margin-top: 14px; }
.manage-tabs { margin-top: 18px; }
.manage-tabs .tab[role="tab"] { cursor: pointer; }
.manage-workspace { margin-top: 0; }
.manage-archived-note { margin-top: 12px; }
.manage-toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 0; border-bottom: 1px solid var(--line);
}
.bank-manage-toolbar { border-top: 1px solid var(--ink); }
.manage-toolbar .search-box { min-width: 220px; max-width: 340px; flex: 1 1 260px; }
.manage-toolbar .select { height: 32px; font-size: 12px; width: auto; max-width: 168px; flex: 0 1 auto; }
.toolbar-divider { width: 1px; height: 18px; background: var(--line-strong); flex: none; }
.toolbar-field { display: inline-flex; align-items: center; gap: 6px; flex: none; }
.toolbar-field-label { font-size: 12px; color: var(--muted); white-space: nowrap; }
.select-all-toggle { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-3); cursor: pointer; }
.select-all-toggle input { width: 14px; height: 14px; cursor: pointer; }
.mtable-wrap.is-busy { opacity: .62; transition: opacity 120ms ease; }
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
.select-hit { display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
.mtable th.select-cell input,
.mtable td.select-cell input { width: 14px; height: 14px; cursor: pointer; }
.mtable-row.is-archived { opacity: .68; }
.mtable th {
  padding: 9px 10px; text-align: left;
  font-size: 12px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase;
  color: var(--ink-3); border-bottom: 1px solid var(--line); white-space: nowrap;
}
.mtable td { padding: 0 10px; height: 44px; border-bottom: 1px solid var(--line); font-size: 12px; color: var(--ink-2); vertical-align: middle; }
.mtable-row { cursor: default; }
.mtable-row:hover { background: var(--surface-2); }
.bank-manage-table .bank-manage-col-id { width: 78px; }
.bank-manage-table .bank-manage-col-stem { width: auto; }
.bank-manage-table .bank-manage-col-type { width: 88px; }
.bank-manage-table .bank-manage-col-chapter { width: 136px; }
.bank-manage-table .bank-manage-col-difficulty { width: 86px; }
.bank-manage-table .bank-manage-col-version { width: 62px; }
.bank-manage-table .bank-manage-col-actions { width: 104px; }
.row-archive-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; padding: 0; flex: none;
}
.id-cell { color: var(--ink-4); font-size: 12px; letter-spacing: .02em; white-space: nowrap; }
.stem-cell { line-height: 1.5; }
.stem-text { display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; color: var(--ink); }
.row-tags { display: inline-flex; gap: 4px; margin-left: 8px; vertical-align: middle; }
.row-tags .tag { font-size: 12px; height: 17px; padding: 0 5px; }
.dim-cell { color: var(--ink-3); }
.small.dim { white-space: nowrap; }

.manage-single { max-width: 860px; }
.tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 0 4px; }
.tag-list { display: flex; flex-direction: column; gap: 6px; padding: 8px 0 4px; }
.tag-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.tag-row .tag-name { flex: 1 1 160px; min-width: 0; overflow-wrap: anywhere; }
.tag-row .tag-row-input { flex: 1 1 160px; min-width: 0; }
.tag-row .tag-count { text-align: right; margin-left: auto; }
.settings-form { margin-top: 12px; }
.export-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 12px; }
.danger-zone { border-color: var(--bad); }
.danger-btn { color: var(--bad); border-color: var(--bad); }
.audit-list { display: flex; flex-direction: column; gap: 2px; margin-top: 10px; }
.audit-row {
  display: grid; grid-template-columns: 132px 210px minmax(0, 1fr);
  gap: 10px; align-items: center; padding: 7px 0;
  border-bottom: 1px solid var(--line); min-width: 0;
}
.member-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.member-actions .select { height: 30px; font-size: 12px; width: 104px; }
.member-leave { padding-top: 12px; border-top: 1px solid var(--line); margin-top: 8px; }
.mtable-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 10px 0; border-bottom: 1px solid var(--line); flex-wrap: wrap;
}
.mtable-foot .list-side { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.page-size { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-3); white-space: nowrap; }
.page-size-select { height: 32px; width: auto; font-size: 12px; padding: 0 6px; }
.import-table { min-width: 620px; }
.import-table th, .import-table td { padding: 8px 10px; }
.block { display: block; }
.chapter-row .select { max-width: 180px; }
.chapter-row { flex-wrap: wrap; }
.chapter-row .list-side { flex-wrap: wrap; }
.tag-count { margin-left: 5px; color: var(--ink-4); font-size: 12px; }
.chapter-add { display: flex; gap: 8px; padding: 12px 0 2px; border-top: 1px solid var(--line); }
.chapter-add .input { max-width: 280px; }
.tag-add { display: flex; gap: 8px; padding: 12px 0 2px; border-top: 1px solid var(--line); }
.tag-add .input { max-width: 280px; }
.child-chapter-form {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  padding: 8px 0 8px 10px; border-bottom: 1px solid var(--line);
}
.child-chapter-form .input { max-width: 280px; }
.chapter-row .chapter-input { max-width: 320px; }
.member-form { display: flex; gap: 8px; padding: 4px 0 2px; }
.member-form .input { flex: 1; }
.member-form .select { width: 140px; }

.manage-create { width: min(100%, 640px); }
.export-panel:focus { outline: 2px solid var(--brand); outline-offset: 2px; }
.create-form { display: flex; flex-direction: column; gap: 14px; }
.create-form label { display: flex; flex-direction: column; gap: 6px; }
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
  .bank-manage-table .bank-manage-col-actions { width: 88px; }
  .bank-manage-table th,
  .bank-manage-table td { padding-left: 8px; padding-right: 8px; }
  .bank-manage-table .stem-text { font-size: 12.5px; }
}
@media (max-width: 640px) {
  .manage-head .page-actions { width: 100%; }
  .manage-head .page-actions .btn { flex: 1 1 auto; justify-content: center; }
  .manage-tabs { gap: 16px; overflow-x: auto; flex-wrap: nowrap; }
  .manage-tabs .tab { white-space: nowrap; }
  .manage-toolbar .search-box { flex-basis: 100%; max-width: none; }
  .manage-toolbar .select { flex: 1 1 120px; max-width: none; }
  .manage-toolbar .toolbar-field { flex: 1 1 150px; min-width: 0; }
  .manage-toolbar .toolbar-field .select { flex: 1 1 auto; width: 100%; max-width: none; }
  .archived-toggle { flex-basis: 100%; }
  .batch-controls { flex-direction: column; align-items: stretch; }
  .batch-group { width: 100%; }
  .batch-group .select,
  .batch-group .input { flex: 1 1 auto; width: auto; max-width: none; }
  .batch-group .btn { flex: 0 0 auto; }
  .member-form { flex-wrap: wrap; }
  .member-form .input { flex-basis: 100%; }
  .create-grid { grid-template-columns: minmax(0, 1fr); }
  .tag-row { grid-template-columns: minmax(0, 1fr) 40px; }
  .tag-row .btn { grid-column: span 1; }
  .audit-row { grid-template-columns: minmax(0, 1fr); gap: 2px; }
  .mtable-foot .list-side { flex: 1 1 100%; }

  /* Compact question table: keep checkbox + stem + one action, no h-scroll. */
  .mtable { min-width: 0; }
  .mtable th.select-cell,
  .mtable td.select-cell { width: 36px; padding: 0; }
  .mtable .select-hit { width: 32px; height: 32px; }
  .mtable th.select-cell input,
  .mtable td.select-cell input { width: 18px; height: 18px; }
  .mtable .bank-manage-col-id,
  .mtable .bank-manage-col-type,
  .mtable .bank-manage-col-chapter,
  .mtable .bank-manage-col-difficulty,
  .mtable .bank-manage-col-version { display: none; }
  .mtable .bank-manage-col-stem { width: auto; min-width: 0; }
  .mtable .stem-cell { min-width: 0; overflow: hidden; }
  .mtable .stem-text { -webkit-line-clamp: 2; white-space: normal; overflow-wrap: anywhere; }
  .mtable .bank-manage-col-actions { width: 88px; padding-left: 4px; padding-right: 4px; }
  .mtable th,
  .mtable td { padding-left: 6px; padding-right: 6px; }
  .mtable th.select-cell,
  .mtable td.select-cell { padding-left: 0; padding-right: 0; }
  .chapter-add,
  .tag-add,
  .child-chapter-form { flex-wrap: wrap; }
  .chapter-add .input,
  .tag-add .input,
  .child-chapter-form .input { flex: 1 1 100%; max-width: none; }
}
</style>
