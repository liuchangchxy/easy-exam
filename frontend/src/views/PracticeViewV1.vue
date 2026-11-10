<template>
  <main class="focus-mode" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
    <header class="focus-topbar">
      <div class="focus-top-left">
        <button type="button" class="focus-exit" @click="handleBack">
          <LinearIcon name="arrow-left" :size="15" />
          <span>{{ t('ep.practice.exit') }}</span>
        </button>
        <span class="focus-sep" aria-hidden="true"></span>
        <div class="focus-context">
          <span class="focus-mode-label">{{ session?.mode === 'ELIMINATION' ? t('ep.practice.mode_elimination') : session?.mode === 'FSRS' ? t('ep.practice.mode_fsrs') : session?.mode === 'MISTAKE' ? t('ep.practice.mode_mistake') : t('ep.practice.mode_practice') }}</span>
          <span v-if="question" class="focus-type">{{ formatType(question.type) }}</span>
        </div>
      </div>
      <div class="focus-top-right">
        <button v-if="question" type="button" class="focus-counter mono" @click="showSheetModal = true">
          {{ index + 1 }} / {{ questions.length }}
          <LinearIcon name="layers" :size="13" />
        </button>
        <button v-if="question" type="button" class="icon-btn" :class="{ 'is-on': isWeak }" :title="isWeak ? t('ep.banks.unmark_weak') : t('ep.banks.mark_weak')" :aria-label="isWeak ? t('ep.banks.unmark_weak') : t('ep.banks.mark_weak')" @click="toggleWeak">
          <LinearIcon name="flag" :size="16" />
        </button>
        <button type="button" class="icon-btn" :title="t('ep.practice.shortcuts_title')" :aria-label="t('ep.practice.shortcuts_title')" @click="showHelpTip = !showHelpTip">
          <LinearIcon name="command" :size="16" />
        </button>
        <div class="focus-more">
          <button type="button" class="icon-btn btn-more-menu" :aria-label="t('ep.practice.more')" @click="showMoreMenu = !showMoreMenu">
            <LinearIcon name="more" :size="16" />
          </button>
          <div v-if="showMoreMenu" class="focus-menu" @click="showMoreMenu = false">
            <button type="button" class="focus-menu-item" @click="toggleEditQuestion">
              <LinearIcon name="edit" :size="14" />{{ isEditingQuestion ? t('ep.practice.edit_exit') : t('ep.practice.edit_question') }}
            </button>
            <button type="button" class="focus-menu-item is-danger" @click="handleKill">
              <LinearIcon name="x" :size="14" />{{ t('ep.practice.kill') }}
            </button>
          </div>
        </div>
        <button type="button" class="btn btn-sm focus-finish" @click="complete">{{ t('ep.practice.finish') }}</button>
      </div>
    </header>

    <!-- Shortcut guide -->
    <div v-if="showHelpTip" class="focus-overlay" @click.self="showHelpTip = false">
      <div class="focus-dialog help-dialog" role="dialog" aria-modal="true">
        <div class="dialog-head">
          <span class="dialog-title">{{ t('ep.practice.shortcuts_title') }}</span>
          <button type="button" class="icon-btn" :aria-label="t('ep.common.close')" @click="showHelpTip = false"><LinearIcon name="x" :size="16" /></button>
        </div>
        <div class="help-body">
          <div class="help-group">
            <div class="rule-label">{{ t('ep.practice.help_nav') }}</div>
            <div class="help-keys">
              <span><kbd>A</kbd><kbd>B</kbd><kbd>C</kbd><kbd>D</kbd> {{ t('ui.k0519') }}</span>
              <span><kbd>Enter</kbd> {{ t('ui.k0520') }}</span>
              <span><kbd>Space</kbd> {{ t('ui.k0521') }} <kbd>→</kbd> {{ t('ui.k0522') }}</span>
              <span><kbd>←</kbd> {{ t('ui.k0523') }}</span>
              <span><kbd>F</kbd> {{ t('ui.k0524') }}</span>
            </div>
          </div>
          <div class="help-group">
            <div class="rule-label">{{ t('ep.practice.help_sheet') }}</div>
            <p class="help-text">{{ t('ep.practice.help_sheet_desc') }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Answer sheet -->
    <div v-if="showSheetModal" class="focus-overlay" @click.self="showSheetModal = false" data-testid="practice-sheet-drawer">
      <div class="focus-dialog sheet-dialog" role="dialog" aria-modal="true">
        <div class="dialog-head">
          <div>
            <span class="dialog-title">{{ t('ep.practice.index') }}</span>
            <span class="dialog-sub">{{ t('ep.practice.answered_ratio', { answered: answeredCount, total: questions.length }) }}</span>
          </div>
          <button type="button" class="icon-btn" :aria-label="t('ep.common.close')" @click="showSheetModal = false"><LinearIcon name="x" :size="16" /></button>
        </div>
        <div class="sheet-body">
          <div class="sheet-legend">
            <span><i class="dot blank"></i>{{ t('ep.practice.unanswered') }}</span>
            <span><i class="dot ok"></i>{{ t('ep.practice.correct') }}</span>
            <span><i class="dot bad"></i>{{ t('ep.practice.incorrect') }}</span>
            <span><i class="dot part"></i>{{ t('ep.practice.partial') }}</span>
          </div>
          <div class="sheet-grid">
            <button
              v-for="(qItem, qIdx) in questions"
              :key="qItem.id"
              type="button"
              class="sheet-num mono"
              :class="getSheetButtonClass(qItem.id, qIdx)"
              @click="goTo(qIdx)"
            >{{ qIdx + 1 }}</button>
          </div>
          <button type="button" class="btn btn-sm" @click="jumpNextUnanswered">{{ t('ep.practice.jump_unanswered') }}</button>
        </div>
      </div>
    </div>

    <!-- Practice report -->
    <div v-if="practiceReport" class="focus-overlay" data-testid="practice-report-modal">
      <div class="focus-dialog report-dialog" role="dialog" aria-modal="true">
        <div class="dialog-head">
          <div>
            <span class="dialog-title">{{ t('ep.practice.report_title') }}</span>
            <span class="dialog-sub">{{ t('ep.practice.report_desc') }}</span>
          </div>
        </div>
        <div class="report-body">
          <div class="stat-row report-stats">
            <div class="stat"><div class="stat-num">{{ practiceReport.score }}</div><div class="stat-cap">{{ t('ep.practice.report_score') }}</div></div>
            <div class="stat"><div class="stat-num">{{ practiceReport.accuracy }}<span class="unit">%</span></div><div class="stat-cap">{{ t('ep.practice.report_accuracy') }}</div></div>
            <div class="stat"><div class="stat-num">{{ practiceReport.answered_count }}<span class="unit">/ {{ practiceReport.total_questions }}</span></div><div class="stat-cap">{{ t('ep.practice.report_answered') }}</div></div>
            <div class="stat"><div class="stat-num">{{ practiceReport.time_spent || 0 }}<span class="unit">{{ t('ep.practice.time_unit') }}</span></div><div class="stat-cap">{{ t('ep.practice.report_time') }}</div></div>
          </div>
          <div class="report-counts">
            <span class="tag ok">{{ t('ep.practice.report_correct') }} {{ practiceReport.correct_count }}</span>
            <span v-if="practiceReport.partial_count" class="tag warn">{{ t('ep.practice.report_partial') }} {{ practiceReport.partial_count }}</span>
            <span class="tag bad">{{ t('ep.practice.report_wrong') }} {{ practiceReport.incorrect_count }}</span>
            <span class="tag">{{ t('ep.practice.report_blank') }} {{ practiceReport.unanswered_count }}</span>
          </div>
        </div>
        <div class="dialog-actions">
          <button type="button" class="btn" @click="handleBack">{{ t('ep.practice.done') }}</button>
          <button type="button" class="btn btn-primary" @click="handleRestartPractice">{{ t('ep.practice.restart') }}</button>
        </div>
      </div>
    </div>

    <!-- Submit confirmation -->
    <div v-if="showCompleteConfirmModal" class="focus-overlay" @click.self="showCompleteConfirmModal = false">
      <div class="focus-dialog confirm-dialog" role="dialog" aria-modal="true">
        <div class="dialog-head"><span class="dialog-title">{{ t('ep.practice.complete_title') }}</span></div>
        <div class="confirm-body">
          <p v-if="questions.length - answeredCount > 0" class="confirm-warn">{{ t('ep.practice.complete_blank', { count: questions.length - answeredCount }) }}</p>
          <p v-else class="confirm-text">{{ t('ep.practice.complete_all') }}</p>
          <p class="confirm-text">{{ t('ep.practice.complete_hint') }}</p>
        </div>
        <div class="dialog-actions">
          <button type="button" class="btn" @click="showCompleteConfirmModal = false">{{ t('ep.practice.cancel') }}</button>
          <button type="button" class="btn btn-primary" :disabled="completing" @click="handleConfirmComplete">
            {{ completing ? t('ep.practice.completing') : t('ep.practice.confirm_complete') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Exit confirmation -->
    <div v-if="showExitConfirmModal" class="focus-overlay" @click.self="handleCancelExit" data-testid="exit-confirm-modal">
      <div class="focus-dialog confirm-dialog" role="dialog" aria-modal="true">
        <div class="dialog-head"><span class="dialog-title">{{ t('ep.practice.exit_title') }}</span></div>
        <div class="confirm-body">
          <p class="confirm-text">{{ t('ep.practice.exit_desc') }}</p>
        </div>
        <div class="dialog-actions">
          <button type="button" class="btn" @click="handleCancelExit">{{ t('ep.practice.continue_practice') }}</button>
          <button type="button" class="btn btn-primary" @click="handleConfirmExit">{{ t('ep.practice.confirm_exit') }}</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="focus-loading skeleton-rows">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </div>

    <template v-else-if="question">
      <div class="focus-layout">
        <article class="focus-reading">
          <div v-if="offlineNotice" class="notice warn focus-offline" data-testid="offline-banner">
            <LinearIcon name="alert" :size="15" />
            <span>{{ offlineNotice }}</span>
            <button v-if="offlineRetryAvailable" type="button" class="btn btn-sm btn-quiet" @click="syncOfflineEdits">{{ t('ep.practice.offline_retry') }}</button>
          </div>

          <!-- Inline question editor -->
          <section v-if="isEditingQuestion" class="edit-panel" data-testid="question-edit-panel">
            <div class="edit-panel-head">
              <span class="edit-panel-title">{{ t('ep.practice.edit_title', { version: question.version_number }) }}</span>
              <button type="button" class="btn btn-sm btn-quiet" @click="isEditingQuestion = false">{{ t('ep.practice.edit_exit') }}</button>
            </div>
            <p v-if="editSaveError" class="notice bad" role="alert" data-testid="question-edit-error">{{ editSaveError }}</p>
            <label class="field">
              <span class="label">{{ t('ep.practice.edit_stem') }}</span>
              <textarea v-model="editStem" class="textarea" rows="3"></textarea>
            </label>
            <div class="edit-grid">
              <label class="field">
                <span class="label">{{ t('ep.banks.type') }}</span>
                <select v-model="editType" class="select">
                  <option value="SINGLE">{{ t('ep.question_types.single') }}</option>
                  <option value="MULTI">{{ t('ep.question_types.multi') }}</option>
                  <option value="JUDGE">{{ t('ep.question_types.judge') }}</option>
                  <option value="ESSAY">{{ t('ep.question_types.essay') }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.banks.difficulty') }}</span>
                <select v-model.number="editDifficulty" class="select">
                  <option :value="1">{{ t('bank_manage.diff_1') }}</option>
                  <option :value="2">{{ t('bank_manage.diff_2') }}</option>
                  <option :value="3">{{ t('bank_manage.diff_3') }}</option>
                  <option :value="4">{{ t('bank_manage.diff_4') }}</option>
                  <option :value="5">{{ t('bank_manage.diff_5') }}</option>
                </select>
              </label>
              <label class="field">
                <span class="label">{{ t('ep.practice.edit_answer') }}</span>
                <input v-model="editAnswer" class="input" :placeholder="t('ep.practice.edit_answer_placeholder')" />
              </label>
            </div>
            <div v-if="editType === 'SINGLE' || editType === 'MULTI' || editType === 'JUDGE'" class="edit-options">
              <div class="edit-options-head">
                <span class="label">{{ t('ep.practice.edit_options') }}</span>
                <button type="button" class="btn btn-sm btn-quiet" @click="addOption">{{ t('ep.practice.edit_add_option') }}</button>
              </div>
              <div v-for="(opt, oIdx) in editOptions" :key="oIdx" class="edit-option-row">
                <input v-model="opt.key" class="input opt-key-input mono" :aria-label="t('ep.practice.edit_option_key')" />
                <input v-model="opt.content" class="input" :placeholder="t('ep.practice.edit_option_text')" />
                <button type="button" class="icon-btn" :aria-label="t('ep.common.delete')" @click="removeOption(oIdx)"><LinearIcon name="x" :size="13" /></button>
              </div>
            </div>
            <label class="field">
              <span class="label">{{ t('ep.practice.edit_explanation') }}</span>
              <textarea v-model="editExplanation" class="textarea" rows="2"></textarea>
            </label>
            <label class="field">
              <span class="label">{{ t('ep.practice.edit_tags') }}</span>
              <input v-model="editTags" class="input" :placeholder="t('ep.practice.edit_tags_placeholder')" />
            </label>
            <label class="edit-check">
              <input v-model="editRegradeHistory" type="checkbox" />
              <span>{{ t('ep.practice.edit_regrade') }}</span>
            </label>
            <div class="edit-panel-actions">
              <button type="button" class="btn" @click="isEditingQuestion = false">{{ t('ep.common.cancel') }}</button>
              <button type="button" class="btn btn-primary" @click="saveQuestionEdit">{{ t('ep.practice.edit_save') }}</button>
            </div>
          </section>

          <!-- Conflict banner -->
          <section v-if="activeConflict || conflictResolvedMessage" class="conflict-banner" data-testid="conflict-banner">
            <div class="conflict-head">
              <LinearIcon name="alert" :size="15" />
              <span>{{ t('ep.practice.conflict_title') }}</span>
              <button type="button" class="btn btn-sm btn-quiet" @click="showConflictModal = !showConflictModal">
                {{ showConflictModal ? t('ep.practice.conflict_hide') : t('ep.practice.conflict_resolve') }}
              </button>
            </div>
            <p v-if="conflictResolvedMessage" class="conflict-resolved">{{ conflictResolvedMessage }}</p>
            <div v-if="showConflictModal" class="conflict-list" data-testid="conflict-list">
              <article v-for="v in questionVersions" :key="v.id" class="conflict-version" :class="{ 'is-current': v.version_number === question.version_number }">
                <div class="conflict-version-head">
                  <span class="mono">{{ t('ep.practice.conflict_version', { version: v.version_number }) }}</span>
                  <span v-if="v.version_number === question.version_number" class="tag brand">{{ t('ep.practice.conflict_current') }}</span>
                  <span class="small dim">{{ v.created_at ? v.created_at.slice(0, 19).replace('T', ' ') : '' }}</span>
                </div>
                <p class="conflict-stem">{{ v.stem }}</p>
                <div class="conflict-meta">
                  <span>{{ t('ep.practice.edit_answer') }} · {{ v.answer }}</span>
                  <button type="button" class="btn btn-sm" @click="handleAdoptQuestionVersion(v)">{{ t('ep.practice.conflict_adopt', { version: v.version_number }) }}</button>
                </div>
              </article>
            </div>
          </section>

          <div :key="question.id" class="q-sheet reading-page focus-sheet" :class="slideTransition">
            <div class="q-meta">
              <span>{{ t('ep.practice.question_no', { current: index + 1 }) }}</span>
              <span>{{ formatType(question.type) }}</span>
              <span v-if="isWeak" class="tag brand">{{ t('ep.review.weak') }}</span>
            </div>
            <div class="q-stem">{{ question.stem }}</div>

            <div v-if="question.options?.length" class="opt-list">
              <button
                v-for="option in question.options"
                :key="option.key"
                type="button"
                class="opt"
                :class="{
                  'is-selected': isOptionSelected(option.key),
                  'is-correct': result && isCorrectOption(option.key),
                  'is-wrong': result && isWrongOption(option.key),
                }"
                :aria-pressed="isOptionSelected(option.key)"
                :disabled="Boolean(result)"
                @click.prevent="selectOption(option.key)"
              >
                <span class="opt-key">{{ option.key }}</span>
                <span class="opt-text">{{ option.content }}</span>
                <span v-if="result && isCorrectOption(option.key)" class="opt-mark ok"><LinearIcon name="check" :size="14" /></span>
                <span v-else-if="result && isWrongOption(option.key)" class="opt-mark bad"><LinearIcon name="x" :size="14" /></span>
              </button>
            </div>

            <div v-else class="field">
              <label class="label" for="practice-text">{{ t('ep.practice.your_answer') }}</label>
              <textarea
                id="practice-text"
                v-model="textAnswer"
                class="textarea"
                :disabled="Boolean(result)"
                rows="4"
                :placeholder="t('ep.practice.essay_placeholder')"
              ></textarea>
            </div>
          </div>

          <!-- Feedback -->
          <section v-if="result" class="feedback-block">
            <div class="verdict-line" :class="result.correctness.toLowerCase()">
              <span class="verdict-mark">
                <LinearIcon :name="result.correctness === 'CORRECT' ? 'check' : 'x'" :size="16" />
              </span>
              <strong>{{ formatVerdictTitle(question.type, result.correctness, result.is_objective) }}</strong>
              <span v-if="result.is_objective && result.score_ratio !== undefined" class="verdict-ratio mono">
                {{ t('ep.practice.answer_ratio', { percent: Math.round((result.score_ratio || 0) * 100) }) }}
              </span>
            </div>
            <div class="answer-line">
              <span>{{ t('ep.practice.answer') }}</span>
              <span class="ans">{{ question.answer || t('ep.practice.ungraded') }}</span>
              <span v-if="hasAnswer" class="answer-yours">{{ t('ep.practice.your_answer') }} · {{ formatUserAnswer(question.options?.length ? answer : textAnswer) }}</span>
            </div>

            <div v-if="question.explanation" class="explain-block">
              <div class="rule-label">{{ t('ep.practice.official_explanation') }}</div>
              <div class="explain-body">{{ question.explanation }}</div>
            </div>

            <div v-if="session?.mode === 'FSRS' || session?.mode === 'MISTAKE'" class="fsrs-block">
              <div class="rule-label">{{ t('ep.practice.rate') }}</div>
              <div class="fsrs-buttons">
                <button type="button" class="btn btn-sm" :class="{ 'is-on': selectedFsrsRating === 1 }" @click="submitRating(1)">{{ t('ep.practice.again') }} <span class="mono">(+10m)</span></button>
                <button type="button" class="btn btn-sm" :disabled="result.correctness === 'INCORRECT'" :class="{ 'is-on': selectedFsrsRating === 2 }" @click="submitRating(2)">{{ t('ep.practice.hard') }} <span class="mono">(+1d)</span></button>
                <button type="button" class="btn btn-sm" :disabled="result.correctness !== 'CORRECT'" :class="{ 'is-on': selectedFsrsRating === 3 }" @click="submitRating(3)">{{ t('ep.practice.good') }} <span class="mono">(+3d)</span></button>
                <button type="button" class="btn btn-sm" :disabled="result.correctness !== 'CORRECT'" :class="{ 'is-on': selectedFsrsRating === 4 }" @click="submitRating(4)">{{ t('ep.practice.easy') }} <span class="mono">(+7d)</span></button>
              </div>
              <p v-if="fsrsRatingStatus" class="hint">{{ fsrsRatingStatus }}</p>
            </div>

            <div class="ai-entry">
              <div class="ai-entry-text">
                <span class="ai-entry-title"><LinearIcon name="cpu" :size="14" />{{ t('ep.practice.ai_title') }}</span>
                <span class="hint">{{ t('ep.practice.ai_secondary') }}</span>
              </div>
              <button type="button" class="btn btn-sm" @click="toggleAiPanel">{{ showAiPanel ? t('ep.practice.ai_close') : t('ep.practice.ai_open') }}</button>
            </div>

            <section v-if="showAiPanel" class="ai-panel">
              <div class="ai-toolbar">
                <div class="ai-actions">
                  <button type="button" class="btn btn-sm" :disabled="aiLoading || generatingVariant" @click="generateExplanation">{{ aiLoading ? t('ep.common.loading') : t('ep.practice.ai_generate') }}</button>
                  <button type="button" class="btn btn-sm" :disabled="aiLoading || generatingVariant" @click="handleVerifyWeb">{{ t('ep.practice.ai_verify') }}</button>
                  <button type="button" class="btn btn-sm" :disabled="aiLoading || generatingVariant" @click="handleGenerateVariant">{{ generatingVariant ? t('ep.common.loading') : t('ep.practice.ai_variant') }}</button>
                </div>
              </div>

              <div class="ai-ask">
                <input v-model="customQuery" class="input" type="text" :placeholder="t('ep.practice.ai_ask_placeholder')" @keyup.enter="askCustomQuery" />
                <button type="button" class="btn btn-sm" :disabled="!customQuery.trim() || aiLoading" @click="askCustomQuery">{{ t('ep.practice.ai_send') }}</button>
              </div>
              <p v-if="aiStatusMessage" class="hint">{{ aiStatusMessage }}</p>

              <div v-if="chatMessages.length" class="ai-chat">
                <div class="rule-label">{{ t('ep.practice.ai_chat') }}</div>
                <div v-for="msg in chatMessages" :key="msg.id" class="chat-row" :class="msg.role">
                  <div class="chat-meta">
                    <span class="chat-sender">{{ msg.role === 'user' ? t('ep.practice.ai_me') : t('ep.practice.ai_assistant') }}</span>
                    <span class="mono">{{ msg.sequence }}</span>
                  </div>
                  <p class="chat-text">{{ msg.content }}</p>
                </div>
              </div>

              <div v-if="answerVersions.length" class="ai-versions">
                <div class="rule-label">{{ t('ep.practice.ai_versions') }}</div>
                <article v-for="version in answerVersions" :key="version.id" class="ai-version" :class="{ 'is-adopted': version.is_adopted }">
                  <div class="ai-version-head">
                    <span class="tag">{{ formatSource(version.source) }}</span>
                    <span v-if="version.is_adopted" class="tag brand">{{ t('ep.practice.ai_adopted') }}</span>
                    <span class="small dim mono">{{ version.created_at ? version.created_at.slice(0, 19).replace('T', ' ') : '' }}</span>
                  </div>
                  <div v-if="editingVersionId !== version.id">
                    <p class="ai-version-text">{{ version.content }}</p>
                    <div v-if="version.evidence?.length" class="ai-evidence">
                      <div class="rule-label">{{ t('ep.practice.ai_evidence') }}</div>
                      <ul>
                        <li v-for="(ev, idx) in version.evidence" :key="idx">
                          <strong>{{ ev.title }}</strong>
                          <span v-if="ev.snippet"> — {{ ev.snippet }}</span>
                          <a v-if="ev.url" :href="ev.url" target="_blank" rel="noopener">{{ t('ep.practice.ai_open_link') }}</a>
                        </li>
                      </ul>
                    </div>
                    <div class="ai-version-actions">
                      <button v-if="!version.is_adopted" type="button" class="btn btn-sm" @click="adopt(version.id)">{{ t('ep.practice.ai_adopt') }}</button>
                      <button type="button" class="btn btn-sm btn-quiet" @click="startEdit(version)">{{ t('ep.practice.ai_edit') }}</button>
                    </div>
                  </div>
                  <div v-else class="ai-version-edit">
                    <textarea v-model="editDraft" class="textarea" rows="4"></textarea>
                    <div class="ai-version-actions">
                      <button type="button" class="btn btn-sm" @click="editingVersionId = null">{{ t('ep.common.cancel') }}</button>
                      <button type="button" class="btn btn-sm btn-primary" :disabled="!editDraft.trim()" @click="savePersonalExplanation">{{ t('ep.practice.ai_save') }}</button>
                    </div>
                  </div>
                </article>
              </div>
              <p v-else class="hint">{{ t('ep.practice.ai_empty') }}</p>
            </section>
          </section>

          <div v-else class="reading-hint">
            <LinearIcon name="command" :size="15" />
            <span>{{ t('ui.k0577') }} · {{ t('ui.k0580') }} <kbd>Enter</kbd></span>
          </div>
        </article>

        <aside class="focus-rail">
          <div class="rail-block">
            <div class="rail-title">{{ t('ep.practice.progress_label') }}</div>
            <div class="focus-progress">
              <span class="mono">{{ answeredCount }} / {{ questions.length }}</span>
              <div class="progress-track"><i :style="{ width: Math.min(100, (answeredCount / Math.max(1, questions.length)) * 100) + '%' }"></i></div>
            </div>
            <div class="rail-note">{{ t('ep.practice.session_title') }}</div>
          </div>

          <div class="rail-block">
            <div class="rail-title">{{ t('ep.practice.index') }}</div>
            <div class="sheet-mini">
              <button
                v-for="(qItem, qIdx) in questions"
                :key="qItem.id"
                type="button"
                class="sheet-num mono"
                :class="getSheetButtonClass(qItem.id, qIdx)"
                @click="goTo(qIdx)"
              >{{ qIdx + 1 }}</button>
            </div>
          </div>

          <div class="rail-block">
            <button type="button" class="btn btn-sm btn-block" :class="{ 'is-on': isWeak }" @click="toggleWeak">
              <LinearIcon name="flag" :size="13" />{{ isWeak ? t('ep.banks.unmark_weak') : t('ep.banks.mark_weak') }}
            </button>
            <button type="button" class="btn btn-sm btn-block" style="margin-top: 6px" @click="complete">{{ t('ep.practice.finish') }}</button>
          </div>

          <div class="rail-block">
            <div class="rail-title">{{ t('ep.practice.shortcuts_title') }}</div>
            <div class="rail-keys">
              <span><kbd>A-D</kbd> {{ t('ui.k0597') }}</span>
              <span><kbd>Enter</kbd> {{ t('ui.k0598') }}</span>
              <span><kbd>Space</kbd> {{ t('ui.k0092') }}</span>
              <span><kbd>F</kbd> {{ t('ui.k0599') }}</span>
            </div>
            <div class="rail-tools">
              <ThemeToggle compact />
              <LocaleToggle compact />
            </div>
          </div>
        </aside>
      </div>

      <footer class="focus-actionbar" data-testid="practice-action-bar">
        <div class="focus-action-inner">
          <button type="button" class="btn btn-sm" :disabled="index === 0" @click="prev">
            <LinearIcon name="arrow-left" :size="14" />{{ t('ep.practice.prev') }}
          </button>
          <span class="spacer"></span>
          <span class="focus-counter mono">{{ index + 1 }} / {{ questions.length }}</span>
          <span class="spacer"></span>
          <button v-if="!result && index < questions.length - 1" type="button" class="btn btn-sm btn-quiet" @click="next">{{ t('ep.practice.next') }}</button>
          <button v-if="!result" type="button" class="btn btn-primary" :disabled="!hasAnswer && question.options?.length" @click="submit">{{ t('ep.practice.submit') }}</button>
          <template v-else>
            <button v-if="index < questions.length - 1" type="button" class="btn btn-primary" @click="next">{{ t('ep.practice.next') }}</button>
            <button v-else type="button" class="btn btn-primary" @click="complete">{{ t('ep.practice.complete') }}</button>
          </template>
        </div>
      </footer>
    </template>
    <div v-else class="focus-empty">
      <div class="empty-title">{{ t('ep.practice.no_questions') }}</div>
      <div class="empty-desc">{{ t('ep.practice.no_questions_hint') }}</div>
      <button type="button" class="btn" @click="handleBack">{{ t('ep.common.back') }}</button>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LinearIcon from '../components/LinearIcon.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import LocaleToggle from '../components/LocaleToggle.vue'
import { useLocale } from '../composables/useLocale.js'
import { useAuthStore } from '../stores/authStore'
import { getSession, getSessionQuestions, submitAttempt, completeSession, syncDraft } from '../api/practice'
import { getQuestion, listQuestionVersions, updateQuestion, getQuestionConflict, resolveQuestionConflict, regradeQuestion } from '../api/questions'
import { generateAnswer, listAnswerVersions, adoptAnswer, saveCandidate, verifyWeb, listQuestionConversations, listConversationMessages, sendChatMessage, generateVariant } from '../api/ai'
import { markWeak, unmarkWeak } from '../api/learning'
import { killQuestion } from '../api/kills'
import { triggerSyncEvent } from '../api/sync'
import { formatVerdictTitle, findFirstUnansweredIndex, findNextUnansweredIndex, isSwipeGestureValid } from '../domain/exam.js'
import { hydrateSessionPractice, normalizeQuestionOptions, shouldResetQuestionForm } from '../domain/practice.js'

const props = defineProps({ token: { type: String, required: true }, sessionId: { type: String, required: true } })
const emit = defineEmits(['back', 'completed'])

const router = useRouter()
const auth = useAuthStore()
const { t } = useLocale()
const authToken = computed(() => props.token || auth.token?.value || (typeof localStorage !== 'undefined' ? localStorage.getItem('easyexam_token') : '') || '')

const showExitConfirmModal = ref(false)

function handleBack() {
  if (practiceReport.value || session.value?.is_completed) {
    doExit()
    return
  }
  showExitConfirmModal.value = true
}

async function handleConfirmExit() {
  showExitConfirmModal.value = false
  saveCurrentQuestionState()
  if (props.sessionId && props.token) {
    try {
      await syncDraft(props.token, props.sessionId, {
        current_index: index.value,
        time_spent: null,
      })
    } catch (_) {}
  }
  doExit()
}

function handleCancelExit() {
  showExitConfirmModal.value = false
}

function doExit() {
  emit('back')
  if (router && window.history.length > 1) {
    router.back()
  } else if (router) {
    router.push('/')
  }
}

function getOfflineQueueKey() {
  const uid = auth.user?.value?.id || auth.user?.value?.username || 'user'
  return `easyexam_offline_question_edits_${uid}`
}

const session = ref(null)
const questions = ref([])
const index = ref(0)
const answer = ref([])
const textAnswer = ref('')
const result = ref(null)
const sessionAnswers = ref({}) // questionId -> { answer, textAnswer, result, showAiPanel, selectedFsrsRating }
const showSheetModal = ref(false)
const showMoreMenu = ref(false)
const showHelpTip = ref(false)
const slideTransition = ref('slide-next')
const selectedFsrsRating = ref(null)
const fsrsRatingStatus = ref('')
const loading = ref(true)
const submitting = ref(false)
const answerVersions = ref([])
const chatMessages = ref([])
const activeConversationId = ref(null)
const showAiPanel = ref(false)
const aiLoading = ref(false)
const generatingVariant = ref(false)
const aiStatusMessage = ref('')
const customQuery = ref('')
const editingVersionId = ref(null)
const editDraft = ref('')
const isWeak = ref(false)
const questionVersions = ref([])
const activeConflict = ref(null)
const showConflictModal = ref(false)
const conflictResolvedMessage = ref('')
const isEditingQuestion = ref(false)
const editStem = ref('')
const editType = ref('SINGLE')
const editOptions = ref([])
const editAnswer = ref('')
const editExplanation = ref('')
const editDifficulty = ref(3)
const editTags = ref('')
const editRegradeHistory = ref(false)
const offlineNotice = ref('')
const offlineRetryAvailable = ref(false)
const editSaveError = ref('')


const question = computed(() => questions.value[index.value])

const hasAnswer = computed(() => {
  if (!question.value) return false
  if (question.value.options?.length) {
    return Array.isArray(answer.value) ? answer.value.length > 0 : Boolean(answer.value)
  }
  return textAnswer.value.trim().length > 0
})

function selectOption(key) {
  if (result.value) return
  if (question.value?.type === 'MULTI') {
    const list = Array.isArray(answer.value) ? [...answer.value] : []
    const idx = list.indexOf(key)
    if (idx >= 0) list.splice(idx, 1)
    else list.push(key)
    answer.value = list
  } else {
    answer.value = key
  }
  saveCurrentQuestionState()
}

function isOptionSelected(key) {
  if (question.value?.type === 'MULTI') {
    return Array.isArray(answer.value) && answer.value.includes(key)
  }
  return answer.value === key
}

function formatType(type) {
  const norm = String(type || '').toUpperCase()
  const map = {
    SINGLE: t('practice.question_type_single'),
    MULTI: t('practice.question_type_multiple'),
    JUDGE: t('practice.question_type_judge'),
    FILL: t('practice.question_type_qa'),
    ESSAY: t('practice.question_type_qa'),
    SHORT_ANSWER: t('practice.question_type_qa'),
    SUBJECTIVE: t('practice.question_type_qa'),
  }
  return map[norm] || String(type || '')
}

function formatSource(source) {
  const map = { AI: t('ui.k0604'), WEB: t('ui.k0605'), PERSONAL: t('ui.k0606'), OFFICIAL: t('ui.k0574') }
  return map[source] || source
}

function normalizedAnswer() {
  if (question.value?.options?.length) {
    if (question.value?.type === 'MULTI') {
      const selected = Array.isArray(answer.value) ? answer.value : [answer.value]
      return [...selected].sort().join('')
    }
    return answer.value
  }
  return textAnswer.value.trim()
}

function isCorrectOption(key) {
  if (!question.value?.answer) return false
  const cleaned = String(question.value.answer).replace(/[,\s]/g, '').toUpperCase()
  return cleaned.includes(String(key).toUpperCase())
}

function isWrongOption(key) {
  return isOptionSelected(key) && !isCorrectOption(key)
}

function formatUserAnswer(val) {
  if (Array.isArray(val)) {
    return val.length ? val.join(', ') : t('ui.k0112')
  }
  return val ? String(val) : t('ui.k0112')
}

let touchStartX = 0
let touchStartY = 0

function handleTouchStart(e) {
  if (!e.touches || e.touches.length !== 1) return
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'textarea' || tag === 'input' || tag === 'pre' || tag === 'code' || tag === 'button') return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}

function handleTouchEnd(e) {
  if (!e.changedTouches || e.changedTouches.length !== 1) return
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'textarea' || tag === 'input' || tag === 'pre' || tag === 'code' || tag === 'button') return
  const touchEndX = e.changedTouches[0].clientX
  const touchEndY = e.changedTouches[0].clientY
  const gesture = isSwipeGestureValid(touchStartX, touchStartY, touchEndX, touchEndY)
  if (gesture === 'prev') {
    prev()
  } else if (gesture === 'next') {
    next()
  }
}

function saveCurrentQuestionState() {
  if (!question.value) return
  const qid = question.value.id
  sessionAnswers.value[qid] = {
    answer: Array.isArray(answer.value) ? [...answer.value] : answer.value,
    textAnswer: textAnswer.value,
    result: result.value,
    showAiPanel: showAiPanel.value,
    selectedFsrsRating: selectedFsrsRating.value,
  }
}

function restoreQuestionState(targetIndex) {
  saveCurrentQuestionState()
  index.value = targetIndex
  if (props.sessionId && props.token) {
    syncDraft(props.token, props.sessionId, { current_index: targetIndex }).catch(() => {})
  }
}

async function handleSyncedEvents(e) {
  const detail = e.detail || {}
  const events = Array.isArray(detail) ? detail : (detail.events || [])
  if (detail.userId && props.user?.id && detail.userId !== props.user.id) {
    return
  }
  if (!question.value) return
  const qEvent = events.find(ev => ev.aggregate_type === 'QUESTION' && ev.aggregate_id === question.value?.id)
  if (qEvent) {
    try {
      const fresh = await getQuestion(props.token, question.value.id)
      if (fresh && fresh.version_number !== question.value.version_number) {
        questions.value[index.value] = fresh
        questionVersions.value = await listQuestionVersions(props.token, fresh.id)
        const conf = await getQuestionConflict(props.token, fresh.id)
        activeConflict.value = conf?.has_conflict ? conf.conflict : null
      }
    } catch (_) {}
  }
}

onMounted(async () => {
  window.addEventListener('online', syncOfflineEdits)
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('easyexam:events-synced', handleSyncedEvents)
  try {
    session.value = await getSession(props.token, props.sessionId)
    if (session.value?.mode === 'EXAM') {
      router.replace(`/exam/${props.sessionId}`)
      return
    }
    questions.value = await getSessionQuestions(props.token, props.sessionId)
    if (session.value) {
      const hydrated = hydrateSessionPractice(session.value, questions.value?.length || 0)
      index.value = hydrated.currentIndex
      sessionAnswers.value = hydrated.sessionAnswers
      const currentSaved = sessionAnswers.value[question.value?.id]
      if (currentSaved) {
        answer.value = Array.isArray(currentSaved.answer) ? [...currentSaved.answer] : (currentSaved.answer ?? '')
        textAnswer.value = currentSaved.textAnswer ?? ''
        result.value = currentSaved.result ?? null
        showAiPanel.value = currentSaved.showAiPanel ?? false
        selectedFsrsRating.value = currentSaved.selectedFsrsRating ?? null
      }
    }
    await syncOfflineEdits()
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('online', syncOfflineEdits)
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('easyexam:events-synced', handleSyncedEvents)
})

watch(question, async (current, oldQuestion) => {
  if (current) {
    const isDifferentQuestion = shouldResetQuestionForm(current, oldQuestion)
    if (isDifferentQuestion) {
      isEditingQuestion.value = false
      editStem.value = ''
      editType.value = 'SINGLE'
      editOptions.value = []
      editAnswer.value = ''
      editExplanation.value = ''
      editTags.value = ''
      const saved = sessionAnswers.value[current.id]
      if (saved) {
        answer.value = Array.isArray(saved.answer) ? [...saved.answer] : (saved.answer ?? '')
        textAnswer.value = saved.textAnswer ?? ''
        result.value = saved.result ?? null
        showAiPanel.value = saved.showAiPanel ?? false
        selectedFsrsRating.value = saved.selectedFsrsRating ?? null
      } else {
        answer.value = current.type === 'MULTI' ? [] : ''
        textAnswer.value = ''
        result.value = null
        showAiPanel.value = false
        selectedFsrsRating.value = null
      }
      showConflictModal.value = false
      conflictResolvedMessage.value = ''
      isWeak.value = false
      customQuery.value = ''
      editingVersionId.value = null
      fsrsRatingStatus.value = ''
    }
    answerVersions.value = await listAnswerVersions(props.token, current.id)
    try {
      questionVersions.value = await listQuestionVersions(props.token, current.id)
    } catch {
      questionVersions.value = []
    }
    try {
      const conf = await getQuestionConflict(props.token, current.id)
      activeConflict.value = conf?.has_conflict ? conf.conflict : null
    } catch {
      activeConflict.value = null
    }
    if (isDifferentQuestion) {
      try {
        const convs = await listQuestionConversations(props.token, current.id)
        if (convs?.length) {
          activeConversationId.value = convs[0].id
          chatMessages.value = await listConversationMessages(props.token, convs[0].id)
        } else {
          activeConversationId.value = null
          chatMessages.value = []
        }
      } catch {
        chatMessages.value = []
      }
    }
  }
}, { immediate: true })

async function submitRating(rating) {

  if (!question.value) return
  selectedFsrsRating.value = rating
  fsrsRatingStatus.value = t('ui.k0607')
  try {
    const res = await submitAttempt(props.token, props.sessionId, {
      question_id: question.value.id,
      user_answer: normalizedAnswer(),
      fsrs_rating: rating,
    })
    result.value = res
    saveCurrentQuestionState()
    triggerSyncEvent('PRACTICE_RATING', 'SESSION', props.sessionId, { question_id: question.value.id, rating })
    fsrsRatingStatus.value = `${t('ui.k0612')}${['', t('ui.k0608'), t('ui.k0609'), t('ui.k0610'), t('ui.k0611')][rating]}${t('ui.k0613')}`
  } catch (err) {
    fsrsRatingStatus.value = `${t('ui.k0614')}${err.detail || err.message}`
  }
}

async function submit() {
  if (!hasAnswer.value || !question.value) return
  submitting.value = true
  try {
    result.value = await submitAttempt(props.token, props.sessionId, {
      question_id: question.value.id,
      user_answer: normalizedAnswer(),
    })
    saveCurrentQuestionState()
    triggerSyncEvent('PRACTICE_ATTEMPT', 'SESSION', props.sessionId, { question_id: question.value.id })
    if (result.value?.correctness === 'INCORRECT' && (session.value?.mode === 'FSRS' || session.value?.mode === 'MISTAKE')) {
      selectedFsrsRating.value = 1
      fsrsRatingStatus.value = t('ui.k0615')
      if (sessionAnswers.value[question.value.id]) {
        sessionAnswers.value[question.value.id].selectedFsrsRating = 1
      }
    }
  } catch (err) {
    alert(`${t('ui.k0617')}${err.detail || err.message || t('ui.k0616')}`)
  } finally {
    submitting.value = false
  }
}

function toggleAiPanel() {
  showAiPanel.value = !showAiPanel.value
  saveCurrentQuestionState()
}

async function generateExplanation() {
  if (!question.value) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const saved = await generateAnswer(props.token, question.value.id, { query: t('ui.k0618') })
    answerVersions.value = [saved, ...answerVersions.value]
  } catch (err) {
    aiStatusMessage.value = `${t('ui.k0619')}${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function askCustomQuery() {
  if (!question.value || !customQuery.value.trim()) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const parentMsgId = chatMessages.value.length ? chatMessages.value[chatMessages.value.length - 1].id : null
    const res = await sendChatMessage(props.token, question.value.id, {
      content: customQuery.value.trim(),
      conversation_id: activeConversationId.value,
      parent_message_id: parentMsgId,
    })
    activeConversationId.value = res.conversation.id
    chatMessages.value.push(res.user_message)
    chatMessages.value.push(res.assistant_message)
    customQuery.value = ''
  } catch (err) {
    aiStatusMessage.value = `${t('ui.k0620')}${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function handleVerifyWeb() {
  if (!question.value) return
  aiLoading.value = true
  aiStatusMessage.value = ''
  try {
    const saved = await verifyWeb(props.token, question.value.id, { query: question.value.stem })
    answerVersions.value = [saved, ...answerVersions.value]
    if (saved.verification_status === 'UNAVAILABLE') {
      aiStatusMessage.value = t('ui.k0621')
    }
  } catch (err) {
    aiStatusMessage.value = `${t('ui.k0622')}${err.detail || err.message}`
  } finally {
    aiLoading.value = false
  }
}

async function handleGenerateVariant() {
  if (!question.value) return
  generatingVariant.value = true
  aiStatusMessage.value = ''
  try {
    await generateVariant(props.token, {
      question_id: question.value.id,
      prompt: t('ui.k0623'),
    })
    aiStatusMessage.value = t('ui.k0624')
  } catch (err) {
    aiStatusMessage.value = `${t('ui.k0625')}${err.detail || err.message}`
  } finally {
    generatingVariant.value = false
  }
}

async function adopt(answerId) {
  const saved = await adoptAnswer(props.token, answerId)
  answerVersions.value = answerVersions.value.map(item =>
    item.question_id === saved.question_id ? { ...item, is_adopted: item.id === saved.id } : item
  )
}

function startEdit(version) {
  editingVersionId.value = version.id
  editDraft.value = version.content
}

async function savePersonalExplanation() {
  if (!question.value || !editDraft.value.trim()) return
  try {
    const saved = await saveCandidate(props.token, question.value.id, {
      content: editDraft.value.trim(),
      source: 'PERSONAL',
    })
    answerVersions.value = [saved, ...answerVersions.value]
    editingVersionId.value = null
  } catch (err) {
    alert(`${t('ui.k0626')}${err.detail || err.message}`)
  }
}

// 标记薄弱与取消薄弱考点状态 (EE-013)
async function toggleWeak() {
  if (!question.value) return
  try {
    if (isWeak.value) {
      await unmarkWeak(props.token, question.value.id)
      isWeak.value = false
    } else {
      await markWeak(props.token, question.value.id)
      isWeak.value = true
    }
  } catch (err) {
    alert(`${t('ui.k0627')}${err.detail || err.message}`)
  }
}

// 斩杀此题：直接将完全掌握的题目移入斩杀题库 (EE-013)
async function handleKill() {
  if (!question.value) return
  if (!window.confirm(t('ui.k0628'))) return
  try {
    await killQuestion(props.token, question.value.id)
    alert(t('ui.k0629'))
    next()
  } catch (err) {
    alert(`${t('ui.k0506')}${err.detail || err.message}`)
  }
}

function prev() {
  if (index.value > 0) {
    slideTransition.value = 'slide-prev'
    restoreQuestionState(index.value - 1)
  }
}

function next() {
  if (index.value < questions.value.length - 1) {
    slideTransition.value = 'slide-next'
    restoreQuestionState(index.value + 1)
  }
}

function goTo(targetIdx) {
  if (targetIdx >= 0 && targetIdx < questions.value.length) {
    slideTransition.value = targetIdx > index.value ? 'slide-next' : 'slide-prev'
    restoreQuestionState(targetIdx)
    showSheetModal.value = false
  }
}

function jumpNextUnanswered() {
  const nextIdx = findNextUnansweredIndex(questions.value, sessionAnswers.value, index.value)
  if (nextIdx >= 0) {
    goTo(nextIdx)
  } else {
    alert(t('ui.k0630'))
  }
}

const answeredCount = computed(() => {
  return Object.values(sessionAnswers.value).filter(s => {
    if (s?.result) return true
    if (Array.isArray(s?.answer) && s.answer.length > 0) return true
    if (typeof s?.answer === 'string' && s.answer.trim().length > 0) return true
    if (s?.textAnswer && s.textAnswer.trim().length > 0) return true
    return false
  }).length
})

function getSheetButtonClass(qid, qIdx) {
  const isCurrent = qIdx === index.value
  const saved = sessionAnswers.value[qid]
  const res = saved?.result
  const isAnswered = Boolean(res || (Array.isArray(saved?.answer) ? saved.answer.length : saved?.answer || saved?.textAnswer))

  return {
    current: isCurrent,
    answered: isAnswered && !res,
    correct: res?.correctness === 'CORRECT',
    incorrect: res?.correctness === 'INCORRECT',
    partial: res?.correctness === 'PARTIAL',
  }
}

function handleKeyDown(e) {
  const targetTag = e.target?.tagName?.toLowerCase()
  if (targetTag === 'input' || targetTag === 'textarea' || targetTag === 'select') {
    return
  }

  const key = e.key.toUpperCase()

  // 1. Select options via A, B, C, D... or 1, 2, 3, 4...
  if (question.value?.options?.length && !result.value) {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    let optKey = null
    if (letters.includes(key)) {
      optKey = key
    } else if (['1', '2', '3', '4', '5', '6', '7', '8'].includes(e.key)) {
      const idx = parseInt(e.key, 10) - 1
      if (idx >= 0 && idx < question.value.options.length) {
        optKey = question.value.options[idx].key
      }
    }
    if (optKey) {
      const exists = question.value.options.some(o => o.key === optKey)
      if (exists) {
        e.preventDefault()
        selectOption(optKey)
        return
      }
    }
  }

  // 2. FSRS rating 1-4 when result exists and in FSRS/MISTAKE mode
  if (result.value && (session.value?.mode === 'FSRS' || session.value?.mode === 'MISTAKE')) {
    if (['1', '2', '3', '4'].includes(e.key)) {
      const rating = parseInt(e.key, 10)
      const isAllowed = (rating === 1) ||
        (rating === 2 && result.value.correctness !== 'INCORRECT') ||
        (rating >= 3 && result.value.correctness === 'CORRECT')
      if (isAllowed) {
        e.preventDefault()
        submitRating(rating)
        return
      }
    }
  }

  // 3. Submit or Next on Enter
  if (e.key === 'Enter') {
    if (!result.value && hasAnswer.value) {
      e.preventDefault()
      submit()
      return
    } else if (result.value) {
      e.preventDefault()
      if (index.value < questions.value.length - 1) {
        next()
      } else {
        complete()
      }
      return
    }
  }

  // 4. Next on Space, ArrowRight, J (allow even if !result)
  if (e.key === ' ' || e.key === 'ArrowRight' || key === 'J') {
    if (index.value < questions.value.length - 1) {
      e.preventDefault()
      next()
      return
    }
  }

  // 5. Prev on ArrowLeft, K
  if (e.key === 'ArrowLeft' || key === 'K') {
    if (index.value > 0) {
      e.preventDefault()
      prev()
      return
    }
  }

  // 6. Toggle weak on F
  if (key === 'F') {
    e.preventDefault()
    toggleWeak()
    return
  }
}


function toggleEditQuestion() {
  if (!question.value) return
  isEditingQuestion.value = !isEditingQuestion.value
  if (isEditingQuestion.value) {
    editSaveError.value = ''
    editStem.value = question.value.stem || ''
    editType.value = question.value.type || 'SINGLE'
    editOptions.value = normalizeQuestionOptions(question.value.options)
    editAnswer.value = question.value.answer || ''
    editExplanation.value = question.value.explanation || ''
    editDifficulty.value = question.value.difficulty ?? 3
    editTags.value = Array.isArray(question.value.tags) ? question.value.tags.join(', ') : (question.value.tags || '')
  }
}

function addOption() {
  const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
  const nextKey = letters[editOptions.value.length] || `Option${editOptions.value.length + 1}`
  editOptions.value.push({ key: nextKey, content: '' })
}

function removeOption(idx) {
  editOptions.value.splice(idx, 1)
}

async function saveQuestionEdit() {
  if (!question.value || !editStem.value.trim()) return
  const tagsList = editTags.value
    ? editTags.value.split(/[,，\s]+/).map(t => t.trim()).filter(Boolean)
    : []
  const payload = {
    stem: editStem.value.trim(),
    type: editType.value,
    options: normalizeQuestionOptions(editOptions.value),
    answer: editAnswer.value.trim(),
    explanation: editExplanation.value.trim(),
    difficulty: Number(editDifficulty.value) || 3,
    tags: tagsList,
    base_version_number: question.value.version_number,
    regrade_history: editRegradeHistory.value,
    apply_fsrs: true,
    allow_stale_branch: true,
  }
  const storageKey = 'easyexam_offline_question_edits'
  const userScopedKey = getOfflineQueueKey()
  const uid = auth.user?.value?.id || auth.user?.value?.username || 'user'
  const queueItem = { userId: uid, questionId: question.value.id, payload, queuedAt: Date.now() }
  if (!window.navigator.onLine) {
    const queue = JSON.parse(localStorage.getItem(storageKey) || '[]')
    queue.push(queueItem)
    localStorage.setItem(storageKey, JSON.stringify(queue))
    localStorage.setItem(userScopedKey, JSON.stringify(queue))
    offlineNotice.value = t('ui.k0631')
    offlineRetryAvailable.value = true
    editSaveError.value = ''
    isEditingQuestion.value = false
    return
  }
  let updated
  try {
    const currentToken = authToken.value
    updated = await updateQuestion(currentToken, question.value.id, payload)
  } catch (err) {
    if (isNetworkFailure(err)) {
      const queue = JSON.parse(localStorage.getItem(storageKey) || '[]')
      queue.push(queueItem)
      localStorage.setItem(storageKey, JSON.stringify(queue))
      localStorage.setItem(userScopedKey, JSON.stringify(queue))
      offlineNotice.value = t('ui.k0632')
      offlineRetryAvailable.value = true
      editSaveError.value = ''
      isEditingQuestion.value = false
    } else {
      offlineNotice.value = ''
      offlineRetryAvailable.value = false
      editSaveError.value = err?.message || t('api_errors.REQUEST_FAILED')
      isEditingQuestion.value = true
    }
    return
  }
  const currentToken = authToken.value
  triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
  isEditingQuestion.value = false
  editSaveError.value = ''
  questions.value[index.value] = updated
  const queue = JSON.parse(localStorage.getItem(storageKey) || '[]').filter(item =>
    !(item.blocked && item.questionId === updated.id))
  localStorage.setItem(storageKey, JSON.stringify(queue))
  localStorage.setItem(userScopedKey, JSON.stringify(queue))
  try {
    questionVersions.value = await listQuestionVersions(currentToken, updated.id)
    const conf = await getQuestionConflict(currentToken, updated.id)
    activeConflict.value = conf?.has_conflict ? conf.conflict : null
  } catch (err) {
    console.error('Question updated but its follow-up refresh failed:', err)
  }
}

function isNetworkFailure(err) {
  return err?.status === 0 || err?.code === 'NETWORK_ERROR'
}

let isSyncing = false
let syncQueued = false

async function processOfflineQueue() {
  const storageKey = 'easyexam_offline_question_edits'
  const userScopedKey = getOfflineQueueKey()
  const uid = auth.user?.value?.id || auth.user?.value?.username || 'user'
  const currentToken = authToken.value
  const raw = localStorage.getItem(storageKey) || localStorage.getItem(userScopedKey)
  if (!raw) return
  let queue = JSON.parse(raw)
  if (!queue.length) return
  const userItems = queue.filter(item => !item.userId || item.userId === uid || item.userId === auth.user?.value?.id || item.userId === auth.user?.value?.username || item.userId === 'user')
  if (!userItems.length) return
  const pendingItems = userItems.filter(item => !item.blocked)
  const blockedItems = userItems.filter(item => item.blocked)
  if (!pendingItems.length) {
    offlineRetryAvailable.value = false
    offlineNotice.value = blockedItems[0]?.error || ''
    return
  }
  offlineRetryAvailable.value = true
  offlineNotice.value = t('ui.k0633')

  // Process atomically item-by-item: NEVER wipe queue before confirmed completion!
  while (true) {
    const itemIndex = queue.findIndex(item => !item.blocked && (!item.userId || item.userId === uid || item.userId === auth.user?.value?.id || item.userId === auth.user?.value?.username || item.userId === 'user'))
    if (itemIndex < 0) break
    const item = queue[itemIndex]
    let updated
    try {
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          updated = await updateQuestion(currentToken, item.questionId, item.payload)
          break
        } catch (err) {
          if (attempt < 2 && isNetworkFailure(err)) {
            await new Promise(r => setTimeout(r, 150))
            continue
          }
          throw err
        }
      }
    } catch (err) {
      console.error('Failed to sync offline question edit:', err)
      if (isNetworkFailure(err)) break
      item.blocked = true
      item.error = err?.message || t('api_errors.REQUEST_FAILED')
      localStorage.setItem(storageKey, JSON.stringify(queue))
      localStorage.setItem(userScopedKey, JSON.stringify(queue))
      if (question.value?.id === item.questionId) {
        editStem.value = item.payload.stem ?? ''
        editType.value = item.payload.type ?? 'SINGLE'
        editOptions.value = item.payload.options ?? []
        editAnswer.value = item.payload.answer ?? ''
        editExplanation.value = item.payload.explanation ?? ''
        editDifficulty.value = item.payload.difficulty ?? 3
        editTags.value = (item.payload.tags ?? []).join(', ')
        editRegradeHistory.value = item.payload.regrade_history ?? false
        isEditingQuestion.value = true
        editSaveError.value = item.error
      }
      continue
    }
    triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
    if (question.value && question.value.id === item.questionId) {
      questions.value[index.value] = updated
      try {
        questionVersions.value = await listQuestionVersions(currentToken, updated.id)
        const conf = await getQuestionConflict(currentToken, updated.id)
        activeConflict.value = conf?.has_conflict ? conf.conflict : null
      } catch (err) {
        console.error('Question updated but its follow-up refresh failed:', err)
      }
    }
    // Remove item only after the update itself is confirmed.
    queue.splice(itemIndex, 1)
    localStorage.setItem(storageKey, JSON.stringify(queue))
    localStorage.setItem(userScopedKey, JSON.stringify(queue))
  }
  const remainingItems = queue.filter(item => !item.userId || item.userId === uid || item.userId === auth.user?.value?.id || item.userId === auth.user?.value?.username || item.userId === 'user')
  const retryableItems = remainingItems.filter(item => !item.blocked)
  const remainingBlockedItems = remainingItems.filter(item => item.blocked)
  offlineRetryAvailable.value = retryableItems.length > 0
  if (retryableItems.length) {
    offlineNotice.value = `${t('ui.k0634')} ${retryableItems.length} ${t('ui.k0635')}`
  } else if (remainingBlockedItems.length) {
    offlineNotice.value = remainingBlockedItems[0].error || ''
  } else {
    offlineNotice.value = ''
    localStorage.removeItem(storageKey)
    localStorage.removeItem(userScopedKey)
  }
}

async function syncOfflineEdits() {
  if (isSyncing) {
    syncQueued = true
    return
  }
  isSyncing = true
  try {
    do {
      syncQueued = false
      await processOfflineQueue()
    } while (syncQueued)
  } finally {
    isSyncing = false
  }
}

async function handleAdoptQuestionVersion(targetVer) {
  try {
    const currentToken = authToken.value
    let updated
    if (activeConflict.value) {
      updated = await resolveQuestionConflict(currentToken, question.value.id, targetVer.version_number)
      activeConflict.value = null
    } else {
      updated = await updateQuestion(currentToken, question.value.id, {
        stem: targetVer.stem,
        type: targetVer.type || question.value.type || 'SINGLE',
        options: targetVer.options || question.value.options || [],
        answer: targetVer.answer || question.value.answer || '',
        explanation: targetVer.explanation || question.value.explanation || '',
        difficulty: targetVer.difficulty ?? question.value.difficulty ?? 3,
        tags: targetVer.tags || question.value.tags || [],
        allow_stale_branch: true,
      })
    }
    conflictResolvedMessage.value = `${t('ui.k0636')}${targetVer.version_number} ${t('ui.k0637')}`
    triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
    questions.value[index.value] = updated
    questionVersions.value = await listQuestionVersions(currentToken, updated.id)
  } catch (err) {
    alert(`${t('ui.k0638')}${err.detail || err.message}`)
  }
}

const showCompleteConfirmModal = ref(false)
const practiceReport = ref(null)
const completing = ref(false)

function complete() {
  const total = questions.value.length
  const answered = answeredCount.value
  const unanswered = Math.max(0, total - answered)
  if (unanswered > 0) {
    showCompleteConfirmModal.value = true
  } else {
    handleConfirmComplete()
  }
}

async function handleConfirmComplete() {
  completing.value = true
  try {
    const report = await completeSession(props.token, props.sessionId)
    practiceReport.value = report
    showCompleteConfirmModal.value = false
    emit('completed', report)
  } catch (err) {
    alert(`${t('ui.k0639')}${err.detail || err.message}`)
  } finally {
    completing.value = false
  }
}

function handleRestartPractice() {
  practiceReport.value = null
  emit('back')
}
</script>

<style scoped>
.focus-mode {
  min-height: 100vh;
  background: var(--paper);
  color: var(--ink);
  padding-top: var(--topbar-h);
  padding-bottom: 76px;
}

/* ---------- top bar ---------- */
.focus-topbar {
  position: fixed;
  inset: 0 0 auto;
  z-index: 40;
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px;
  background: color-mix(in srgb, var(--paper) 94%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.focus-top-left,
.focus-top-right {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.focus-top-left { gap: 12px; }
.focus-exit {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--ink-2);
  font-family: var(--font-sans);
  font-size: 12.5px;
  cursor: pointer;
  padding: 4px 2px;
}
.focus-exit:hover { color: var(--ink); }
.focus-sep {
  width: 1px;
  height: 18px;
  background: var(--line);
}
.focus-context {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.focus-mode-label {
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: .02em;
  white-space: nowrap;
}
.focus-type {
  font-size: 11.5px;
  color: var(--ink-3);
  white-space: nowrap;
}
.focus-counter {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-2);
  font-family: var(--font-mono);
  font-size: 11.5px;
  padding: 5px 9px;
  border-radius: var(--r-xs);
  cursor: pointer;
}
.focus-counter:hover { border-color: var(--line-strong); color: var(--ink); }
.focus-menu {
  position: absolute;
  top: calc(var(--topbar-h) - 4px);
  right: 0;
  min-width: 168px;
  padding: 5px;
  background: var(--surface);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-2);
  z-index: 5;
}
.focus-more { position: relative; }
.focus-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  background: transparent;
  color: var(--ink-2);
  font-family: var(--font-sans);
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
}
.focus-menu-item:hover { background: var(--surface-2); color: var(--ink); }
.focus-menu-item.is-danger { color: var(--bad); }
.focus-finish { white-space: nowrap; }

.icon-btn.is-on { color: var(--flag); border-color: var(--warn-line); background: var(--warn-soft); }

/* ---------- layout ---------- */
.focus-layout {
  display: grid;
  grid-template-columns: minmax(0, var(--reading-w)) 244px;
  gap: clamp(32px, 5vw, 72px);
  justify-content: center;
  align-items: start;
  width: min(100% - 48px, 1120px);
  margin: 0 auto;
  padding: 44px 0 56px;
}
.focus-reading { min-width: 0; }
.focus-sheet {
  padding-bottom: 8px;
}
.focus-sheet .q-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
  font-family: var(--font-sans);
  font-size: 11.5px;
  letter-spacing: .06em;
  color: var(--ink-3);
  text-transform: uppercase;
}
.focus-sheet .q-stem {
  font-family: var(--font-serif);
  font-size: 20px;
  line-height: 1.72;
  letter-spacing: .01em;
  margin-bottom: 30px;
  white-space: pre-wrap;
}
.opt-list {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--line);
}
.opt {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) 20px;
  align-items: start;
  gap: 10px;
  width: 100%;
  padding: 14px 10px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  text-align: left;
  font-family: var(--font-serif);
  font-size: 16.5px;
  line-height: 1.65;
  cursor: pointer;
  transition: background .14s var(--ease);
}
.opt:hover:not(:disabled) { background: var(--surface-2); }
.opt:disabled { cursor: default; }
.opt-key {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-3);
}
.opt-text { white-space: pre-wrap; }
.opt-mark { display: flex; justify-content: flex-end; padding-top: 4px; }
.opt-mark.ok { color: var(--ok); }
.opt-mark.bad { color: var(--bad); }

/* ---------- feedback ---------- */
.feedback-block {
  margin-top: 34px;
  padding-top: 26px;
  border-top: 1px solid var(--line-strong);
  animation: focus-rise .22s var(--ease);
}
@keyframes focus-rise {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}
.verdict-line {
  display: flex;
  align-items: baseline;
  gap: 9px;
  font-family: var(--font-sans);
  font-size: 14px;
  margin-bottom: 12px;
}
.verdict-line strong { font-weight: 650; letter-spacing: .01em; }
.verdict-mark { display: inline-flex; align-self: center; }
.verdict-line.correct { color: var(--ok); }
.verdict-line.partial { color: var(--warn); }
.verdict-line.incorrect { color: var(--bad); }
.verdict-line.ungraded { color: var(--ink-2); }
.verdict-ratio {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--ink-3);
}
.answer-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
  font-family: var(--font-sans);
  font-size: 12.5px;
  color: var(--ink-3);
}
.answer-line .ans {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--ink);
  letter-spacing: .04em;
}
.answer-yours { margin-left: auto; }
.explain-block { padding-top: 22px; }
.explain-body {
  margin-top: 10px;
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.8;
  color: var(--ink-2);
  white-space: pre-wrap;
}
.fsrs-block {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
}
.fsrs-buttons { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.fsrs-buttons .btn.is-on { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }
.fsrs-buttons .mono { color: var(--ink-3); font-size: 10.5px; }

/* ---------- AI (secondary) ---------- */
.ai-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 30px;
  padding: 14px 0;
  border-top: 1px solid var(--line);
}
.ai-entry-text { display: flex; flex-direction: column; gap: 3px; }
.ai-entry-title {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-2);
}
.ai-panel {
  margin-top: 8px;
  padding: 18px;
  background: var(--surface);
  border: 1px solid var(--line);
}
.ai-toolbar { display: flex; justify-content: space-between; gap: 12px; }
.ai-actions { display: flex; flex-wrap: wrap; gap: 7px; }
.ai-ask { display: flex; gap: 8px; margin-top: 12px; }
.ai-ask .input { flex: 1; }
.ai-chat { margin-top: 16px; }
.chat-row {
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}
.chat-row:last-child { border-bottom: 0; }
.chat-meta {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-sans);
  font-size: 10.5px;
  color: var(--ink-3);
  margin-bottom: 4px;
}
.chat-sender { font-weight: 600; }
.chat-text {
  font-family: var(--font-serif);
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--ink-2);
  white-space: pre-wrap;
  margin: 0;
}
.ai-versions { margin-top: 18px; }
.ai-version {
  padding: 12px 0;
  border-top: 1px solid var(--line);
}
.ai-version-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.ai-version-head .dim { margin-left: auto; }
.ai-version-text {
  font-family: var(--font-serif);
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--ink-2);
  white-space: pre-wrap;
  margin: 0 0 8px;
}
.ai-evidence ul { margin: 6px 0 0; padding-left: 18px; }
.ai-evidence li { font-size: 12px; color: var(--ink-3); line-height: 1.6; margin-bottom: 4px; }
.ai-evidence a { color: var(--brand); margin-left: 6px; }
.ai-version-actions { display: flex; gap: 7px; margin-top: 9px; }
.ai-version-edit .textarea { margin-top: 4px; }
.ai-version.is-adopted { background: color-mix(in srgb, var(--brand-soft) 46%, transparent); }

/* ---------- rail ---------- */
.focus-rail {
  position: sticky;
  top: calc(var(--topbar-h) + 24px);
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding-top: 4px;
}
.rail-block { padding-bottom: 20px; border-bottom: 1px solid var(--line); }
.rail-block:last-child { border-bottom: 0; padding-bottom: 0; }
.rail-title {
  font-family: var(--font-sans);
  font-size: 10.5px;
  font-weight: 650;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--ink-3);
  margin-bottom: 10px;
}
.focus-progress { display: flex; flex-direction: column; gap: 7px; }
.focus-progress .mono { font-size: 12px; color: var(--ink-2); }
.progress-track {
  height: 3px;
  background: var(--surface-3);
  overflow: hidden;
}
.progress-track i {
  display: block;
  height: 100%;
  background: var(--brand);
  transition: width .3s var(--ease);
}
.rail-note { margin-top: 8px; font-size: 11.5px; color: var(--ink-4); }
.sheet-mini {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
}
.sheet-num {
  min-width: 26px;
  height: 26px;
  padding: 0 4px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10.5px;
  border-radius: var(--r-xs);
  cursor: pointer;
}
.sheet-num:hover { border-color: var(--line-strong); color: var(--ink); }
.sheet-num.current { border-color: var(--ink); color: var(--ink); font-weight: 700; }
.sheet-num.answered { background: var(--surface-2); color: var(--ink-2); }
.sheet-num.correct { background: var(--ok-soft); border-color: var(--ok-line); color: var(--ok); }
.sheet-num.incorrect { background: var(--bad-soft); border-color: var(--bad-line); color: var(--bad); }
.sheet-num.partial { background: var(--warn-soft); border-color: var(--warn-line); color: var(--warn); }
.rail-keys { display: flex; flex-direction: column; gap: 7px; }
.rail-keys span {
  display: flex;
  align-items: center;
  gap: 7px;
  font-family: var(--font-sans);
  font-size: 11.5px;
  color: var(--ink-3);
}
kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 19px;
  height: 19px;
  padding: 0 4px;
  border: 1px solid var(--line-strong);
  border-bottom-width: 2px;
  border-radius: var(--r-xs);
  background: var(--surface);
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-2);
}
.rail-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}

/* ---------- action bar ---------- */
.focus-actionbar {
  position: fixed;
  inset: auto 0 0;
  z-index: 40;
  background: color-mix(in srgb, var(--paper) 94%, transparent);
  backdrop-filter: blur(10px);
  border-top: 1px solid var(--line);
  padding: 10px 18px calc(10px + env(safe-area-inset-bottom, 0px));
}
.focus-action-inner {
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(100%, 1120px);
  margin: 0 auto;
}
.focus-action-inner .spacer { flex: 1; }
.focus-actionbar .focus-counter { border-color: transparent; background: transparent; }

/* ---------- dialogs ---------- */
.focus-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(20, 23, 19, .42);
  backdrop-filter: blur(2px);
}
.focus-dialog {
  width: min(100%, 460px);
  max-height: 86vh;
  overflow: auto;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-2);
}
.sheet-dialog { width: min(100%, 540px); }
.report-dialog { width: min(100%, 560px); }
.dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line);
}
.dialog-title {
  display: block;
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 650;
  letter-spacing: .01em;
}
.dialog-sub {
  display: block;
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--ink-3);
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px 18px;
  border-top: 1px solid var(--line);
}
.sheet-body { padding: 18px 20px 20px; }
.sheet-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 14px;
  font-size: 11.5px;
  color: var(--ink-3);
}
.sheet-legend span { display: inline-flex; align-items: center; gap: 6px; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot.blank { background: var(--surface-3); border: 1px solid var(--line-strong); }
.dot.ok { background: var(--ok); }
.dot.bad { background: var(--bad); }
.dot.part { background: var(--warn); }
.sheet-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 6px;
  margin-bottom: 16px;
}
.sheet-grid .sheet-num { height: 32px; }
.report-body { padding: 22px 20px; }
.report-stats { margin-bottom: 18px; }
.report-counts { display: flex; flex-wrap: wrap; gap: 8px; }
.help-body { padding: 18px 20px 22px; display: flex; flex-direction: column; gap: 20px; }
.help-keys { display: flex; flex-direction: column; gap: 8px; margin-top: 9px; }
.help-keys span { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; font-size: 12px; color: var(--ink-2); }
.help-text { margin: 7px 0 0; font-size: 12.5px; line-height: 1.65; color: var(--ink-3); }
.confirm-body { padding: 18px 20px 6px; }
.confirm-body p { margin: 0 0 10px; font-size: 13px; line-height: 1.65; color: var(--ink-2); }
.confirm-warn { color: var(--warn); }
.confirm-text { color: var(--ink-2); }

/* ---------- inline editor / conflict ---------- */
.edit-panel {
  margin-bottom: 28px;
  padding: 18px;
  background: var(--surface);
  border: 1px solid var(--line-strong);
}
.edit-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.edit-panel-title {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: .02em;
}
.edit-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.edit-options { margin: 4px 0 12px; }
.edit-options-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.edit-option-row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) 28px;
  gap: 7px;
  align-items: center;
  margin-bottom: 6px;
}
.edit-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--ink-2);
  margin: 4px 0 14px;
}
.edit-panel-actions { display: flex; justify-content: flex-end; gap: 8px; }
.conflict-banner {
  margin-bottom: 26px;
  padding: 14px 16px;
  background: var(--warn-soft);
  border: 1px solid var(--warn-line);
}
.conflict-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--warn);
}
.conflict-head .btn { margin-left: auto; }
.conflict-resolved { margin: 8px 0 0; font-size: 12px; color: var(--ok); }
.conflict-list { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.conflict-version {
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--line);
}
.conflict-version.is-current { border-color: var(--brand-line); }
.conflict-version-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
  font-size: 11px;
}
.conflict-stem {
  margin: 0 0 8px;
  font-family: var(--font-serif);
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--ink-2);
}
.conflict-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 11.5px;
  color: var(--ink-3);
}
.focus-offline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
}
.focus-offline .btn { margin-left: auto; }
.reading-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  color: var(--ink-4);
}

/* ---------- states ---------- */
.focus-loading {
  width: min(100% - 48px, var(--reading-w));
  margin: 48px auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.focus-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 96px 24px;
  text-align: center;
}
.focus-empty .empty-desc { margin-bottom: 12px; }

/* ---------- responsive ---------- */
@media (max-width: 1024px) {
  .focus-layout {
    grid-template-columns: minmax(0, var(--reading-w));
    width: min(100% - 40px, var(--reading-w));
    padding-top: 34px;
  }
  .focus-rail { display: none; }
}
@media (max-width: 768px) {
  .focus-mode { padding-bottom: 72px; }
  .focus-topbar { padding: 0 12px; gap: 8px; }
  .focus-type,
  .focus-sep { display: none; }
  .focus-layout { width: 100%; padding: 20px 16px 40px; }
  .focus-sheet .q-stem { font-size: 18.5px; }
  .opt { font-size: 16px; padding: 13px 6px; }
  .focus-actionbar { padding: 8px 12px calc(8px + env(safe-area-inset-bottom, 0px)); }
  .focus-action-inner .focus-counter { display: none; }
  .focus-action-inner .spacer { display: none; }
  .focus-action-inner > .btn { flex: 1; justify-content: center; }
  .focus-action-inner > .btn-primary { flex: 1.6; }
  .edit-grid { grid-template-columns: 1fr 1fr; }
  .sheet-grid { grid-template-columns: repeat(5, 1fr); }
}
@media (max-width: 420px) {
  .focus-mode-label { max-width: 96px; overflow: hidden; text-overflow: ellipsis; }
  .focus-exit span { display: none; }
  .focus-sheet .q-stem { font-size: 17.5px; line-height: 1.7; }
  .focus-sheet .q-meta { gap: 8px; font-size: 10.5px; }
  .opt { grid-template-columns: 24px minmax(0, 1fr) 16px; font-size: 15.5px; }
  .edit-grid { grid-template-columns: 1fr; }
  .ai-toolbar { flex-direction: column; }
  .answer-yours { margin-left: 0; }
  .verdict-ratio { margin-left: 0; }
  .focus-finish { padding-left: 9px; padding-right: 9px; }
  .focus-overlay { padding: 10px; }
}
</style>
