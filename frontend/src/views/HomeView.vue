<template>
  <div class="today">
    <header class="masthead">
      <div class="masthead-meta">
        <span>{{ dateLine }}</span>
        <span>{{ weekLine }}</span>
        <span class="byline">{{ user?.username }} · {{ t('ep.brand.sub') }}</span>
      </div>
      <div class="masthead-row">
        <div>
          <h1 class="masthead-title">{{ t('ep.today.title') }}</h1>
          <div class="od-row masthead-actions">
            <button type="button" class="btn btn-primary" :disabled="!actionsReady" @click="startToday">
              <LinearIcon name="play" :size="15" />{{ todayActionLabel }}
            </button>
            <button v-if="dueMistakesCount" type="button" class="btn" @click="router.push('/review')">
              {{ t('ep.today.figure_due') }} {{ dueMistakesCount }}
            </button>
          </div>
        </div>
        <div class="masthead-figures">
          <div class="mf"><div class="mf-n">{{ summary?.attempts ?? '—' }}</div><div class="mf-c">{{ t('ep.today.figure_attempts') }}</div></div>
          <div class="mf"><div class="mf-n">{{ dueMistakesCount }}</div><div class="mf-c">{{ t('ep.today.figure_due') }}</div></div>
          <div class="mf"><div class="mf-n">{{ accuracyText }}</div><div class="mf-c">{{ t('ep.today.figure_accuracy') }}</div></div>
          <div class="mf"><div class="mf-n">{{ mistakesCount }}</div><div class="mf-c">{{ t('ep.today.figure_mistakes') }}</div></div>
        </div>
      </div>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="today-grid">
      <div class="today-main">
        <div v-if="activeSessions.length" class="resume-card">
          <div class="resume-kicker"><LinearIcon name="play" :size="13" />{{ t('ep.today.active_badge') }}</div>
          <div class="resume-title">{{ activeSessions[0].bank_name }}</div>
          <div class="resume-meta">
            {{ t('ep.today.active_one', {
              bank: activeSessions[0].bank_name,
              mode: formatSessionMode(activeSessions[0].mode),
              answered: activeSessions[0].answered_count,
              total: activeSessions[0].total_questions,
            }) }}
          </div>
          <div class="progress"><div class="progress-fill" :style="{ width: sessionPercent(activeSessions[0]) + '%' }"></div></div>
          <div class="od-row resume-meta-row">
            <span class="tiny dim">{{ activeSessions[0].answered_count }} / {{ activeSessions[0].total_questions }} {{ t('ep.exam.answered') }}</span>
            <span class="tiny mono">{{ sessionPercent(activeSessions[0]) }}%</span>
          </div>
          <div class="resume-actions">
            <button type="button" class="btn btn-primary btn-sm" @click="handleResume(activeSessions[0])">{{ t('ep.today.resume_action') }}</button>
            <button v-if="activeSessions.length > 1" type="button" class="btn btn-sm btn-quiet" @click="showActiveSessionsModal = true">
              {{ t('ep.today.view_all', { count: activeSessions.length }) }}
            </button>
            <button type="button" class="btn btn-sm btn-quiet" :disabled="abandoningSession" @click="handleAbandonSession(activeSessions[0].id)">
              {{ t('ep.today.abandon') }}
            </button>
          </div>
        </div>

        <section class="section today-section">
          <div class="section-head">
            <span class="section-title">{{ t('ep.today.plan') }}</span>
            <span class="section-note">{{ t('ep.today.quick_due_hint') }}</span>
          </div>
          <button type="button" class="plan-row" @click="router.push('/review')">
            <span class="plan-mark">01</span>
            <span class="list-main">
              <span class="plan-title">{{ t('ep.today.plan_due') }}</span>
              <span class="plan-sub">{{ t('ep.review.due_count', { count: dueMistakesCount }) }}</span>
            </span>
            <span class="plan-cta"><LinearIcon name="arrow-right" :size="15" /></span>
          </button>
          <button type="button" class="plan-row" @click="router.push('/review?tab=mistakes')">
            <span class="plan-mark">02</span>
            <span class="list-main">
              <span class="plan-title">{{ t('ep.today.plan_mistakes') }}</span>
              <span class="plan-sub">{{ t('ep.review.mistakes_count', { count: mistakesCount }) }}</span>
            </span>
            <span class="plan-cta"><LinearIcon name="arrow-right" :size="15" /></span>
          </button>
          <button type="button" class="plan-row" @click="startSprint">
            <span class="plan-mark">03</span>
            <span class="list-main">
              <span class="plan-title">{{ t('ep.today.plan_new') }}</span>
              <span class="plan-sub">{{ todayPlanCount ? t('ep.today.plan_items', { count: todayPlanCount }) : t('ep.today.plan_empty') }}</span>
            </span>
            <span class="plan-cta"><LinearIcon name="arrow-right" :size="15" /></span>
          </button>
        </section>

        <section class="section today-section">
          <div class="section-head">
            <span class="section-title">{{ t('ep.today.banks_title') }}</span>
            <span class="section-note">{{ t('ep.banks.sub', { count: banks.length }) }}</span>
            <span class="section-action">
              <button type="button" class="link-btn" @click="router.push('/banks')">{{ t('ep.common.all') }}</button>
            </span>
          </div>
          <div v-if="loading" class="skeleton-rows">
            <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
          </div>
          <div v-else-if="banks.length" class="today-bank-list">
            <div v-for="bank in banks" :key="bank.id" class="today-bank-row">
              <button type="button" class="today-bank-open" :aria-label="`${t('ep.banks.open')} ${bank.name}`" @click="router.push(`/banks/${bank.id}`)">
                <span class="bank-name-cell">
                  <span class="bank-name">{{ bank.name }}</span>
                  <span class="bank-meta">
                    <span>{{ bank.category || t('ep.banks.detail') }}</span>
                    <span>{{ t('ep.banks.questions', { count: bank.question_count || 0 }) }}</span>
                  </span>
                </span>
              </button>
              <span class="bank-row-actions">
                <button type="button" class="btn btn-sm" @click="emit('start', bank)">{{ t('ep.today.start_practice') }}</button>
                <LinearIcon name="chevron-right" :size="16" />
              </span>
            </div>
          </div>
          <div v-else class="empty">
            <div class="empty-title">{{ t('ep.today.banks_empty') }}</div>
            <div class="empty-desc">{{ t('ep.today.banks_empty_hint') }}</div>
            <div class="empty-actions">
              <button type="button" class="btn btn-primary" @click="openCreateBankDialog">{{ t('ep.today.create_bank') }}</button>
            </div>
          </div>
        </section>
      </div>

      <aside class="today-rail">
        <div class="rail-block">
          <div class="rail-title">{{ t('ep.today.plan') }}</div>
          <div v-if="planDays.length" class="d-week-bars" aria-hidden="true">
            <div v-for="day in planDays" :key="day.day_number" class="d-week-bar" :title="`${day.day_number}: ${day.question_count}`">
              <i :style="{ height: planBarHeight(day.question_count) }"></i>
              <em>{{ day.day_number }}</em>
            </div>
          </div>
          <div v-else class="rail-note">{{ t('ep.today.plan_empty') }}</div>
          <div v-if="todayPlan" class="rail-note weekly-plan-note">
            {{ todayPlan.question_count || 0 }} {{ t('ui.k0101') }} · {{ todayPlan.planned_minutes || 0 }} {{ t('ui.k0231') }}
          </div>
        </div>
        <div class="rail-block">
          <div class="rail-title">{{ t('ep.today.next') }}</div>
          <button v-for="bank in banks.slice(0, 3)" :key="bank.id" type="button" class="rail-link" @click="router.push(`/banks/${bank.id}`)">
            <span class="list-main"><span class="rail-link-title">{{ bank.name }}</span><span class="rail-note">{{ t('ep.banks.questions', { count: bank.question_count || 0 }) }}</span></span>
            <span class="rail-link-n">→</span>
          </button>
          <div v-if="!banks.length" class="rail-note">{{ t('ep.today.no_next') }}</div>
        </div>
      </aside>
    </div>

    <!-- Create bank -->
    <AppDialog
      :open="showCreateDialog"
      :title="t('home.create_bank')"
      initial-focus="#home-create-bank-name"
      data-testid="home-create-bank-dialog"
      @close="closeCreateBankDialog"
    >
      <form id="home-create-bank-form" class="form-grid" @submit.prevent="handleCreateBank">
        <label class="field"><span class="label">{{ t('home.bank_name') }}</span>
          <input id="home-create-bank-name" v-model.trim="newBank.name" class="input" type="text" :placeholder="t('home.bank_name_placeholder')" required />
        </label>
        <label class="field"><span class="label">{{ t('home.category') }}</span>
          <input v-model.trim="newBank.category" class="input" type="text" :placeholder="t('home.category_placeholder')" />
        </label>
        <label class="field"><span class="label">{{ t('home.description') }}</span>
          <textarea v-model.trim="newBank.description" class="textarea" :placeholder="t('home.description_placeholder')" rows="3"></textarea>
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
      </form>
      <template #foot>
        <button type="button" class="btn btn-quiet" @click="closeCreateBankDialog">{{ t('common.cancel') }}</button>
        <button type="submit" class="btn btn-primary" form="home-create-bank-form" :disabled="creatingBank">{{ creatingBank ? t('home.creating') : t('home.confirm_create') }}</button>
      </template>
    </AppDialog>

    <!-- Active sessions -->
    <AppDialog
      :open="showActiveSessionsModal"
      :title="t('ep.today.sessions_title')"
      panel-class="exam-setup-dialog home-dialog"
      style="--app-dialog-width: 520px"
      initial-focus=".session-row .primary"
      data-testid="active-sessions-dialog"
      @close="showActiveSessionsModal = false"
    >
      <p>{{ t('ep.today.sessions_desc') }}</p>
      <div class="session-list">
        <div v-for="sess in activeSessions" :key="sess.id" class="session-row">
          <div class="session-info">
            <div class="od-row" style="gap: 8px">
              <span class="tag">{{ formatSessionMode(sess.mode) }}</span>
              <strong>{{ sess.bank_name }}</strong>
              <span class="tiny dim">{{ formatTimeAgo(sess.updated_at || sess.created_at) }}</span>
            </div>
            <div class="progress" style="margin-top: 8px"><div class="progress-fill" :style="{ width: sessionPercent(sess) + '%' }"></div></div>
            <div class="tiny dim" style="margin-top: 4px">{{ sess.answered_count }} / {{ sess.total_questions }} {{ t('ep.exam.answered') }}</div>
          </div>
          <div class="od-row" style="gap: 6px">
            <button type="button" class="primary" @click="handleResume(sess)">{{ t('ep.today.resume_action') }}</button>
            <button type="button" class="secondary-btn" :disabled="abandoningSession" @click="handleAbandonSession(sess.id)">{{ t('ep.today.abandon') }}</button>
          </div>
        </div>
      </div>
      <div class="bank-actions">
        <button type="button" class="btn btn-sm btn-danger" :disabled="abandoningSession" @click="handleAbandonAllSessions">{{ t('ep.today.session_clear_all') }}</button>
        <span class="spacer"></span>
        <button type="button" @click="showActiveSessionsModal = false">{{ t('ep.common.close') }}</button>
      </div>
    </AppDialog>

    <!-- Exam setup -->
    <AppDialog
      :open="Boolean(examBank)"
      :title="t('ep.exam.setup')"
      panel-class="exam-setup-dialog home-dialog"
      style="--app-dialog-width: 520px"
      initial-focus="#home-exam-total"
      data-testid="home-exam-setup-dialog"
      @close="examBank = null"
    >
      <form class="home-dialog-form" @submit.prevent="beginExam">
        <p>{{ examBank?.name }} · {{ t('ep.banks.questions', { count: examBank?.question_count ?? 0 }) }}</p>
        <label>{{ t('ep.exam.questions') }}
          <input id="home-exam-total" v-model.number="totalQuestions" type="number" min="1" :max="examBank?.question_count" required />
        </label>
        <label>{{ t('ep.exam.time') }}
          <input id="home-exam-minutes" v-model.number="timeLimitMinutes" type="number" min="0" max="600" required />
        </label>
        <details class="exam-advanced-accordion">
          <summary class="exam-advanced-summary">
            <span>{{ t('common.advanced_settings') }}</span>
            <LinearIcon name="chevron-right" :size="12" class="summary-chevron" />
          </summary>
          <div class="exam-advanced-content">
            <label>{{ t('ep.exam.blueprint') }}
              <div style="display: flex; gap: 0.5rem; align-items: center;">
                <select v-model="selectedProfileId" style="flex: 1;" @change="onExamProfileChange">
                  <option value="">{{ t('ui.k0155') }}</option>
                  <option v-for="p in examProfiles" :key="p.id" :value="p.id">
                    {{ p.name }} {{ p.latest_blueprint ? t('ui.k0665') : t('ui.k0666') }}
                  </option>
                </select>
                <button type="button" class="action-link-btn" style="white-space: nowrap; font-size: 0.8rem; padding: 0.35rem 0.6rem;" @click="openBlueprintEditor">
                  {{ t('ui.k0038') }}
                </button>
              </div>
            </label>
            <div v-if="selectedProfileBlueprintSummary" class="notice info" style="margin-top: 10px">
              <span>{{ t('ui.k0157') }} {{ selectedProfileBlueprintSummary.sectionsCount }} {{ t('ui.k0158') }} {{ selectedProfileBlueprintSummary.totalQuestions }} {{ t('ui.k0101') }}</span>
            </div>
            <label class="check" style="margin-top: 10px;">
              <input v-model="recordMistakes" type="checkbox" />
              <span>{{ t('ep.exam.record_mistakes') }}</span>
            </label>
          </div>
        </details>
        <p v-if="examError" class="error">{{ examError }}</p>
        <div class="dialog-actions-row">
          <button type="button" class="secondary-btn" @click="examBank = null">{{ t('common.cancel') }}</button>
          <button type="submit" class="primary" :disabled="startingExam">{{ startingExam ? t('ui.k0663') : t('ep.exam.start') }}</button>
        </div>
      </form>
    </AppDialog>

    <!-- Add question -->
    <AppDialog
      :open="showAddQuestionDialog"
      :title="`${t('ep.today.add_question')} · ${targetBankForQuestion?.name || ''}`"
      panel-class="exam-setup-dialog home-dialog"
      style="--app-dialog-width: 640px; max-height: min(85vh, 960px)"
      initial-focus="#home-add-question-stem"
      @close="showAddQuestionDialog = false"
    >
      <form class="home-dialog-form" @submit.prevent="handleCreateQuestion">
        <label>{{ t('ui.k0164') }}
          <textarea id="home-add-question-stem" v-model.trim="addQuestionForm.stem" rows="2" :placeholder="t('ui.k0165')" required></textarea>
        </label>
        <div class="form-grid two">
          <label>{{ t('ep.banks.type') }}
            <select v-model="addQuestionForm.type" @change="onQuestionTypeChange">
              <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
              <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
              <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
              <option value="ESSAY">{{ t('ep.question_types.essay') }}</option>
            </select>
          </label>
          <label>{{ t('ep.banks.difficulty') }}
            <select v-model.number="addQuestionForm.difficulty">
              <option v-for="opt in difficultyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
        </div>
        <div v-if="addQuestionForm.type === 'SINGLE' || addQuestionForm.type === 'MULTI' || addQuestionForm.type === 'JUDGE'">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <label style="margin: 0; font-weight: 600;">{{ t('ui.k0173') }}</label>
            <button v-if="addQuestionForm.type !== 'JUDGE'" type="button" class="btn btn-sm btn-quiet" @click="handleAddOpt">{{ t('ui.k0174') }}</button>
          </div>
          <div v-for="(opt, idx) in addQuestionForm.options" :key="idx" class="add-opt-row">
            <input
              v-if="addQuestionForm.type === 'SINGLE' || addQuestionForm.type === 'JUDGE'"
              type="radio"
              name="correct-opt-radio"
              :checked="addQuestionForm.answer === opt.key"
              @change="addQuestionForm.answer = opt.key"
            />
            <input
              v-else-if="addQuestionForm.type === 'MULTI'"
              type="checkbox"
              :checked="addQuestionForm.answer.includes(opt.key)"
              @change="handleToggleMultiAnswer(opt.key)"
            />
            <input v-model.trim="opt.key" style="width: 3.5rem; text-align: center; font-weight: 600;" :placeholder="t('ui.k0176')" />
            <input v-model.trim="opt.text" style="flex: 1;" :placeholder="t('ui.k0177')" />
            <button
              v-if="addQuestionForm.type !== 'JUDGE'"
              type="button"
              class="btn btn-sm btn-quiet"
              :title="t('ui.k0178')"
              @click="addQuestionForm.options.splice(idx, 1)"
            >✕</button>
          </div>
        </div>
        <label>{{ t('ep.banks.answer') }}
          <input v-model.trim="addQuestionForm.answer" :placeholder="t('ui.k0180')" required />
        </label>
        <label>{{ t('ep.banks.analysis') }}
          <textarea v-model.trim="addQuestionForm.explanation" rows="2" :placeholder="t('ui.k0183')"></textarea>
        </label>
        <label>{{ t('ui.k0184') }}
          <input v-model.trim="addQuestionForm.tags" :placeholder="t('ui.k0185')" />
        </label>
        <p v-if="addQuestionError" class="error">{{ addQuestionError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showAddQuestionDialog = false">{{ t('common.cancel') }}</button>
          <button type="submit" class="primary" :disabled="savingQuestion">{{ savingQuestion ? t('ui.k0668') : t('ui.k0669') }}</button>
        </div>
      </form>
    </AppDialog>

    <!-- Share / members -->
    <AppDialog
      :open="showShareDialog"
      :title="`${t('ep.banks.member_tab')} · ${targetBankForShare?.name || ''}`"
      panel-class="exam-setup-dialog home-dialog"
      style="--app-dialog-width: 560px"
      initial-focus="#home-member-username"
      @close="showShareDialog = false"
    >
      <p>{{ t('ep.banks.members_note') }}</p>
      <div v-if="loadingMembers" class="tiny dim">{{ t('ep.common.loading') }}</div>
      <div v-else class="member-list">
        <div v-for="m in bankMembersList" :key="m.user_id" class="member-row">
          <span>{{ m.username }}</span>
          <div class="od-row" style="gap: 8px">
            <span class="tag">{{ m.role === 'ADMIN' ? t('ep.banks.owner') : m.role === 'EDITOR' ? t('ep.banks.editor') : t('ep.banks.member') }}</span>
            <button v-if="m.role !== 'ADMIN' && m.user_id !== user?.id" type="button" class="link-btn danger" @click="handleRemoveMember(m.user_id)">
              {{ t('ep.banks.remove') }}
            </button>
          </div>
        </div>
      </div>
      <form style="border-top: 1px solid var(--line); padding-top: 12px;" @submit.prevent="handleAddMember">
        <div class="od-row" style="gap: 8px">
          <input id="home-member-username" v-model.trim="memberUsername" style="flex: 1;" :placeholder="t('ui.k0192')" required />
          <select v-model="memberRole" style="width: 7rem;">
            <option value="MEMBER">{{ t('ep.banks.member') }}</option>
            <option value="EDITOR">{{ t('ep.banks.editor') }}</option>
          </select>
          <button type="submit" class="primary" :disabled="submittingMember">{{ submittingMember ? t('ui.k0672') : t('ep.banks.add_member') }}</button>
        </div>
        <p v-if="shareMessage" :class="{ error: shareIsError, success: !shareIsError }" style="margin: 0.4rem 0 0; font-size: 0.85rem;">{{ shareMessage }}</p>
      </form>
      <div style="border-top: 1px solid var(--line); padding-top: 12px;">
        <div class="small strong" style="margin-bottom: 6px">{{ t('ui.k0195') }}</div>
        <div class="od-row" style="gap: 8px; align-items: center;">
          <input v-model.trim="copyQuestionId" style="flex: 1;" :placeholder="t('ui.k0196')" />
          <select v-model="copyTargetBankId" style="width: 9rem;">
            <option value="">{{ t('ui.k0197') }}</option>
            <option v-for="b in banks.filter(x => x.id !== targetBankForShare?.id)" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
          <button type="button" class="btn btn-sm" :disabled="!copyQuestionId.trim() || !copyTargetBankId || copyingQuestion" @click="handleCopyQuestion">
            {{ copyingQuestion ? t('ui.k0674') : t('ui.k0675') }}
          </button>
        </div>
        <p v-if="copyNotice" class="small" style="color: var(--brand); margin: 6px 0 0;">{{ copyNotice }}</p>
      </div>
      <div class="bank-actions">
        <button type="button" @click="showShareDialog = false">{{ t('ep.common.close') }}</button>
      </div>
    </AppDialog>

    <!-- Export -->
    <AppDialog
      :open="showExportDialog"
      :title="t('ep.today.export')"
      panel-class="exam-setup-dialog home-dialog"
      style="--app-dialog-width: 420px"
      initial-focus="#home-export-format"
      @close="showExportDialog = false"
    >
      <p>{{ targetBankForExport?.name }} · {{ t('ep.banks.questions', { count: targetBankForExport?.question_count || 0 }) }}</p>
      <label>{{ t('ep.common.export') }}
        <select id="home-export-format" v-model="exportFormat">
          <option value="json">JSON</option>
          <option value="csv">CSV</option>
          <option value="txt">TXT</option>
          <option value="xlsx">XLSX</option>
        </select>
      </label>
      <div class="bank-actions">
        <button type="button" @click="showExportDialog = false">{{ t('common.cancel') }}</button>
        <button type="button" class="primary" :disabled="exporting" @click="handleDownloadExport">{{ exporting ? t('ui.k0676') : t('ep.common.export') }}</button>
      </div>
    </AppDialog>

    <!-- AI batch -->
    <AppDialog
      :open="showAiBatchModal"
      :title="t('home.batch_ai_title')"
      panel-class="exam-setup-dialog home-dialog"
      style="--app-dialog-width: 560px"
      initial-focus="#home-ai-incremental:not([disabled]), #home-ai-stop, #home-ai-start:not([disabled])"
      @close="closeAiBatchModal"
    >
      <p>{{ t('home.batch_ai_desc') }}</p>
      <div class="stat-row">
        <div class="stat"><div class="stat-n">{{ aiBatchStatus?.total ?? aiBatchBank?.question_count ?? 0 }}</div><div class="stat-c">{{ t('home.batch_ai_total') }}</div></div>
        <div class="stat"><div class="stat-n">{{ aiBatchStatus?.with_explanation ?? 0 }}</div><div class="stat-c">{{ t('home.batch_ai_has_expl') }}</div></div>
        <div class="stat"><div class="stat-n">{{ aiBatchStatus?.without_explanation ?? 0 }}</div><div class="stat-c">{{ t('home.batch_ai_missing') }}</div></div>
      </div>
      <label class="check">
        <input id="home-ai-incremental" type="radio" :value="false" v-model="aiBatchOverwrite" :disabled="aiBatchStatus?.status === 'running'" />
        <span>{{ t('home.batch_ai_incremental') }}</span>
      </label>
      <label class="check">
        <input id="home-ai-overwrite" type="radio" :value="true" v-model="aiBatchOverwrite" :disabled="aiBatchStatus?.status === 'running'" />
        <span>{{ t('home.batch_ai_overwrite') }}</span>
      </label>
      <div v-if="aiBatchStatus?.status === 'running' || (aiBatchStatus?.processed || 0) > 0">
        <div class="od-row" style="justify-content: space-between; margin-bottom: 4px;">
          <span class="small strong">{{ aiBatchStatus?.status === 'running' ? t('home.batch_ai_status_running') : (aiBatchStatus?.status === 'stopped' ? t('home.batch_ai_status_stopped') : t('home.batch_ai_status_completed')) }}</span>
          <span class="mono tiny">{{ aiBatchPercent }}%</span>
        </div>
        <div class="progress"><div class="progress-fill" :style="{ width: aiBatchPercent + '%' }"></div></div>
        <div class="tiny dim" style="margin-top: 4px">{{ aiBatchStatus?.processed || 0 }} / {{ aiBatchStatus?.total || 0 }}</div>
      </div>
      <div class="bank-actions">
        <button type="button" class="secondary-btn" @click="closeAiBatchModal">{{ t('ep.common.close') }}</button>
        <button v-if="aiBatchStatus?.status === 'running'" id="home-ai-stop" type="button" class="btn btn-danger" @click="handleStopAiBatch">{{ t('home.batch_ai_stop') }}</button>
        <button v-else id="home-ai-start" type="button" class="primary" :disabled="aiBatchLoading || (aiBatchStatus && aiBatchStatus.without_explanation === 0 && !aiBatchOverwrite)" @click="handleStartAiBatch">
          {{ t('home.batch_ai_start') }}
        </button>
      </div>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import AppDialog from '../components/AppDialog.vue'
import { listBanks, createBank, createQuestion, addBankMember, listBankMembers, removeBankMember, copyQuestionToBank } from '../api/banks'
import { startExam, listProfiles, getBlueprint } from '../api/exams'
import { startSession, listActiveSessions, getSession, abandonSession, abandonAllSessions } from '../api/practice'
import { listDueMistakes, listMistakes } from '../api/mistakes'
import { getLearningSummary, getLearningTrends, getStudyPlan } from '../api/learning'
import { getAiBatchStatus, startAiBatchGenerate, stopAiBatchGenerate } from '../api/ai'
import { triggerSyncEvent } from '../api/sync'
import { useLocale } from '../composables/useLocale.js'

const route = useRoute()
const router = useRouter()
const { t, locale } = useLocale()

const props = defineProps({ token: { type: String, required: true }, user: { type: Object, default: null } })
const emit = defineEmits(['start', 'mock-exam', 'resume-session', 'learning', 'mistakes', 'import', 'logout'])

const banks = ref([])
const activeSessions = ref([])
const showActiveSessionsModal = ref(false)
const abandoningSession = ref(false)
const loading = ref(true)
// The masthead primary action depends on both the bank list and active
// sessions. Keep it disabled until both have settled so an early click cannot
// be misread as "no banks" and open the create dialog instead of practice.
const actionsReady = ref(false)
const error = ref('')

const dueMistakesCount = ref(0)
const mistakesCount = ref(0)
const summary = ref(null)
const trends = ref(null)
const todayPlan = ref(null)

const dateLine = computed(() => {
  try {
    return new Intl.DateTimeFormat(locale.value, { year: 'numeric', month: 'long', day: 'numeric' }).format(new Date())
  } catch (_) {
    return ''
  }
})

const weekLine = computed(() => {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 1)
  const week = Math.ceil(((now - start) / 86400000 + start.getDay() + 1) / 7)
  return locale.value === 'en-US' ? `Week ${week}` : `第 ${week} 周`
})

const accuracyText = computed(() => {
  const rate = trends.value?.recent?.correct_rate
  return Number.isFinite(rate) ? `${Math.round(rate)}%` : '—'
})

const todayActionLabel = computed(() => (
  activeSessions.value.length ? t('ep.today.continue') : t('ep.today.start_practice')
))

const planDays = computed(() => {
  const days = Array.isArray(todayPlan.value?.days) ? todayPlan.value.days.slice(0, 7) : []
  return days.map((day, index) => ({
    day_number: day.day_number || index + 1,
    question_count: Number(day.question_count) || 0,
  }))
})

const maxPlanQuestions = computed(() => Math.max(1, ...planDays.value.map(day => day.question_count)))

function planBarHeight(questionCount) {
  const value = Number(questionCount) || 0
  return value ? `${Math.max(8, Math.round((value / maxPlanQuestions.value) * 34))}px` : '2px'
}

const difficultyOptions = computed(() => [1, 2, 3, 4, 5].map(value => ({ value, label: t('ep.difficulty.' + value) })))

const todayPlanCount = computed(() => {
  const day = todayPlan.value?.days?.[0]
  return day?.question_count || 0
})

const aiBatchPercent = computed(() => {
  const total = aiBatchStatus.value?.total || 0
  const processed = aiBatchStatus.value?.processed || 0
  return total ? Math.min(100, Math.round((processed / total) * 100)) : 0
})

async function refreshLearningStats() {
  if (!props.token) return
  const [dueRes, misRes, summaryRes, trendsRes, planRes] = await Promise.allSettled([
    listDueMistakes(props.token),
    listMistakes(props.token),
    getLearningSummary(props.token),
    getLearningTrends(props.token, { window_days: 7 }),
    getStudyPlan(props.token, { days: 7, minutes_per_day: 30 }),
  ])
  dueMistakesCount.value = dueRes.status === 'fulfilled' && Array.isArray(dueRes.value) ? dueRes.value.length : 0
  mistakesCount.value = misRes.status === 'fulfilled' && Array.isArray(misRes.value) ? misRes.value.length : 0
  summary.value = summaryRes.status === 'fulfilled' ? summaryRes.value : null
  trends.value = trendsRes.status === 'fulfilled' ? trendsRes.value : null
  todayPlan.value = planRes.status === 'fulfilled' ? planRes.value : null
}

function sessionPercent(session) {
  if (!session?.total_questions) return 0
  return Math.min(100, Math.round((session.answered_count / session.total_questions) * 100))
}

function formatSessionMode(mode) {
  const map = {
    EXAM: t('ep.nav.exams'),
    PRACTICE: t('ep.practice.setup'),
    MISTAKE: t('ep.today.plan_mistakes'),
    FSRS: t('ep.today.plan_due'),
    ELIMINATION: t('ep.practice.kill'),
  }
  return map[mode] || mode || t('ep.nav.review')
}

async function startToday() {
  if (!actionsReady.value) return
  if (activeSessions.value.length) {
    await handleResume(activeSessions.value[0])
    return
  }
  if (await startTodayPlan()) return
  const bank = banks.value.find(b => b.question_count > 0)
  if (bank) emit('start', bank)
  else openCreateBankDialog()
}

function todayPlanTask() {
  const day = todayPlan.value?.days?.[0]
  const tasks = Array.isArray(day?.bank_tasks)
    ? day.bank_tasks.filter(task => task?.bank_id && Array.isArray(task.question_ids) && task.question_ids.length)
    : []
  if (!tasks.length) return null
  const bankIds = [...new Set(tasks.map(task => task.bank_id))]
  const questionIds = [...new Set(tasks.flatMap(task => task.question_ids))]
  return { bankIds, questionIds }
}

async function startTodayPlan() {
  const task = todayPlanTask()
  if (!task) return false
  try {
    const session = await startSession(props.token, {
      bank_id: task.bankIds[0],
      ...(task.bankIds.length > 1 ? { bank_ids: task.bankIds } : {}),
      mode: 'PRACTICE',
      question_ids: task.questionIds,
    })
    router.push(`/practice/${session.id}`)
    return true
  } catch (err) {
    error.value = err.detail || err.message
    return false
  }
}

async function startSprint() {
  if (await startTodayPlan()) return
  const bank = banks.value.find(b => b.question_count > 0)
  if (!bank) {
    openCreateBankDialog()
    return
  }
  try {
    const session = await startSession(props.token, {
      bank_id: bank.id,
      mode: 'PRACTICE',
      total_questions: Math.min(20, bank.question_count || 1),
    })
    router.push(`/practice/${session.id}`)
  } catch (err) {
    error.value = err.detail || err.message
  }
}

const examBank = ref(null)
const examProfiles = ref([])
const selectedProfileId = ref('')
const selectedProfileBlueprintSummary = ref(null)
const recordMistakes = ref(true)
const totalQuestions = ref(0)
const timeLimitMinutes = ref(120)
const startingExam = ref(false)
const examError = ref('')

const showCreateDialog = ref(false)
const creatingBank = ref(false)
const createError = ref('')
const newBank = ref({ name: '', description: '', category: '' })

const showAddQuestionDialog = ref(false)
const targetBankForQuestion = ref(null)
const savingQuestion = ref(false)
const addQuestionError = ref('')
const addQuestionForm = ref({
  stem: '',
  type: 'SINGLE',
  options: [{ key: 'A', text: '' }, { key: 'B', text: '' }, { key: 'C', text: '' }, { key: 'D', text: '' }],
  answer: 'A',
  explanation: '',
  difficulty: 3,
  tags: '',
})

const showShareDialog = ref(false)
const targetBankForShare = ref(null)
const memberUsername = ref('')
const memberRole = ref('MEMBER')
const submittingMember = ref(false)
const shareMessage = ref('')
const shareIsError = ref(false)
const bankMembersList = ref([])
const loadingMembers = ref(false)
const copyQuestionId = ref('')
const copyTargetBankId = ref('')
const copyingQuestion = ref(false)
const copyNotice = ref('')

const showExportDialog = ref(false)
const targetBankForExport = ref(null)
const exportFormat = ref('json')
const exporting = ref(false)

const showAiBatchModal = ref(false)
const aiBatchBank = ref(null)
const aiBatchStatus = ref(null)
const aiBatchOverwrite = ref(false)
const aiBatchLoading = ref(false)
let aiBatchPollTimer = null

function closeAllModals() {
  showActiveSessionsModal.value = false
  examBank.value = null
  showCreateDialog.value = false
  showAddQuestionDialog.value = false
  showShareDialog.value = false
  showExportDialog.value = false
  closeAiBatchModal()
}

async function openAiBatchModal(bank) {
  closeAllModals()
  aiBatchBank.value = bank
  showAiBatchModal.value = true
  aiBatchOverwrite.value = false
  aiBatchLoading.value = true
  try {
    aiBatchStatus.value = await getAiBatchStatus(props.token, bank.id)
    if (aiBatchStatus.value?.status === 'running') startAiBatchPolling()
  } catch (err) {
    console.error(err)
  } finally {
    aiBatchLoading.value = false
  }
}

function closeAiBatchModal() {
  showAiBatchModal.value = false
  stopAiBatchPolling()
}

function startAiBatchPolling() {
  stopAiBatchPolling()
  aiBatchPollTimer = setInterval(async () => {
    if (!showAiBatchModal.value || !aiBatchBank.value) {
      stopAiBatchPolling()
      return
    }
    try {
      const st = await getAiBatchStatus(props.token, aiBatchBank.value.id)
      aiBatchStatus.value = st
      if (st.status !== 'running' && st.status !== 'stopping') stopAiBatchPolling()
    } catch (_) {}
  }, 1500)
}

function stopAiBatchPolling() {
  if (aiBatchPollTimer) {
    clearInterval(aiBatchPollTimer)
    aiBatchPollTimer = null
  }
}

async function handleStartAiBatch() {
  if (!aiBatchBank.value) return
  aiBatchLoading.value = true
  try {
    aiBatchStatus.value = await startAiBatchGenerate(props.token, aiBatchBank.value.id, aiBatchOverwrite.value)
    startAiBatchPolling()
  } catch (err) {
    alert(err.detail || err.message)
  } finally {
    aiBatchLoading.value = false
  }
}

async function handleStopAiBatch() {
  if (!aiBatchBank.value) return
  try {
    aiBatchStatus.value = await stopAiBatchGenerate(props.token, aiBatchBank.value.id)
  } catch (err) {
    alert(err.detail || err.message)
  }
}

function openActiveSessionsModal() {
  closeAllModals()
  showActiveSessionsModal.value = true
}

function openCreateBankDialog() {
  closeAllModals()
  newBank.value = { name: '', description: '', category: '' }
  createError.value = ''
  showCreateDialog.value = true
}

function closeCreateBankDialog() {
  showCreateDialog.value = false
}

async function handleResume(sessionSummary) {
  try {
    const fullSession = await getSession(props.token, sessionSummary.id)
    showActiveSessionsModal.value = false
    emit('resume-session', fullSession)
    if (fullSession?.mode === 'EXAM') router.push(`/exam/${fullSession.id}`)
    else router.push(`/practice/${fullSession.id}`)
  } catch (err) {
    alert(`${t('ui.k0275')}${err.detail || err.message}`)
  }
}

async function handleCreateBank() {
  if (!newBank.value.name) return
  creatingBank.value = true
  createError.value = ''
  try {
    const created = await createBank(props.token, {
      name: newBank.value.name,
      description: newBank.value.description,
      category: newBank.value.category || t('ep.banks.title'),
    })
    triggerSyncEvent('BANK_CREATED', 'BANK', created.id, { name: created.name })
    showCreateDialog.value = false
    newBank.value = { name: '', description: '', category: '' }
    banks.value = await listBanks(props.token)
  } catch (err) {
    createError.value = err.detail || err.message
  } finally {
    creatingBank.value = false
  }
}

async function openExamSetup(bank) {
  closeAllModals()
  examBank.value = bank
  totalQuestions.value = bank.question_count
  timeLimitMinutes.value = 120
  examError.value = ''
  selectedProfileId.value = ''
  recordMistakes.value = true
  try {
    examProfiles.value = await listProfiles(props.token)
  } catch (_) {
    examProfiles.value = []
  }
}

async function beginExam() {
  if (!examBank.value || totalQuestions.value < 1 || totalQuestions.value > examBank.value.question_count) return
  startingExam.value = true
  examError.value = ''
  try {
    const session = await startExam(props.token, {
      bank_id: examBank.value.id,
      total_questions: totalQuestions.value,
      time_limit: timeLimitMinutes.value,
      profile_id: selectedProfileId.value || undefined,
      record_mistakes: recordMistakes.value,
    })
    emit('mock-exam', session)
    examBank.value = null
  } catch (err) {
    examError.value = err.detail || err.message
  } finally {
    startingExam.value = false
  }
}

function openAddQuestion(bank) {
  closeAllModals()
  targetBankForQuestion.value = bank
  addQuestionForm.value = {
    stem: '',
    type: 'SINGLE',
    options: [{ key: 'A', text: '' }, { key: 'B', text: '' }, { key: 'C', text: '' }, { key: 'D', text: '' }],
    answer: 'A',
    explanation: '',
    difficulty: 3,
    tags: '',
  }
  addQuestionError.value = ''
  showAddQuestionDialog.value = true
}

function handleAddOpt() {
  const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
  const nextKey = letters[addQuestionForm.value.options.length] || `Opt${addQuestionForm.value.options.length + 1}`
  addQuestionForm.value.options.push({ key: nextKey, text: '' })
}

function handleToggleMultiAnswer(key) {
  let curr = addQuestionForm.value.answer ? addQuestionForm.value.answer.split('') : []
  if (curr.includes(key)) curr = curr.filter(k => k !== key)
  else {
    curr.push(key)
    curr.sort()
  }
  addQuestionForm.value.answer = curr.join('')
}

function onQuestionTypeChange() {
  if (addQuestionForm.value.type === 'JUDGE') {
    addQuestionForm.value.options = [{ key: 'T', text: t('ui.k0067') }, { key: 'F', text: t('ui.k0075') }]
    addQuestionForm.value.answer = 'T'
  } else if ((addQuestionForm.value.type === 'SINGLE' || addQuestionForm.value.type === 'MULTI') && addQuestionForm.value.options.length === 2 && addQuestionForm.value.options[0].key === 'T') {
    addQuestionForm.value.options = [
      { key: 'A', text: '' },
      { key: 'B', text: '' },
      { key: 'C', text: '' },
      { key: 'D', text: '' },
    ]
    addQuestionForm.value.answer = 'A'
  }
}

async function handleCreateQuestion() {
  if (!targetBankForQuestion.value || !addQuestionForm.value.stem.trim()) return
  savingQuestion.value = true
  addQuestionError.value = ''
  try {
    const tagsList = addQuestionForm.value.tags ? addQuestionForm.value.tags.split(/[,，\s]+/).filter(Boolean) : []
    const created = await createQuestion(props.token, targetBankForQuestion.value.id, {
      stem: addQuestionForm.value.stem.trim(),
      type: addQuestionForm.value.type,
      options: addQuestionForm.value.options,
      answer: addQuestionForm.value.answer.trim(),
      explanation: addQuestionForm.value.explanation.trim(),
      difficulty: addQuestionForm.value.difficulty,
      tags: tagsList,
    })
    triggerSyncEvent('QUESTION_CREATED', 'QUESTION', created.id, { bank_id: targetBankForQuestion.value.id })
    targetBankForQuestion.value.question_count = (targetBankForQuestion.value.question_count || 0) + 1
    showAddQuestionDialog.value = false
  } catch (err) {
    addQuestionError.value = err.detail || err.message
  } finally {
    savingQuestion.value = false
  }
}

async function openShareDialog(bank) {
  closeAllModals()
  targetBankForShare.value = bank
  memberUsername.value = ''
  memberRole.value = 'MEMBER'
  shareMessage.value = ''
  shareIsError.value = false
  copyQuestionId.value = ''
  copyTargetBankId.value = ''
  copyNotice.value = ''
  showShareDialog.value = true
  await fetchBankMembers(bank.id)
}

async function fetchBankMembers(bankId) {
  loadingMembers.value = true
  try {
    bankMembersList.value = await listBankMembers(props.token, bankId)
  } catch (err) {
    console.error(t('ui.k0276'), err)
    bankMembersList.value = []
  } finally {
    loadingMembers.value = false
  }
}

async function handleAddMember() {
  if (!targetBankForShare.value || !memberUsername.value.trim()) return
  submittingMember.value = true
  shareMessage.value = ''
  try {
    await addBankMember(props.token, targetBankForShare.value.id, memberUsername.value.trim(), memberRole.value)
    shareIsError.value = false
    shareMessage.value = `${t('ui.k0277')} ${memberUsername.value}`
    memberUsername.value = ''
    await fetchBankMembers(targetBankForShare.value.id)
  } catch (err) {
    shareIsError.value = true
    shareMessage.value = err.detail || err.message
  } finally {
    submittingMember.value = false
  }
}

async function handleRemoveMember(memberUserId) {
  if (!targetBankForShare.value || !confirm(t('ui.k0278'))) return
  try {
    await removeBankMember(props.token, targetBankForShare.value.id, memberUserId)
    await fetchBankMembers(targetBankForShare.value.id)
  } catch (err) {
    alert(`${t('ui.k0279')}${err.detail || err.message}`)
  }
}

async function handleCopyQuestion() {
  if (!targetBankForShare.value || !copyQuestionId.value.trim() || !copyTargetBankId.value) return
  copyingQuestion.value = true
  copyNotice.value = ''
  try {
    await copyQuestionToBank(props.token, targetBankForShare.value.id, copyQuestionId.value.trim(), copyTargetBankId.value)
    triggerSyncEvent('QUESTION_COPIED', 'QUESTION', copyQuestionId.value.trim(), { target_bank_id: copyTargetBankId.value })
    copyNotice.value = t('ui.k0280')
    copyQuestionId.value = ''
    banks.value = await listBanks(props.token)
  } catch (err) {
    copyNotice.value = `${t('ui.k0281')}${err.detail || err.message}`
  } finally {
    copyingQuestion.value = false
  }
}

function openExportDialog(bank) {
  closeAllModals()
  targetBankForExport.value = bank
  exportFormat.value = 'json'
  showExportDialog.value = true
}

async function handleDownloadExport() {
  if (!targetBankForExport.value) return
  exporting.value = true
  try {
    const res = await fetch(`/api/v1/banks/${targetBankForExport.value.id}/export?format=${exportFormat.value}`, {
      headers: { Authorization: `Bearer ${props.token}` },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `${t('ui.k0282')}${res.status})`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const ext = exportFormat.value === 'xlsx' ? 'xlsx' : exportFormat.value
    a.download = `${targetBankForExport.value.name}_export.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showExportDialog.value = false
  } catch (err) {
    alert(`${t('ui.k0283')}${err.message}`)
  } finally {
    exporting.value = false
  }
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return ''
  try {
    const diffMs = Date.now() - new Date(dateStr).getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return t('ui.k0299')
    if (diffMins < 60) return `${diffMins} ${t('ui.k0300')}`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours} ${t('ui.k0301')}`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} ${t('ui.k0302')}`
  } catch (_) {
    return String(dateStr).slice(0, 16).replace('T', ' ')
  }
}

async function refreshActiveSessions() {
  try {
    activeSessions.value = await listActiveSessions(props.token)
  } catch (_) {
    activeSessions.value = []
  }
}

async function handleAbandonSession(sessionId) {
  if (!confirm(t('ep.today.abandon_confirm'))) return
  abandoningSession.value = true
  try {
    await abandonSession(props.token, sessionId)
    await refreshActiveSessions()
    if (activeSessions.value.length === 0) showActiveSessionsModal.value = false
  } catch (err) {
    alert(`${t('ui.k0304')}${err.detail || err.message}`)
  } finally {
    abandoningSession.value = false
  }
}

async function handleAbandonAllSessions() {
  if (!confirm(t('home.abandon_confirm_all', { count: activeSessions.value.length }))) return
  abandoningSession.value = true
  try {
    await abandonAllSessions(props.token)
    await refreshActiveSessions()
    showActiveSessionsModal.value = false
  } catch (err) {
    alert(`${t('ui.k0307')}${err.detail || err.message}`)
  } finally {
    abandoningSession.value = false
  }
}

async function onExamProfileChange() {
  if (!selectedProfileId.value) {
    selectedProfileBlueprintSummary.value = null
    return
  }
  try {
    const bp = await getBlueprint(props.token, selectedProfileId.value)
    // The API wraps the stored configuration as { id, profile_id, version_number, blueprint }.
    const config = bp?.blueprint || {}
    const sections = Array.isArray(config.sections) ? config.sections : []
    if (sections.length) {
      const total = sections.reduce((acc, s) => acc + (Number(s.count) || 0), 0)
      selectedProfileBlueprintSummary.value = {
        sectionsCount: sections.length,
        totalQuestions: total,
        negativeMark: Number(config.negative_mark) || 0,
      }
      if (total > 0 && examBank.value) totalQuestions.value = Math.min(total, examBank.value.question_count || total)
    } else {
      selectedProfileBlueprintSummary.value = null
    }
  } catch (_) {
    selectedProfileBlueprintSummary.value = null
  }
}

function openBlueprintEditor() {
  // The exam centre owns the single blueprint editor (its setup drawer);
  // Today must not spawn a second modal for the same configuration.
  examBank.value = null
  router.push('/exams')
}

function openAiSettings() {
  router.push({ path: '/settings', query: { section: 'ai' } })
}

async function handleSyncedEvents(e) {
  const detail = e.detail || {}
  const events = Array.isArray(detail) ? detail : (detail.events || [])
  if (detail.userId && props.user?.id && detail.userId !== props.user.id) return
  const hasBankOrQuestion = events.some(ev => ev.aggregate_type === 'BANK' || ev.aggregate_type === 'QUESTION')
  const hasSession = events.some(ev => ev.aggregate_type === 'SESSION')
  if (hasBankOrQuestion) {
    try { banks.value = await listBanks(props.token) } catch (_) {}
  }
  if (hasSession) {
    try { activeSessions.value = await listActiveSessions(props.token) } catch (_) {}
    refreshLearningStats()
  }
}

onMounted(async () => {
  window.addEventListener('easyexam:action', handleEasyExamAction)
  window.addEventListener('easyexam:events-synced', handleSyncedEvents)

  if (route.query.action) {
    handleEasyExamAction({ detail: route.query.action })
    router.replace({ path: '/', query: {} })
  }

  try {
    banks.value = await listBanks(props.token)
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    loading.value = false
  }
  try {
    activeSessions.value = await listActiveSessions(props.token)
  } catch (_) {
    activeSessions.value = []
  }
  actionsReady.value = true
  refreshLearningStats()
})

watch(() => route.query.action, (act) => {
  if (act) {
    handleEasyExamAction({ detail: act })
    router.replace({ path: '/', query: {} })
  }
})

function handleEasyExamAction(e) {
  const action = e?.detail
  if (action === 'create_bank') openCreateBankDialog()
  else if (action === 'blueprint') router.push('/exams')
  else if (action === 'ai') openAiSettings()
  else if (action === 'drafts') {
    window.dispatchEvent(new CustomEvent('easyexam:open-dialog', { detail: 'drafts' }))
  }
}

onUnmounted(() => {
  window.removeEventListener('easyexam:events-synced', handleSyncedEvents)
  window.removeEventListener('easyexam:action', handleEasyExamAction)
})

defineExpose({ openCreateBankDialog, showCreateDialog, closeAllModals })
</script>

<style scoped>
.today {
  padding-top: 0;
}

.masthead-actions { margin-top: 0; flex-wrap: wrap; gap: 8px; }

.today-section { margin-top: 36px; }
.today-section:first-child { margin-top: 0; }

.resume-kicker {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--ink-3);
}

.resume-meta { color: var(--ink-3); font-size: 12.5px; margin: 4px 0 12px; }
.resume-meta-row { justify-content: space-between; margin-top: 6px; }
.resume-actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }

.today-bank-list { border-top: 1px solid var(--line); }
.today-bank-row {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  min-height: 58px;
  border-bottom: 1px solid var(--line);
}
.today-bank-row:hover { background: var(--surface-2); }
.today-bank-open {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
  border: 0;
  background: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.today-bank-open:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.bank-name-cell { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.bank-name { font-size: 14px; font-weight: 500; color: var(--ink); }
.bank-meta { display: flex; gap: 12px; font-size: 12.5px; color: var(--ink-3); }
.bank-row-actions { display: flex; align-items: center; gap: 8px; color: var(--ink-4); }

.session-list { display: flex; flex-direction: column; border-top: 1px solid var(--line); }
/* AppDialog owns the modal behaviour; keep the legacy border-only box metrics. */
:global(.app-dialog-panel.exam-setup-dialog.home-dialog) {
  width: min(100%, var(--app-dialog-width, 520px));
  padding: 0;
  gap: 0;
  overflow: hidden;
}
:global(.app-dialog-panel.exam-setup-dialog.home-dialog .app-dialog-head) {
  padding: 22px 22px 0;
  border-bottom: 0;
}
:global(.app-dialog-panel.exam-setup-dialog.home-dialog .app-dialog-body) {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 22px 22px;
}
.home-dialog-form { display: flex; flex-direction: column; gap: 14px; }
.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.session-info { flex: 1; min-width: 0; }

.member-list { border-top: 1px solid var(--line); }
.member-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 40px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}

.add-opt-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.small { font-size: 12px; }
.strong { font-weight: 600; }

.spacer { flex: 1; }
.weekly-plan-note { margin-top: 9px; }

@media (max-width: 900px) {
  .today-grid { gap: 30px; }
}

@media (max-width: 768px) {
  .session-row { flex-direction: column; align-items: flex-start; }
}
</style>
