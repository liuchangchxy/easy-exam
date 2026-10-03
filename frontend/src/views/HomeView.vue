<template>
  <main class="home-page">
    <header class="page-header home-header">
      <div class="home-brand-area">
        <div class="home-brand-title">
          <span class="home-brand-icon">
            <LinearIcon name="layers" size="18" />
          </span>
          <h1>{{ t('home.asset_hub') }}</h1>
        </div>
        <p class="home-user-pill">
          <span class="user-role-dot" :class="user?.is_admin ? 'role-admin' : 'role-user'"></span>
          {{ user?.username }}
          <span v-if="user?.is_admin" class="user-role-badge">{{ user?.is_admin ? t('sidebar.role_admin') : t('sidebar.role_user') }}</span>
        </p>
      </div>

      <div class="home-actions-area">
        <!-- 支持快速创建题库与斩杀查漏会话恢复 -->
        <button type="button" class="primary btn-create-bank" @click="openCreateBankDialog">
          <LinearIcon name="plus" size="14" /> {{ t('home.create_bank') }}
        </button>
      </div>
    </header>

    <!-- EE-019: 未完成会话恢复与管理终端 HUD -->
    <section v-if="activeSessions.length > 0" class="active-session-banner">
      <div class="banner-content">
        <span class="banner-badge">
          <LinearIcon name="terminal" size="13" /> {{ t('home.active_session_badge') }}
        </span>
        <span class="banner-text">
          <template v-if="activeSessions.length === 1">
            {{ t('home.active_session_one', { bank: activeSessions[0].bank_name, mode: formatSessionMode(activeSessions[0].mode), answered: activeSessions[0].answered_count, total: activeSessions[0].total_questions }) }}
          </template>
          <template v-else>
            {{ t('home.active_session_many', { count: activeSessions.length, bank: activeSessions[0].bank_name, mode: formatSessionMode(activeSessions[0].mode), answered: activeSessions[0].answered_count, total: activeSessions[0].total_questions }) }}
          </template>
        </span>
      </div>
      <div class="banner-btn-group">
        <button type="button" class="primary btn-resume-session" @click="handleResume(activeSessions[0])">
          <LinearIcon name="play" size="13" /> {{ activeSessions.length > 1 ? t('home.resume_latest') : t('home.resume_session') }}
        </button>
        <button v-if="activeSessions.length > 1" type="button" class="secondary-btn btn-view-all-sessions" @click="openActiveSessionsModal">
          {{ t('home.all_sessions', { count: activeSessions.length }) }}
        </button>
        <button v-else type="button" class="btn-abandon-single text-btn" :disabled="abandoningSession" @click="handleAbandonSession(activeSessions[0].id)">
          {{ t('home.abandon_session') }}
        </button>
      </div>
    </section>

    <!-- 未完成会话列表与管理对话框 (EE-019) -->
    <div v-if="showActiveSessionsModal" class="exam-setup-backdrop" @click.self="showActiveSessionsModal = false" @keydown.esc="showActiveSessionsModal = false">
      <div class="exam-setup-dialog active-sessions-dialog modal-dialog-large" role="dialog" aria-modal="true">
        <div class="dialog-header-flex">
          <h2>{{ t('home.active_sessions_title', { count: activeSessions.length }) }}</h2>
          <button type="button" class="btn-close-icon" @click="showActiveSessionsModal = false">✕</button>
        </div>
        <p class="dialog-desc">
          {{ t('home.active_sessions_desc') }}
        </p>

        <div class="sessions-list-grid">
          <div
            v-for="sess in activeSessions"
            :key="sess.id"
            class="session-item-row"
          >
            <div class="session-item-info">
              <div class="session-item-header">
                <span class="session-mode-badge">
                  {{ formatSessionMode(sess.mode) }}
                </span>
                <strong class="session-bank-title">{{ sess.bank_name }}</strong>
                <small class="session-time-ago">{{ formatTimeAgo(sess.updated_at || sess.created_at) }}</small>
              </div>
              <div class="session-item-progress">
                <div class="session-progress-track">
                  <div
                    class="session-progress-bar"
                    :style="{ width: `${sess.total_questions ? Math.min(100, Math.round((sess.answered_count / sess.total_questions) * 100)) : 0}%` }"
                  ></div>
                </div>
                <span class="session-progress-label">
                  {{ sess.answered_count }} / {{ sess.total_questions }} {{ t('ui.k0130') }}{{ sess.total_questions ? Math.min(100, Math.round((sess.answered_count / sess.total_questions) * 100)) : 0 }}%)
                </span>
              </div>
            </div>
            <div class="session-item-actions">
              <button type="button" class="primary" @click="handleResume(sess)">
                {{ t('home.resume_session') }}
              </button>
              <button
                type="button"
                class="btn-ghost-danger"
                :disabled="abandoningSession"
                @click="handleAbandonSession(sess.id)"
              >
                {{ t('home.abandon_session') }}
              </button>
            </div>
          </div>
        </div>

        <div class="dialog-footer-flex">
          <button
            type="button"
            class="btn-ghost-danger"
            :disabled="abandoningSession"
            @click="handleAbandonAllSessions"
          >
            {{ t('home.clear_all_drafts') }}
          </button>
          <button type="button" class="secondary-btn" @click="showActiveSessionsModal = false">{{ t('ui.k0134') }}</button>
        </div>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted" style="padding: 2rem; text-align: center; font-family: var(--linear-mono);">{{ t('ui.k0135') }}</p>
    <section v-else class="bank-grid">
      <article v-for="bank in banks" :key="bank.id" class="bank-card" :class="{ 'has-active-session': Boolean(getActiveSessionForBank(bank.id)) }">
        <div class="bank-card-title-row">
          <h2>{{ bank.name }}</h2>
          <span v-if="getActiveSessionForBank(bank.id)" class="badge-active-progress">
            <LinearIcon name="clock" size="12" /> {{ t('home.active_session_badge') }} ({{ getActiveSessionForBank(bank.id).answered_count }}/{{ getActiveSessionForBank(bank.id).total_questions }})
          </span>
        </div>
        <p>{{ bank.description || t('home.no_description') }}</p>
        <div class="bank-meta-info">
          <small>{{ t('home.questions_count', { count: bank.question_count }) }}</small>
          <span v-if="bank.category" class="bank-category-pill">{{ bank.category }}</span>
        </div>
        <div class="bank-actions-container">
          <!-- 顺序通刷进度展示 (当存在进行中会话时显示) -->
          <div v-if="getActiveSessionForBank(bank.id)" class="sequential-progress-box">
            <div class="sequential-progress-header">
              <span class="progress-title">
                <LinearIcon name="play" size="11" />
                {{ t('home.sequential_practice') }}
              </span>
              <span class="progress-percent">
                {{ getActiveSessionForBank(bank.id).total_questions ? Math.min(100, Math.round((getActiveSessionForBank(bank.id).answered_count / getActiveSessionForBank(bank.id).total_questions) * 100)) : 0 }}%
              </span>
            </div>
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: `${getActiveSessionForBank(bank.id).total_questions ? Math.min(100, Math.round((getActiveSessionForBank(bank.id).answered_count / getActiveSessionForBank(bank.id).total_questions) * 100)) : 0}%` }"
              ></div>
            </div>
            <small class="progress-detail-text">
              {{ t('home.sequential_progress', {
                answered: getActiveSessionForBank(bank.id).answered_count,
                total: getActiveSessionForBank(bank.id).total_questions,
                percent: getActiveSessionForBank(bank.id).total_questions ? Math.min(100, Math.round((getActiveSessionForBank(bank.id).answered_count / getActiveSessionForBank(bank.id).total_questions) * 100)) : 0
              }) }}
            </small>
          </div>

          <div class="bank-primary-actions">
            <template v-if="getActiveSessionForBank(bank.id)">
              <button
                class="primary btn-resume-direct"
                @click="handleResume(getActiveSessionForBank(bank.id))"
              >
                <LinearIcon name="play" size="13" />
                {{ t('home.resume_sequential', {
                  answered: getActiveSessionForBank(bank.id).answered_count,
                  total: getActiveSessionForBank(bank.id).total_questions
                }) }}
              </button>
              <button
                type="button"
                class="secondary-btn btn-restart-sequential"
                :title="t('home.restart_sequential')"
                @click="handleRestartSequential(bank)"
              >
                <LinearIcon name="rotate-ccw" size="12" /> {{ t('home.restart_sequential') }}
              </button>
            </template>
            <template v-else>
              <button class="primary" :disabled="!bank.question_count" @click="$emit('start', bank)">
                <LinearIcon name="play" size="13" /> {{ t('home.start_sequential', { total: bank.question_count }) }}
              </button>
            </template>
            <button class="secondary-btn" :disabled="!bank.question_count" @click="openExamSetup(bank)">
              <LinearIcon name="award" size="13" /> {{ t('home.start_mock_exam') }}
            </button>
          </div>
          <div class="bank-utility-actions">
            <button type="button" class="btn-util-link btn-ai-batch" @click="openAiBatchModal(bank)">
              <LinearIcon name="zap" size="12" /> {{ t('home.batch_ai_btn') }}
            </button>
            <button type="button" class="btn-util-link" @click="openAddQuestion(bank)">{{ t('home.add_question') }}</button>
            <button type="button" class="btn-util-link" @click="openShareDialog(bank)">{{ t('home.share') }}</button>
            <button type="button" class="btn-util-link" @click="openExportDialog(bank)">{{ t('home.export') }}</button>
          </div>
        </div>
      </article>
      <div v-if="!banks.length" class="empty-state-card">
        <div class="empty-state-icon">
          <LinearIcon name="inbox" size="26" />
        </div>
        <h3 class="empty-state-title">{{ t('home.no_banks') }}</h3>
        <p class="empty-state-desc">{{ t('home.create_bank_hint') || t('home.no_banks') }}</p>
        <div class="empty-state-actions">
          <button type="button" class="primary" @click="openCreateBankDialog">
            <LinearIcon name="plus" size="14" /> {{ t('home.create_bank') }}
          </button>
        </div>
      </div>
    </section>

    <!-- 创建题库对话框 -->
    <div v-if="showCreateDialog" class="exam-setup-backdrop" @click.self="showCreateDialog = false" @keydown.esc="showCreateDialog = false">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" aria-labelledby="create-bank-title" @submit.prevent="handleCreateBank">
        <h2 id="create-bank-title">{{ t('home.create_bank') }}</h2>
        <label>{{ t('home.bank_name') }}
          <input v-model.trim="newBank.name" type="text" :placeholder="t('home.bank_name_placeholder')" required />
        </label>
        <label>{{ t('home.category') }}
          <input v-model.trim="newBank.category" type="text" :placeholder="t('home.category_placeholder')" />
        </label>
        <label>{{ t('home.description') }}
          <textarea v-model.trim="newBank.description" :placeholder="t('home.description_placeholder')" rows="3"></textarea>
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showCreateDialog = false">{{ t('common.cancel') }}</button>
          <button type="submit" :disabled="creatingBank">{{ creatingBank ? t('home.creating') : t('home.confirm_create') }}</button>
        </div>
      </form>
    </div>

    <!-- 模考设置对话框 (EE-002, EE-010: 支持蓝图选择与错题入库开关) -->
    <div v-if="examBank" class="exam-setup-backdrop" @click.self="examBank = null" @keydown.esc="examBank = null">
      <form class="exam-setup-dialog" role="dialog" aria-modal="true" aria-labelledby="exam-setup-title" @submit.prevent="beginExam">
        <h2 id="exam-setup-title">{{ t('ui.k0150') }}</h2>
        <p>{{ examBank.name }} {{ t('ui.k0151') }} {{ examBank.question_count }} {{ t('ui.k0101') }}</p>
        <label>{{ t('ui.k0152') }}
          <input v-model.number="totalQuestions" type="number" min="1" :max="examBank.question_count" required />
        </label>
        <label>{{ t('ui.k0153') }}
          <input v-model.number="timeLimitMinutes" type="number" min="0" max="600" required />
        </label>
        <label>{{ t('ui.k0154') }}
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <select v-model="selectedProfileId" style="flex: 1;" @change="onExamProfileChange">
              <option value="">{{ t('ui.k0155') }}</option>
              <option v-for="p in examProfiles" :key="p.id" :value="p.id">
                {{ p.name }} {{ p.latest_blueprint ? t('ui.k0665') : t('ui.k0666') }}
              </option>
            </select>
            <button type="button" class="action-link-btn" style="white-space: nowrap; font-size: 0.8rem; padding: 0.35rem 0.6rem;" @click="openBlueprintDialogFromExam">
              {{ t('ui.k0038') }}
            </button>
          </div>
        </label>
        <div v-if="selectedProfileBlueprintSummary" style="background: var(--success-light); border: 1px solid var(--success-border); border-radius: 6px; padding: 0.6rem 0.75rem; font-size: 0.85rem; color: var(--success);">
          <strong>{{ t('ui.k0156') }}</strong>
          {{ t('ui.k0157') }} {{ selectedProfileBlueprintSummary.sectionsCount }} {{ t('ui.k0158') }} {{ selectedProfileBlueprintSummary.totalQuestions }} {{ t('ui.k0101') }}
          <span v-if="selectedProfileBlueprintSummary.negativeMark > 0">{{ t('ui.k0159') }} {{ selectedProfileBlueprintSummary.negativeMark }} {{ t('ui.k0160') }}</span>
          <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">
            {{ t('ui.k0161') }}{{ totalQuestions }} {{ t('ui.k0123') }}
          </div>
        </div>
        <label class="ctrl-check exam-option-checkbox">
          <input v-model="recordMistakes" type="checkbox" />
          <span>{{ t('ui.k0162') }}</span>
        </label>
        <p v-if="examError" class="error">{{ examError }}</p>
        <div class="dialog-actions-row">
          <button type="button" class="secondary-btn" @click="examBank = null">{{ t('ui.k0149') }}</button>
          <button type="submit" class="primary" :disabled="startingExam">{{ startingExam ? t('ui.k0663') : t('ui.k0667') }}</button>
        </div>
      </form>
    </div>

    <!-- EE-011: 手动录入题目对话框 -->
    <div v-if="showAddQuestionDialog" class="exam-setup-backdrop" @click.self="showAddQuestionDialog = false" @keydown.esc="showAddQuestionDialog = false">
      <form class="exam-setup-dialog" role="dialog" style="width: min(100%, 36rem); max-height: 85vh; overflow-y: auto;" @submit.prevent="handleCreateQuestion">
        <h2>{{ t('ui.k0163') }}{{ targetBankForQuestion?.name }}）</h2>
        <label>{{ t('ui.k0164') }}
          <textarea v-model.trim="addQuestionForm.stem" rows="2" :placeholder="t('ui.k0165')" required></textarea>
        </label>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          <label>{{ t('ui.k0072') }}
            <select v-model="addQuestionForm.type" @change="onQuestionTypeChange">
              <option value="SINGLE">{{ t('ui.k0050') }}</option>
              <option value="MULTI">{{ t('ui.k0051') }}</option>
              <option value="JUDGE">{{ t('ui.k0052') }}</option>
              <option value="ESSAY">{{ t('ui.k0166') }}</option>
            </select>
          </label>
          <label>{{ t('ui.k0167') }}
            <select v-model.number="addQuestionForm.difficulty">
              <option :value="1">{{ t('ui.k0168') }}</option>
              <option :value="2">{{ t('ui.k0169') }}</option>
              <option :value="3">{{ t('ui.k0170') }}</option>
              <option :value="4">{{ t('ui.k0171') }}</option>
              <option :value="5">{{ t('ui.k0172') }}</option>
            </select>
          </label>
        </div>
        <div v-if="addQuestionForm.type === 'SINGLE' || addQuestionForm.type === 'MULTI' || addQuestionForm.type === 'JUDGE'">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <label style="margin: 0; font-weight: 600;">{{ t('ui.k0173') }}</label>
            <button v-if="addQuestionForm.type !== 'JUDGE'" type="button" class="btn-add-opt" @click="handleAddOpt">{{ t('ui.k0174') }}</button>
          </div>
          <div v-for="(opt, idx) in addQuestionForm.options" :key="idx" class="add-opt-row" style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.45rem;">
            <label style="display: flex; align-items: center; margin: 0; cursor: pointer;" :title="`${t('ui.k0175')}${opt.key})`">
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
            </label>
            <input v-model.trim="opt.key" style="width: 3.5rem; text-align: center; font-weight: 600;" :placeholder="t('ui.k0176')" />
            <input v-model.trim="opt.text" style="flex: 1;" :placeholder="t('ui.k0177')" />
            <button
              v-if="addQuestionForm.type !== 'JUDGE'"
              type="button"
              class="btn-remove-opt"
              :title="t('ui.k0178')"
              style="border: none; background: var(--danger-light); color: var(--danger); border-radius: 4px; padding: 0.35rem 0.6rem; cursor: pointer; font-size: 0.85rem;"
              @click="addQuestionForm.options.splice(idx, 1)"
            >✕</button>
          </div>
        </div>
        <label>{{ t('ui.k0179') }}
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <input v-model.trim="addQuestionForm.answer" :placeholder="t('ui.k0180')" required style="flex: 1;" />
            <span style="font-size: 0.8rem; color: var(--text-muted);">{{ t('ui.k0181') }}</span>
          </div>
        </label>
        <label>{{ t('ui.k0182') }}
          <textarea v-model.trim="addQuestionForm.explanation" rows="2" :placeholder="t('ui.k0183')"></textarea>
        </label>
        <label>{{ t('ui.k0184') }}
          <input v-model.trim="addQuestionForm.tags" :placeholder="t('ui.k0185')" />
        </label>
        <p v-if="addQuestionError" class="error">{{ addQuestionError }}</p>
        <div class="bank-actions">
          <button type="button" @click="showAddQuestionDialog = false">{{ t('ui.k0149') }}</button>
          <button type="submit" :disabled="savingQuestion">{{ savingQuestion ? t('ui.k0668') : t('ui.k0669') }}</button>
        </div>
      </form>
    </div>

    <!-- EE-020: 共享成员管理与跨库复制对话框 -->
    <div v-if="showShareDialog" class="exam-setup-backdrop" @click.self="showShareDialog = false" @keydown.esc="showShareDialog = false">
      <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 36rem);">
        <h2>{{ t('ui.k0186') }}</h2>
        <p>{{ t('ui.k0187') }}{{ targetBankForShare?.name }}】</p>

        <!-- 现有成员列表 -->
        <div style="margin-bottom: 1rem;">
          <h3 style="font-size: 0.95rem; margin-bottom: 0.4rem;">{{ t('ui.k0188') }}</h3>
          <div v-if="loadingMembers" style="color: var(--text-tertiary); font-size: 0.85rem;">{{ t('ui.k0189') }}</div>
          <div v-else style="display: flex; flex-direction: column; gap: 0.4rem; max-height: 8rem; overflow-y: auto;">
            <div v-for="m in bankMembersList" :key="m.user_id" style="display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0.6rem; background: var(--bg-page); border: 1px solid var(--border); border-radius: 4px;">
              <span style="font-size: 0.85rem; font-weight: 500;">{{ m.username }}</span>
              <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span style="font-size: 0.75rem; padding: 0.1rem 0.4rem; background: var(--bg-subtle); border-radius: 4px;">
                  {{ m.role === 'ADMIN' ? t('ui.k0643') : m.role === 'EDITOR' ? t('ui.k0670') : t('ui.k0671') }}
                </span>
                <button v-if="m.role !== 'ADMIN' && m.user_id !== user?.id" type="button" style="color: var(--danger); border: none; background: none; cursor: pointer; font-size: 0.75rem;" @click="handleRemoveMember(m.user_id)">
                  {{ t('ui.k0190') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 添加成员表单 -->
        <form style="border-top: 1px dashed var(--border-strong); padding-top: 0.75rem; margin-bottom: 1rem;" @submit.prevent="handleAddMember">
          <h3 style="font-size: 0.95rem; margin-bottom: 0.4rem;">{{ t('ui.k0191') }}</h3>
          <div style="display: flex; gap: 0.5rem; margin-bottom: 0.4rem;">
            <input v-model.trim="memberUsername" style="flex: 1;" :placeholder="t('ui.k0192')" required />
            <select v-model="memberRole" style="width: 7rem;">
              <option value="MEMBER">{{ t('ui.k0193') }}</option>
              <option value="EDITOR">{{ t('ui.k0194') }}</option>
            </select>
            <button type="submit" :disabled="submittingMember">{{ submittingMember ? t('ui.k0672') : t('ui.k0673') }}</button>
          </div>
          <p v-if="shareMessage" :class="{ error: shareIsError, success: !shareIsError }" style="margin: 0.2rem 0; font-size: 0.85rem;">{{ shareMessage }}</p>
        </form>

        <!-- 跨库复制题目小工具 -->
        <div style="border-top: 1px dashed var(--border-strong); padding-top: 0.75rem;">
          <h3 style="font-size: 0.95rem; margin-bottom: 0.4rem;">{{ t('ui.k0195') }}</h3>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <input v-model.trim="copyQuestionId" style="flex: 1;" :placeholder="t('ui.k0196')" />
            <select v-model="copyTargetBankId" style="width: 9rem;">
              <option value="">{{ t('ui.k0197') }}</option>
              <option v-for="b in banks.filter(x => x.id !== targetBankForShare?.id)" :key="b.id" :value="b.id">
                {{ b.name }}
              </option>
            </select>
            <button type="button" :disabled="!copyQuestionId.trim() || !copyTargetBankId || copyingQuestion" @click="handleCopyQuestion">
              {{ copyingQuestion ? t('ui.k0674') : t('ui.k0675') }}
            </button>
          </div>
          <p v-if="copyNotice" style="font-size: 0.85rem; color: var(--primary); margin: 0.3rem 0 0 0;">{{ copyNotice }}</p>
        </div>

        <div class="bank-actions" style="margin-top: 1rem;">
          <button type="button" @click="showShareDialog = false">{{ t('ui.k0134') }}</button>
        </div>
      </div>
    </div>

    <!-- EE-008: 题库多格式导出对话框 -->
    <div v-if="showExportDialog" class="exam-setup-backdrop" @click.self="showExportDialog = false" @keydown.esc="showExportDialog = false">
      <div class="exam-setup-dialog" role="dialog" style="width: min(100%, 28rem);">
        <h2>{{ t('ui.k0198') }}</h2>
        <p>{{ t('ui.k0187') }}{{ targetBankForExport?.name }}{{ t('ui.k0199') }} {{ targetBankForExport?.question_count || 0 }} {{ t('ui.k0200') }}</p>
        <label>{{ t('ui.k0201') }}
          <select v-model="exportFormat">
            <option value="json">{{ t('ui.k0202') }}</option>
            <option value="csv">{{ t('ui.k0203') }}</option>
            <option value="txt">{{ t('ui.k0204') }}</option>
            <option value="xlsx">{{ t('ui.k0205') }}</option>
          </select>
        </label>
        <div class="bank-actions">
          <button type="button" @click="showExportDialog = false">{{ t('ui.k0149') }}</button>
          <button type="button" class="primary" :disabled="exporting" @click="handleDownloadExport">
            {{ exporting ? t('ui.k0676') : t('ui.k0677') }}
          </button>
        </div>
      </div>
    </div>

    <!-- AI 批量生成题库解析对话框 -->
    <div v-if="showAiBatchModal" class="exam-setup-backdrop" @click.self="closeAiBatchModal" @keydown.esc="closeAiBatchModal">
      <div class="exam-setup-dialog ai-batch-dialog" role="dialog" aria-modal="true" style="width: min(100%, 36rem);">
        <div class="dialog-header-row" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <h2 style="font-size: 1.15rem; margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <LinearIcon name="zap" size="16" />
            <span>{{ t('home.batch_ai_title') }}</span>
          </h2>
          <button type="button" class="btn-close-icon" style="border: none; background: none; font-size: 1.25rem; cursor: pointer; color: var(--text-muted);" @click="closeAiBatchModal">✕</button>
        </div>
        <p style="font-size: 0.825rem; color: var(--text-muted); margin: 0 0 1rem; line-height: 1.45;">
          {{ t('home.batch_ai_desc') }}
        </p>

        <!-- 统计面板 -->
        <div class="ai-batch-stats-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 1.25rem;">
          <div style="background: var(--bg-subtle); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border); text-align: center;">
            <small style="color: var(--text-muted); font-size: 0.75rem;">{{ t('home.batch_ai_total') }}</small>
            <strong style="display: block; font-size: 1.25rem; font-family: var(--linear-mono); color: var(--text-main);">{{ aiBatchStatus?.total ?? aiBatchBank?.question_count ?? 0 }}</strong>
          </div>
          <div style="background: var(--bg-subtle); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border); text-align: center;">
            <small style="color: var(--text-muted); font-size: 0.75rem;">{{ t('home.batch_ai_has_expl') }}</small>
            <strong style="display: block; font-size: 1.25rem; font-family: var(--linear-mono); color: var(--success, #16a34a);">{{ aiBatchStatus?.with_explanation ?? 0 }}</strong>
          </div>
          <div style="background: var(--bg-subtle); padding: 0.75rem; border-radius: 8px; border: 1px solid var(--border); text-align: center;">
            <small style="color: var(--text-muted); font-size: 0.75rem;">{{ t('home.batch_ai_missing') }}</small>
            <strong style="display: block; font-size: 1.25rem; font-family: var(--linear-mono); color: var(--primary);">{{ aiBatchStatus?.without_explanation ?? 0 }}</strong>
          </div>
        </div>

        <!-- 选项模式 -->
        <div style="margin-bottom: 1.25rem;">
          <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; cursor: pointer; color: var(--text-main); margin-bottom: 0.4rem;">
            <input type="radio" :value="false" v-model="aiBatchOverwrite" :disabled="aiBatchStatus?.status === 'running'" />
            <span>{{ t('home.batch_ai_incremental') }}</span>
          </label>
          <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; cursor: pointer; color: var(--text-muted);">
            <input type="radio" :value="true" v-model="aiBatchOverwrite" :disabled="aiBatchStatus?.status === 'running'" />
            <span>{{ t('home.batch_ai_overwrite') }}</span>
          </label>
        </div>

        <!-- 正在执行中的进度状态条 -->
        <div v-if="aiBatchStatus?.status === 'running' || (aiBatchStatus?.processed || 0) > 0" style="margin-bottom: 1.25rem; background: var(--bg-subtle); padding: 0.85rem; border-radius: 8px; border: 1px solid var(--border);">
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem; margin-bottom: 0.4rem;">
            <span style="color: var(--primary); font-weight: 600;">
              {{ aiBatchStatus?.status === 'running' ? t('home.batch_ai_status_running') : (aiBatchStatus?.status === 'stopped' ? t('home.batch_ai_status_stopped') : t('home.batch_ai_status_completed')) }}
            </span>
            <span style="font-family: var(--linear-mono); color: var(--text-muted);">
              {{ aiBatchStatus?.total ? Math.min(100, Math.round(((aiBatchStatus.processed || 0) / aiBatchStatus.total) * 100)) : 0 }}%
            </span>
          </div>
          <div style="height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-bottom: 0.4rem;">
            <div
              style="height: 100%; background: var(--primary); transition: width 300ms ease;"
              :style="{ width: `${aiBatchStatus?.total ? Math.min(100, Math.round(((aiBatchStatus.processed || 0) / aiBatchStatus.total) * 100)) : 0}%` }"
            ></div>
          </div>
          <div style="font-size: 0.78rem; color: var(--text-muted); font-family: var(--linear-mono); display: flex; justify-content: space-between;">
            <span>{{ t('home.batch_ai_progress', {
              processed: aiBatchStatus?.processed || 0,
              total: aiBatchStatus?.total || 0,
              percent: aiBatchStatus?.total ? Math.min(100, Math.round(((aiBatchStatus.processed || 0) / aiBatchStatus.total) * 100)) : 0,
              succeeded: aiBatchStatus?.succeeded || 0,
              failed: aiBatchStatus?.failed || 0,
            }) }}</span>
          </div>
          <p v-if="aiBatchStatus?.current_question_stem" style="margin: 0.4rem 0 0; font-size: 0.75rem; color: var(--text-tertiary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            {{ t('home.batch_ai_processing', { stem: aiBatchStatus.current_question_stem }) }}
          </p>
        </div>

        <p style="font-size: 0.75rem; color: var(--text-tertiary); margin: 0 0 1.25rem;">
          {{ t('home.batch_ai_running_tip') }}
        </p>

        <!-- 底部操作按钮 -->
        <div style="display: flex; justify-content: flex-end; gap: 0.75rem; border-top: 1px solid var(--border); padding-top: 0.85rem;">
          <button type="button" class="secondary-btn" @click="closeAiBatchModal">{{ t('common.close') }}</button>
          <button
            v-if="aiBatchStatus?.status === 'running'"
            type="button"
            style="color: var(--danger); border: 1px solid var(--danger-border); background: var(--bg-card); border-radius: 6px; padding: 0.4rem 0.85rem; font-size: 0.85rem; cursor: pointer;"
            @click="handleStopAiBatch"
          >
            {{ t('home.batch_ai_stop') }}
          </button>
          <button
            v-else
            type="button"
            class="primary"
            :disabled="aiBatchLoading || (aiBatchStatus && aiBatchStatus.without_explanation === 0 && !aiBatchOverwrite)"
            @click="handleStartAiBatch"
          >
            {{ t('home.batch_ai_start') }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import { listBanks, createBank, createQuestion, addBankMember, listBankMembers, removeBankMember, copyQuestionToBank } from '../api/banks'
import { startExam, listProfiles, getBlueprint } from '../api/exams'
import { listActiveSessions, getSession, abandonSession, abandonAllSessions } from '../api/practice'
import { getAiBatchStatus, startAiBatchGenerate, stopAiBatchGenerate } from '../api/ai'
import { triggerSyncEvent } from '../api/sync'
import { useLocale } from '../composables/useLocale.js'

const route = useRoute()
const router = useRouter()

const { t } = useLocale()

const props = defineProps({ token: { type: String, required: true }, user: { type: Object, default: null } })
const emit = defineEmits(['start', 'mock-exam', 'resume-session', 'learning', 'mistakes', 'import', 'logout'])

const banks = ref([])
const activeSessions = ref([])
const showActiveSessionsModal = ref(false)
const abandoningSession = ref(false)
const loading = ref(true)
const error = ref('')

function getActiveSessionForBank(bankId) {
  return activeSessions.value.find(s => s.bank_id === bankId) || null
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
const newBank = ref({ name: '', description: '', category: t('ui.k0146') })

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

// EE-008: 导出状态
const showExportDialog = ref(false)
const targetBankForExport = ref(null)
const exportFormat = ref('json')
const exporting = ref(false)

// AI 批量预生成题库解析状态
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
    if (aiBatchStatus.value?.status === 'running') {
      startAiBatchPolling()
    }
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
      if (st.status !== 'running' && st.status !== 'stopping') {
        stopAiBatchPolling()
      }
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
    const st = await startAiBatchGenerate(props.token, aiBatchBank.value.id, aiBatchOverwrite.value)
    aiBatchStatus.value = st
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
    const st = await stopAiBatchGenerate(props.token, aiBatchBank.value.id)
    aiBatchStatus.value = st
  } catch (err) {
    alert(err.detail || err.message)
  }
}

async function handleRestartSequential(bank) {
  const active = getActiveSessionForBank(bank.id)
  if (active) {
    try {
      await abandonSession(props.token, active.id)
      activeSessions.value = activeSessions.value.filter(s => s.id !== active.id)
    } catch (_) {}
  }
  emit('start', bank)
}

function openActiveSessionsModal() {
  closeAllModals()
  showActiveSessionsModal.value = true
}

function openCreateBankDialog() {
  closeAllModals()
  newBank.value = { name: '', description: '', category: t('ui.k0146') }
  createError.value = ''
  showCreateDialog.value = true
}


async function handleResume(sessionSummary) {
  try {
    const fullSession = await getSession(props.token, sessionSummary.id)
    showActiveSessionsModal.value = false
    emit('resume-session', fullSession)
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
      category: newBank.value.category || t('ui.k0146'),
    })
    triggerSyncEvent('BANK_CREATED', 'BANK', created.id, { name: created.name })
    showCreateDialog.value = false
    newBank.value = { name: '', description: '', category: t('ui.k0146') }
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
  if (curr.includes(key)) {
    curr = curr.filter(k => k !== key)
  } else {
    curr.push(key)
    curr.sort()
  }
  addQuestionForm.value.answer = curr.join('')
}

function onQuestionTypeChange() {
  if (addQuestionForm.value.type === 'JUDGE') {
    addQuestionForm.value.options = [
      { key: 'T', text: t('ui.k0067') },
      { key: 'F', text: t('ui.k0075') }
    ]
    addQuestionForm.value.answer = 'T'
  } else if ((addQuestionForm.value.type === 'SINGLE' || addQuestionForm.value.type === 'MULTI') && addQuestionForm.value.options.length === 2 && addQuestionForm.value.options[0].key === 'T') {
    addQuestionForm.value.options = [
      { key: 'A', text: '' },
      { key: 'B', text: '' },
      { key: 'C', text: '' },
      { key: 'D', text: '' }
    ]
    addQuestionForm.value.answer = 'A'
  }
}

async function handleCreateQuestion() {
  if (!targetBankForQuestion.value || !addQuestionForm.value.stem.trim()) return
  savingQuestion.value = true
  addQuestionError.value = ''
  try {
    const tagsList = addQuestionForm.value.tags
      ? addQuestionForm.value.tags.split(/[,，\s]+/).filter(Boolean)
      : []
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
    shareMessage.value = `${t('ui.k0277')} ${memberUsername.value}！`
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
      headers: {
        Authorization: `Bearer ${props.token}`,
      },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `${t('ui.k0282')}${res.status})`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const ext = exportFormat.value === 'xlsx' ? 'xlsx' : exportFormat.value === 'csv' ? 'csv' : exportFormat.value === 'txt' ? 'txt' : 'json'
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

function formatSessionMode(mode) {
  const map = {
    EXAM: t('ui.k0293'),
    PRACTICE: t('ui.k0294'),
    MISTAKE: t('ui.k0295'),
    FSRS: t('ui.k0296'),
    ELIMINATION: t('ui.k0297'),
  }
  return map[mode] || mode || t('ui.k0298')
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
  if (!confirm(t('home.abandon_confirm_one'))) return
  abandoningSession.value = true
  try {
    await abandonSession(props.token, sessionId)
    await refreshActiveSessions()
    if (activeSessions.value.length === 0) {
      showActiveSessionsModal.value = false
    }
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

async function onExamProfileChange() {
  if (!selectedProfileId.value) {
    selectedProfileBlueprintSummary.value = null
    return
  }
  try {
    const bp = await getBlueprint(props.token, selectedProfileId.value)
    if (bp && bp.sections?.length) {
      const total = bp.sections.reduce((acc, s) => acc + (Number(s.count) || 0), 0)
      selectedProfileBlueprintSummary.value = {
        sectionsCount: bp.sections.length,
        totalQuestions: total,
        negativeMark: bp.negative_mark || 0,
      }
      if (total > 0 && examBank.value) {
        totalQuestions.value = Math.min(total, examBank.value.question_count || total)
      }
    } else {
      selectedProfileBlueprintSummary.value = null
    }
  } catch (_) {
    selectedProfileBlueprintSummary.value = null
  }
}

function openBlueprintDialogFromExam() {
  examBank.value = null
  window.dispatchEvent(new CustomEvent('easyexam:open-dialog', { detail: 'blueprint' }))
}

async function handleSyncedEvents(e) {
  const detail = e.detail || {}
  const events = Array.isArray(detail) ? detail : (detail.events || [])
  if (detail.userId && props.user?.id && detail.userId !== props.user.id) {
    return
  }
  const hasBankOrQuestion = events.some(ev => ev.aggregate_type === 'BANK' || ev.aggregate_type === 'QUESTION')
  const hasSession = events.some(ev => ev.aggregate_type === 'SESSION')
  if (hasBankOrQuestion) {
    try { banks.value = await listBanks(props.token) } catch (_) {}
  }
  if (hasSession) {
    try { activeSessions.value = await listActiveSessions(props.token) } catch (_) {}
  }
}

onMounted(async () => {
  // Synchronously register listener first to avoid missing any dispatches during async loads
  window.addEventListener('easyexam:action', handleEasyExamAction)
  window.addEventListener('easyexam:events-synced', handleSyncedEvents)

  // Immediately handle actions passed via route query (e.g. from AppLayout or command palette)
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
  else if (action === 'blueprint' || action === 'drafts' || action === 'ai') {
    window.dispatchEvent(new CustomEvent('easyexam:open-dialog', { detail: action }))
  }
}

onUnmounted(() => {
  window.removeEventListener('easyexam:events-synced', handleSyncedEvents)
  window.removeEventListener('easyexam:action', handleEasyExamAction)
})

defineExpose({
  openCreateBankDialog,
  showCreateDialog,
  closeAllModals
})
</script>

<style scoped>
.home-page {
  width: min(100% - 2rem, 76rem);
  margin: 1.5rem auto;
}

.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  padding: 0.85rem 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
}

.home-brand-area {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-shrink: 0;
}

.home-brand-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.home-brand-icon {
  font-size: 1.4rem;
  line-height: 1;
}

.home-brand-title h1 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.01em;
  margin: 0;
}

.home-user-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  font-size: 0.775rem;
  color: var(--text-muted);
  margin: 0;
}

.user-role-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--primary);
}
.user-role-dot.role-admin {
  background: var(--success);
}

.user-role-badge {
  font-size: 0.7rem;
  color: var(--primary);
  font-weight: 600;
  margin-left: 0.15rem;
}

.home-main-nav {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.main-nav-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.85rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-main);
  cursor: pointer;
  transition: all 0.15s ease;
}

.main-nav-tab:hover {
  background: var(--bg-muted);
  border-color: var(--border);
  color: var(--primary);
}

.main-nav-tab.featured {
  color: var(--primary);
  font-weight: 600;
}

.main-nav-tab.featured:hover {
  background: var(--primary-light);
  border-color: var(--primary-border);
}

.home-actions-area {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-shrink: 0;
}

.btn-create-bank {
  padding: 0.45rem 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xs);
}

.home-utility-group {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.btn-util {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.4rem 0.6rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-util:hover {
  background: var(--bg-muted);
  border-color: var(--border);
  color: var(--text-main);
}

.btn-util.btn-logout {
  color: var(--danger);
}

.btn-util.btn-logout:hover {
  background: var(--danger-light);
  border-color: var(--danger-border);
  color: var(--danger);
}

.bank-card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.bank-card-title-row h2 {
  margin: 0;
  font-size: 1.15rem;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.4;
  flex: 1;
  min-width: 0;
}

.badge-active-progress {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  background: var(--primary-light);
  color: var(--primary);
  border: 1px solid var(--primary-border);
  border-radius: 9999px;
  white-space: nowrap;
}

.bank-card.has-active-session {
  border-color: var(--primary-border);
  box-shadow: var(--shadow-sm);
}

.btn-resume-direct {
  background: var(--primary) !important;
  color: var(--on-primary) !important;
}

.bank-meta-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 0.5rem 0 0.85rem 0;
}

.bank-category-pill {
  font-size: 0.75rem;
  background: var(--bg-subtle);
  color: var(--text-muted);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}

.bank-actions-container {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-top: 0.5rem;
}

.bank-primary-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.bank-utility-actions {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  flex-wrap: wrap;
  border-top: 1px dashed var(--border);
  padding-top: 0.5rem;
}

.btn-util-link {
  font-size: 0.775rem;
  padding: 0.25rem 0.55rem;
  color: var(--text-muted);
  background: var(--bg-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-util-link:hover {
  color: var(--primary);
  border-color: var(--primary-border);
  background: var(--primary-light);
}

.dialog-actions-row {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.exam-option-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-page);
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  cursor: pointer;
}

.exam-setup-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: color-mix(in srgb, var(--text-main) 44%, transparent);
  backdrop-filter: blur(2px);
}

.exam-setup-dialog {
  width: min(100%, 28rem);
  display: grid;
  gap: 1.15rem;
  padding: 1.75rem;
  border-radius: var(--radius-xl);
  background: var(--bg-card);
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--border);
}

.exam-setup-dialog h2 {
  font-size: 1.25rem;
  color: var(--text-main);
}

.exam-setup-dialog label {
  display: grid;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-main);
}

.exam-setup-dialog input:not([type="checkbox"]):not([type="radio"]),
.exam-setup-dialog textarea {
  width: 100%;
}

.exam-setup-dialog label.exam-option-checkbox,
.exam-setup-dialog label.ctrl-check {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 0.6rem !important;
}

.exam-setup-dialog label.exam-option-checkbox input[type="checkbox"],
.exam-setup-dialog label.ctrl-check input[type="checkbox"],
.exam-setup-dialog input[type="checkbox"],
.exam-setup-dialog input[type="radio"] {
  width: auto !important;
  margin: 0 !important;
  flex: 0 0 auto !important;
}

.exam-setup-dialog .bank-actions {
  justify-content: flex-end;
  margin-top: 0.5rem;
}

.active-session-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1.25rem;
  margin-bottom: 1.5rem;
  background: linear-gradient(135deg, var(--primary-light) 0%, var(--success-light) 100%);
  border: 1px solid var(--primary-border);
  border-radius: var(--radius-lg, 8px);
  box-shadow: var(--shadow-sm);
  flex-wrap: wrap;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 280px;
}

.banner-badge {
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  background: var(--primary);
  color: var(--on-primary);
  border-radius: 4px;
  white-space: nowrap;
}

.banner-text {
  font-size: 0.9rem;
  color: var(--text-main);
  line-height: 1.4;
}

.banner-btn-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-view-all-sessions {
  font-size: 0.85rem;
  padding: 0.45rem 0.85rem;
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  color: var(--text-main);
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-view-all-sessions:hover {
  background: var(--bg-subtle);
  border-color: var(--border-strong);
}

.btn-abandon-single {
  font-size: 0.85rem;
  color: var(--danger);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.4rem 0.6rem;
  text-decoration: underline;
}

.btn-abandon-single:hover {
  color: var(--danger-hover);
}

@media (max-width: 1080px) {
  .btn-util-label {
    display: none;
  }
  .home-page {
    width: 100%;
    padding: 0 0.85rem;
    margin: 0.75rem auto;
  }
  .active-session-banner {
    flex-direction: column;
    align-items: stretch;
    gap: 0.65rem;
    padding: 0.75rem 1rem;
  }
  .banner-btn-group {
    width: 100%;
    justify-content: flex-start;
  }
  .bank-primary-actions {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .bank-primary-actions .btn-resume-direct,
  .bank-primary-actions > button.primary {
    width: 100%;
    flex: 1 1 100%;
    min-height: 2.6rem;
    font-weight: 600;
  }
  .bank-primary-actions .btn-restart-sequential,
  .bank-primary-actions > button.secondary-btn {
    flex: 1 1 calc(50% - 0.25rem);
    min-height: 2.4rem;
    font-size: 0.8125rem;
  }
}

@media (max-width: 768px) {
  .home-header {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.65rem;
  }
  .home-brand-area {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .home-brand-title h1 {
    font-size: 1.05rem;
  }
  .home-user-pill {
    font-size: 0.72rem;
    padding: 0.15rem 0.45rem;
  }
  .home-actions-area {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .btn-create-bank {
    padding: 0.45rem 0.85rem;
    font-size: 0.825rem;
    min-height: 42px;
    white-space: nowrap;
  }
  .bank-utility-actions {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem;
  }
  .btn-util-link {
    min-height: 38px;
    justify-content: center;
  }
  .active-session-banner {
    padding: 0.6rem 0.85rem;
    gap: 0.5rem;
    margin-bottom: 0.85rem;
  }
  .banner-text {
    font-size: 0.82rem;
  }
}

.sequential-progress-box {
  margin-bottom: 0.65rem;
  padding: 0.5rem 0.65rem;
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.sequential-progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  font-weight: 600;
  margin-bottom: 0.35rem;
  color: var(--text-main);
}

.sequential-progress-header .progress-title {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--primary);
}

.sequential-progress-header .progress-percent {
  font-family: var(--linear-mono);
  color: var(--primary);
}

.sequential-progress-box .progress-track {
  height: 5px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.sequential-progress-box .progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 3px;
  transition: width 200ms ease;
}

.progress-detail-text {
  display: block;
  margin-top: 0.35rem;
  font-size: 0.72rem;
  color: var(--text-muted);
  font-family: var(--linear-mono);
}

.btn-restart-sequential {
  padding: 0.4rem 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.btn-restart-sequential:hover {
  color: var(--danger);
  border-color: var(--danger-border);
}

.btn-ai-batch {
  color: var(--primary);
  font-weight: 500;
}

.btn-ai-batch:hover {
  background: var(--primary-light);
}
</style>
