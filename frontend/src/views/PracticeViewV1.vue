<template>
  <main class="practice-page" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
    <header class="page-header compact-header">
      <div class="header-left-bar">
        <button type="button" class="btn-back" @click="handleBack">{{ t('ui.k0510') }}</button>
        <div class="header-titles">
          <h1 class="practice-title">{{ session?.mode === 'ELIMINATION' ? t('ui.k0734') : session?.mode === 'FSRS' ? t('ui.k0735') : session?.mode === 'PRACTICE' ? t('home.sequential_practice') : t('ui.k0736') }}</h1>
          <span v-if="question" class="badge-type-pill">{{ formatType(question.type) }}</span>
          <button v-if="question" type="button" class="badge-index-pill btn-sheet-trigger-pill" @click="showSheetModal = true" :title="t('ui.k0511')">
            <small>{{ index + 1 }} / {{ questions.length }}</small> <LinearIcon name="layers" size="13" /> {{ t('ui.k0093') }}
          </button>
        </div>
      </div>
      <div class="header-actions">
        <ThemeToggle compact class="desktop-only-btn" />
        <LocaleToggle compact class="desktop-only-btn" />
        <!-- 桌面端平铺操作 -->
        <button type="button" class="secondary-btn btn-help-guide desktop-only-btn" @click="showHelpTip = !showHelpTip" :title="t('ui.k0512')">
          <LinearIcon name="zap" size="13" /> {{ t('ui.k0513') }}
        </button>
        <button type="button" class="btn-flag desktop-only-btn" :class="{ active: isWeak }" @click="toggleWeak">
          {{ isWeak ? t('ui.k0737') : t('ui.k0738') }}
        </button>
        <button type="button" class="btn-kill desktop-only-btn" @click="handleKill">
          {{ t('ui.k0486') }}
        </button>
        <button type="button" class="btn-edit-question desktop-only-btn" @click="toggleEditQuestion">
          {{ isEditingQuestion ? t('ui.k0739') : t('ui.k0740') }}
        </button>
        <button type="button" class="primary btn-header-complete desktop-only-btn" @click="complete">{{ t('ui.k0514') }}</button>

        <!-- 移动端右上角“更多 ⋯”菜单 -->
        <div class="mobile-more-wrapper mobile-only-inline">
          <button type="button" class="btn-help-mobile" @click="showHelpTip = !showHelpTip" :title="t('ui.k0513')">
            <LinearIcon name="zap" size="13" />
          </button>
          <button type="button" class="btn-more-menu" @click="showMoreMenu = !showMoreMenu" :aria-label="t('ui.k0515')">
            ⋯
          </button>
          <div v-if="showMoreMenu" class="mobile-dropdown-menu" @click="showMoreMenu = false">
            <button type="button" class="dropdown-item" :class="{ active: isWeak }" @click="toggleWeak">
              {{ isWeak ? t('ui.k0741') : t('ui.k0738') }}
            </button>
            <button type="button" class="dropdown-item text-danger" @click="handleKill">
              {{ t('ui.k0486') }}
            </button>
            <button type="button" class="dropdown-item" @click="toggleEditQuestion">
              {{ isEditingQuestion ? t('ui.k0739') : t('ui.k0740') }}
            </button>
            <button type="button" class="dropdown-item text-danger" @click="complete">
              {{ t('ui.k0516') }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- 快捷键与操作指南弹窗 (轻量弹出，零侵占刷题黄金视野) -->
    <div v-if="showHelpTip" class="help-tip-backdrop" @click.self="showHelpTip = false">
      <div class="help-tip-dialog" role="dialog" aria-modal="true">
        <div class="help-tip-header">
          <h3><LinearIcon name="zap" size="15" /> {{ t('ui.k0517') }}</h3>
          <button type="button" class="btn-close-tip" @click="showHelpTip = false">✕</button>
        </div>
        <div class="help-tip-body">
          <div class="tip-section">
            <strong><LinearIcon name="compass" size="14" /> {{ t('ui.k0518') }}</strong>
            <ul>
              <li><kbd>A</kbd> / <kbd>B</kbd> / <kbd>C</kbd> / <kbd>D</kbd>{{ t('ui.k0519') }}</li>
              <li><kbd>Enter ↵</kbd>{{ t('ui.k0520') }}</li>
              <li><kbd>Space ␣</kbd> {{ t('ui.k0521') }} <kbd>→</kbd>{{ t('ui.k0522') }}</li>
              <li><kbd>←</kbd> {{ t('ui.k0521') }} <kbd>K</kbd>{{ t('ui.k0523') }}</li>
              <li><kbd>F</kbd>{{ t('ui.k0524') }}</li>
              <li><kbd>1</kbd> ~ <kbd>4</kbd>{{ t('ui.k0525') }}</li>
            </ul>
          </div>
          <div class="tip-section">
            <strong><LinearIcon name="maximize" size="14" /> {{ t('ui.k0526') }}</strong>
            <p>{{ t('ui.k0527') }}</p>
          </div>
          <div class="tip-section">
            <strong><LinearIcon name="layers" size="14" /> {{ t('ui.k0528') }}</strong>
            <p>{{ t('ui.k0529') }} <strong>“{{ index + 1 }}/{{ questions.length }} {{ t('ui.k0530') }}</strong> {{ t('ui.k0531') }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 答题卡抽屉 / 快速跳转面板 (移动端底部抽屉，桌面端居中弹窗) -->
    <div v-if="showSheetModal" class="sheet-modal-backdrop" @click.self="showSheetModal = false" data-testid="practice-sheet-drawer">
      <div class="sheet-modal-drawer">
        <div class="sheet-drawer-header">
          <div class="sheet-drawer-title">
            <h3>{{ t('ui.k0093') }}</h3>
            <span class="sheet-stats-pill">{{ t('ui.k0096') }} {{ answeredCount }} / {{ questions.length }} {{ t('ui.k0101') }}</span>
          </div>
          <button type="button" class="btn-close-sheet" @click="showSheetModal = false">✕</button>
        </div>

        <div class="sheet-quick-actions">
          <button type="button" class="btn-jump-next-unanswered" @click="jumpNextUnanswered">
            {{ t('ui.k0532') }}
          </button>
        </div>

        <div class="sheet-legend-bar">
          <span class="legend-item"><span class="legend-dot unanswered"></span> {{ t('ui.k0099') }}</span>
          <span class="legend-item"><span class="legend-dot correct"></span> {{ t('ui.k0067') }}</span>
          <span class="legend-item"><span class="legend-dot incorrect"></span> {{ t('ui.k0075') }}</span>
          <span class="legend-item"><span class="legend-dot partial"></span> {{ t('ui.k0533') }}</span>
        </div>

        <div class="sheet-numbers-grid">
          <button
            v-for="(qItem, qIdx) in questions"
            :key="qItem.id"
            type="button"
            class="sheet-num-btn"
            :class="getSheetButtonClass(qItem.id, qIdx)"
            @click="goTo(qIdx)"
          >
            {{ qIdx + 1 }}
          </button>
        </div>
      </div>
    </div>

    <!-- 练习完成交卷结果报告卡片 (优雅模态框) -->
    <div v-if="practiceReport" class="sheet-modal-backdrop" data-testid="practice-report-modal">
      <div class="practice-result-card-modal">
        <div class="result-card-badge"><LinearIcon name="check" size="14" /> {{ t('ui.k0534') }}</div>
        <h2>{{ t('ui.k0535') }}</h2>
        <div class="result-stats-grid">
          <div class="result-stat-box">
            <small>{{ t('ui.k0063') }}</small>
            <strong class="text-primary">{{ practiceReport.score }}</strong>
          </div>
          <div class="result-stat-box">
            <small>{{ t('ui.k0064') }}</small>
            <strong :class="practiceReport.accuracy >= 80 ? 'text-success' : practiceReport.accuracy >= 60 ? 'text-warning' : 'text-danger'">
              {{ practiceReport.accuracy }}%
            </strong>
          </div>
          <div class="result-stat-box">
            <small>{{ t('ui.k0536') }}</small>
            <strong>{{ practiceReport.answered_count }} / {{ practiceReport.total_questions }}</strong>
          </div>
          <div class="result-stat-box">
            <small>{{ t('ui.k0537') }}</small>
            <strong>{{ formatRemainingTime ? formatRemainingTime(practiceReport.time_spent || 0) : `${practiceReport.time_spent || 0}${t('ui.k0742')}` }}</strong>
          </div>
        </div>
        <div class="result-counts-bar">
          <span class="count-tag text-success">{{ t('ui.k0538') }} {{ practiceReport.correct_count }}</span>
          <span v-if="practiceReport.partial_count" class="count-tag text-warning">{{ t('ui.k0539') }} {{ practiceReport.partial_count }}</span>
          <span class="count-tag text-danger">{{ t('ui.k0540') }} {{ practiceReport.incorrect_count }}</span>
          <span class="count-tag text-muted">{{ t('ui.k0541') }} {{ practiceReport.unanswered_count }}</span>
        </div>
        <div class="result-card-actions">
          <button type="button" class="primary" @click="handleBack">{{ t('ui.k0081') }}</button>
          <button type="button" class="secondary-btn" @click="handleRestartPractice">{{ t('ui.k0542') }}</button>
        </div>
      </div>
    </div>

    <!-- 交卷前未答题目确认提示弹窗 -->
    <div v-if="showCompleteConfirmModal" class="sheet-modal-backdrop" @click.self="showCompleteConfirmModal = false">
      <div class="confirm-submit-dialog">
        <h3>{{ t('ui.k0543') }}</h3>
        <p v-if="questions.length - answeredCount > 0" class="confirm-warning-desc">
          {{ t('ui.k0544') }} <strong class="text-danger">{{ questions.length - answeredCount }}</strong> {{ t('ui.k0545') }}
        </p>
        <p v-else class="confirm-info-desc">
          {{ t('ui.k0546') }} {{ questions.length }} {{ t('ui.k0547') }}
        </p>
        <div class="confirm-dialog-actions">
          <button type="button" class="secondary-btn" @click="showCompleteConfirmModal = false">{{ t('ui.k0548') }}</button>
          <button type="button" class="primary" :disabled="completing" @click="handleConfirmComplete">
            {{ completing ? t('ui.k0658') : t('ui.k0659') }}
          </button>
        </div>
      </div>
    </div>


    <p v-if="loading">{{ t('ui.k0549') }}</p>
    <section v-else-if="question" class="question-card">
      <!-- 离线暂存提示 -->
      <div v-if="offlineNotice" class="offline-banner" data-testid="offline-banner">
        <span>{{ offlineNotice }}</span>
        <button type="button" class="btn-sync-offline" @click="syncOfflineEdits">{{ t('ui.k0550') }}</button>
      </div>

      <!-- 题目编辑面板 (EE-011: 支持完整题干、选项、题型、答案、难度、解析与标签编辑) -->
      <div v-if="isEditingQuestion" class="question-edit-panel" data-testid="question-edit-panel">
        <h3>{{ t('ui.k0551') }}{{ question.version_number }})</h3>
        <div class="edit-form-grid">
          <label class="form-row">
            <span>{{ t('ui.k0211') }}</span>
            <textarea v-model="editStem" class="input-edit-stem" rows="3"></textarea>
          </label>
          <div class="form-row-group">
            <label>
              <span>{{ t('ui.k0366') }}</span>
              <select v-model="editType" class="select-edit-type">
                <option value="SINGLE">{{ t('ui.k0050') }}</option>
                <option value="MULTI">{{ t('ui.k0051') }}</option>
                <option value="JUDGE">{{ t('ui.k0052') }}</option>
                <option value="ESSAY">{{ t('ui.k0166') }}</option>
              </select>
            </label>
            <label>
              <span>{{ t('ui.k0552') }}</span>
              <select v-model.number="editDifficulty" class="select-edit-diff">
                <option :value="1">{{ t('ui.k0168') }}</option>
                <option :value="2">{{ t('ui.k0169') }}</option>
                <option :value="3">{{ t('ui.k0170') }}</option>
                <option :value="4">{{ t('ui.k0171') }}</option>
                <option :value="5">{{ t('ui.k0172') }}</option>
              </select>
            </label>
            <label>
              <span>{{ t('ui.k0080') }}</span>
              <input v-model="editAnswer" class="input-edit-answer" :placeholder="t('ui.k0553')" />
            </label>
          </div>
          <div v-if="editType === 'SINGLE' || editType === 'MULTI' || editType === 'JUDGE'" class="options-edit-block">
            <div class="options-header">
              <span>{{ t('ui.k0370') }}</span>
              <button type="button" class="btn-add-option" @click="addOption">{{ t('ui.k0554') }}</button>
            </div>
            <div v-for="(opt, oIdx) in editOptions" :key="oIdx" class="option-edit-row">
              <input v-model="opt.key" class="opt-key-input" :placeholder="t('ui.k0176')" style="width: 3.5rem;" />
              <input v-model="opt.content" class="opt-text-input" :placeholder="t('ui.k0555')" style="flex: 1;" />
              <button type="button" class="btn-del-option" @click="removeOption(oIdx)">{{ t('ui.k0256') }}</button>
            </div>
          </div>
          <label class="form-row">
            <span>{{ t('ui.k0213') }}</span>
            <textarea v-model="editExplanation" class="input-edit-exp" rows="2"></textarea>
          </label>
          <label class="form-row">
            <span>{{ t('ui.k0556') }}</span>
            <input v-model="editTags" class="input-edit-tags" :placeholder="t('ui.k0557')" />
          </label>
          <div class="edit-regrade-option" style="margin: 0.5rem 0; padding: 0.5rem; background: var(--bg-page); border-radius: 6px;">
            <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; cursor: pointer;">
              <input type="checkbox" v-model="editRegradeHistory" class="checkbox-regrade-history" />
              <span>{{ t('ui.k0558') }}</span>
            </label>
          </div>
        </div>
        <div class="edit-actions">
          <button type="button" @click="isEditingQuestion = false">{{ t('ui.k0149') }}</button>
          <button type="button" class="primary btn-save-question-edit" @click="saveQuestionEdit">{{ t('ui.k0559') }}</button>
        </div>
      </div>

      <!-- 多端并发修改冲突保留与选择横幅 (基于服务端真实冲突检测) -->
      <div v-if="activeConflict || conflictResolvedMessage" class="conflict-banner" data-testid="conflict-banner">
        <div v-if="activeConflict" class="conflict-header">
          <span class="conflict-badge">{{ t('ui.k0560') }}{{ activeConflict.base_version_number }} {{ t('ui.k0561') }}{{ activeConflict.server_version_number }} {{ t('ui.k0562') }}</span>
          <button type="button" class="btn-conflict-toggle" @click="showConflictModal = !showConflictModal">
            {{ showConflictModal ? t('ui.k0743') : t('ui.k0744') }}
          </button>
        </div>
        <p v-if="conflictResolvedMessage" class="conflict-resolved-msg">{{ conflictResolvedMessage }}</p>

        <div v-if="showConflictModal" class="conflict-list" data-testid="conflict-list">
          <div
            v-for="v in questionVersions"
            :key="v.id"
            class="conflict-version-item"
            :class="{ active: v.version_number === question.version_number }"
            :data-testid="`conflict-version-${v.version_number}`"
          >
            <div class="conflict-version-meta">
              <strong>{{ t('ui.k0563') }}{{ v.version_number }}</strong>
              <small>{{ v.created_at ? v.created_at.slice(0, 19).replace('T', ' ') : '' }}</small>
              <span v-if="v.version_number === question.version_number" class="badge-current">{{ t('ui.k0564') }}</span>
            </div>
            <div class="conflict-version-body">
              <p><strong>{{ t('ui.k0211') }}</strong>{{ v.stem }}</p>
              <p><strong>{{ t('ui.k0565') }}</strong>{{ v.answer }}</p>
              <p v-if="v.explanation"><strong>{{ t('ui.k0372') }}</strong>{{ v.explanation }}</p>
            </div>
            <div class="conflict-version-actions">
              <button
                type="button"
                class="btn-adopt-version primary"
                :disabled="!activeConflict && v.version_number === question.version_number"
                @click="handleAdoptQuestionVersion(v)"
              >
                {{ !activeConflict && v.version_number === question.version_number ? t('ui.k0745') : `${t('ui.k0746')}${v.version_number})` }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div :key="question.id" class="question-slide-wrapper" :class="slideTransition">
          <div class="practice-split-grid" :class="{ 'has-result': Boolean(result) }">
            <div class="practice-split-left">
              <div class="stem-box">
                <h2>{{ question.stem }}</h2>
              </div>

              <!-- 客观选择题 -->
              <div v-if="question.options?.length" class="options-group">
                <label
                  v-for="option in question.options"
                  :key="option.key"
                  class="option"
                  :class="{
                    selected: isOptionSelected(option.key),
                    'option-correct': result && isCorrectOption(option.key),
                    'option-wrong': result && isWrongOption(option.key)
                  }"
                  @click.prevent="selectOption(option.key)"
                >
                  <kbd class="key-cap" :title="`${t('ui.k0084')} ${option.key} ${t('ui.k0085')}`">{{ option.key }}</kbd>
                  <input
                    :type="question.type === 'MULTI' ? 'checkbox' : 'radio'"
                    :name="`practice-${question.id}`"
                    :value="option.key"
                    :checked="isOptionSelected(option.key)"
                    :disabled="Boolean(result)"
                  />
                  <span class="option-text-content">{{ option.content }}</span>
                  <span v-if="result && isCorrectOption(option.key)" class="inline-verdict-badge correct">{{ t('ui.k0566') }}</span>
                  <span v-if="result && isWrongOption(option.key)" class="inline-verdict-badge wrong">{{ t('ui.k0567') }}</span>
                </label>
              </div>

              <!-- 主观题 / 填空题文本输入 -->
              <div v-else class="text-answer-box">
                <label>
                  <span>{{ t('ui.k0568') }}</span>
                  <textarea
                    v-model="textAnswer"
                    :disabled="Boolean(result)"
                    rows="4"
                    :placeholder="t('ui.k0569')"
                  />
                </label>
              </div>

              <!-- 紧凑即时判分结果摘要条 (无需向下滚动即可直观看到对错与标准答案) -->
              <div v-if="result" class="quick-verdict-bar" :class="result.correctness.toLowerCase()">
                <div class="verdict-status-title">
                  <span class="verdict-icon">
                    <LinearIcon :name="result.correctness === 'CORRECT' ? 'check' : 'x'" size="15" />
                  </span>
                  <strong>{{ formatVerdictTitle(question.type, result.correctness, result.is_objective) }}</strong>
                </div>
                <div class="verdict-text-inline">
                  <span v-if="question.answer">{{ t('ui.k0080') }}<strong class="text-correct">{{ question.answer }}</strong></span>
                  <span v-if="hasAnswer">{{ t('ui.k0570') }}<strong :class="result.correctness === 'CORRECT' ? 'text-correct' : 'text-danger'">{{ formatUserAnswer(question.options?.length ? answer : textAnswer) }}</strong></span>
                  <span v-if="result.is_objective && result.score_ratio !== undefined">{{ t('ui.k0571') }}{{ Math.round((result.score_ratio || 0) * 100) }}%</span>
                </div>
              </div>
            </div>

            <div class="practice-split-right">
              <!-- 判分结果卡片 -->
              <section v-if="result" class="result-card">
                <div class="result-header">
                  <strong :class="result.correctness.toLowerCase()">
                    {{ formatVerdictTitle(question.type, result.correctness, result.is_objective) }}
                    <span v-if="result.correctness === 'CORRECT'" class="sub-correct-badge">{{ t('ui.k0572') }}</span>
                  </strong>
                  <span v-if="result.is_objective">{{ t('ui.k0573') }}{{ result.score_ratio }}</span>
                </div>

                <!-- FSRS 记忆评级交互区 (驱动下次复习时间) -->
                <div v-if="session?.mode === 'FSRS' || session?.mode === 'MISTAKE'" class="fsrs-rating-box">
                  <h4>{{ t('practice.fsrs_rating_title') }} (1-4)：</h4>
                  <div class="fsrs-buttons">
                    <button
                      type="button"
                      class="rating-btn again"
                      :class="{ selected: selectedFsrsRating === 1 }"
                      @click="submitRating(1)"
                    >
                      1 - {{ t('practice.fsrs_again') }} (+10m)
                    </button>
                    <button
                      type="button"
                      class="rating-btn hard"
                      :disabled="result.correctness === 'INCORRECT'"
                      :class="{ selected: selectedFsrsRating === 2 }"
                      @click="submitRating(2)"
                    >
                      2 - {{ t('practice.fsrs_hard') }} (+1d)
                    </button>
                    <button
                      type="button"
                      class="rating-btn good"
                      :disabled="result.correctness !== 'CORRECT'"
                      :class="{ selected: selectedFsrsRating === 3 }"
                      @click="submitRating(3)"
                    >
                      3 - {{ t('practice.fsrs_good') }} (+3d)
                    </button>
                    <button
                      type="button"
                      class="rating-btn easy"
                      :disabled="result.correctness !== 'CORRECT'"
                      :class="{ selected: selectedFsrsRating === 4 }"
                      @click="submitRating(4)"
                    >
                      4 - {{ t('practice.fsrs_easy') }} (+7d)
                    </button>
                  </div>
                  <p v-if="fsrsRatingStatus" class="fsrs-status">{{ fsrsRatingStatus }}</p>
                </div>

                <div v-if="question.explanation" class="official-explanation">
                  <h4>{{ t('ui.k0574') }}</h4>
                  <p>{{ question.explanation }}</p>
                </div>

                <!-- AI 助教入口卡片 (位于官方解析下方，阅读解析后可直接展开提问) -->
                <div class="ai-assistant-entry-block">
                  <div class="ai-entry-meta">
                    <span class="ai-badge">
                      <LinearIcon name="cpu" size="13" /> {{ t('ui.k0575') }}
                    </span>
                    <span class="ai-desc">{{ t('ui.k0576') }}</span>
                  </div>
                  <button
                    type="button"
                    class="secondary-btn btn-toggle-ai-card"
                    :class="{ active: showAiPanel }"
                    @click="toggleAiPanel"
                  >
                    <LinearIcon name="cpu" size="13" /> {{ showAiPanel ? t('ui.k0747') : t('ui.k0748') }}
                  </button>
                </div>
              </section>

              <!-- 桌面端未判分时的专注作答状态卡 -->
              <div v-else class="practice-answering-placeholder desktop-only-block">
                <div class="placeholder-icon">
                  <LinearIcon name="command" size="22" />
                </div>
                <div class="placeholder-content">
                  <h4>{{ t('ui.k0577') }}</h4>
                  <p>{{ t('ui.k0578') }}</p>
                  <p>{{ t('ui.k0579') }}<strong>{{ t('ui.k0580') }}</strong>{{ t('ui.k0581') }} <strong>Enter</strong> {{ t('ui.k0582') }}</p>
                </div>
              </div>

      <!-- AI 助教与多版本解释面板 -->
      <section v-if="showAiPanel" class="ai-panel">
        <div class="ai-toolbar">
          <h3>{{ t('ui.k0583') }}</h3>
          <div class="ai-btn-group">
            <button type="button" :disabled="aiLoading || generatingVariant" @click="generateExplanation">
              {{ aiLoading ? t('ui.k0689') : t('ui.k0749') }}
            </button>
            <button type="button" :disabled="aiLoading || generatingVariant" @click="handleVerifyWeb">
              {{ aiLoading ? t('ui.k0750') : t('ui.k0751') }}
            </button>
            <button type="button" :disabled="aiLoading || generatingVariant" @click="handleGenerateVariant">
              {{ generatingVariant ? t('ui.k0752') : t('ui.k0753') }}
            </button>
          </div>
        </div>

        <!-- 自定义追问输入框 -->
        <div class="ai-ask-box">
          <input
            v-model="customQuery"
            type="text"
            :placeholder="t('ui.k0584')"
            @keyup.enter="askCustomQuery"
          />
          <button type="button" :disabled="!customQuery.trim() || aiLoading" @click="askCustomQuery">
            {{ t('ui.k0585') }}
          </button>
        </div>

        <p v-if="aiStatusMessage" class="ai-status">{{ aiStatusMessage }}</p>

        <!-- 连续追问对话历史 (MiaowTest 对话模型) -->
        <div v-if="chatMessages.length" class="ai-chat-thread">
          <h4>{{ t('ui.k0586') }}{{ chatMessages.length }})</h4>
          <div v-for="msg in chatMessages" :key="msg.id" class="chat-bubble" :class="msg.role">
            <div class="chat-sender">
              <strong>{{ msg.role === 'user' ? t('ui.k0754') : t('ui.k0755') }}</strong>
              <small class="muted">#{{ msg.sequence }}</small>
            </div>
            <p class="chat-text">{{ msg.content }}</p>
          </div>
        </div>

        <!-- 历史解释版本列表 -->
        <div v-if="answerVersions.length" class="ai-history">
          <h4>{{ t('ui.k0587') }}{{ answerVersions.length }})</h4>
          <article
            v-for="version in answerVersions"
            :key="version.id"
            class="version-card"
            :class="{ adopted: version.is_adopted }"
          >
            <div class="version-meta">
              <span class="source-tag">{{ formatSource(version.source) }}</span>
              <span v-if="version.is_adopted" class="badge-adopted">{{ t('ui.k0588') }}</span>
              <small class="muted">{{ version.created_at ? version.created_at.slice(0, 19).replace('T', ' ') : '' }}</small>
            </div>

            <!-- 查看模式 -->
            <div v-if="editingVersionId !== version.id" class="version-content">
              <p class="content-text">{{ version.content }}</p>

              <!-- 联网证据展示 -->
              <div v-if="version.evidence?.length" class="evidence-box">
                <h5>{{ t('ui.k0589') }}{{ version.evidence.length }})</h5>
                <ul>
                  <li v-for="(ev, idx) in version.evidence" :key="idx">
                    <strong>{{ ev.title }}</strong>
                    <span v-if="ev.snippet"> - {{ ev.snippet }}</span>
                    <a v-if="ev.url" :href="ev.url" target="_blank" rel="noopener">{{ t('ui.k0590') }}</a>
                  </li>
                </ul>
              </div>

              <div class="version-actions">
                <button
                  v-if="!version.is_adopted"
                  type="button"
                  class="btn-adopt"
                  @click="adopt(version.id)"
                >{{ t('ui.k0591') }}</button>
                <button
                  type="button"
                  @click="startEdit(version)"
                >{{ t('ui.k0592') }}</button>
              </div>
            </div>

            <!-- 编辑模式 -->
            <div v-else class="version-edit-box">
              <textarea v-model="editDraft" rows="4" />
              <div class="version-edit-actions">
                <button type="button" @click="editingVersionId = null">{{ t('ui.k0149') }}</button>
                <button type="button" class="primary" :disabled="!editDraft.trim()" @click="savePersonalExplanation">
                  {{ t('ui.k0593') }}
                </button>
              </div>
            </div>
          </article>
        </div>
        <p v-else class="muted">{{ t('ui.k0594') }}</p>
      </section>
        </div>
      </div>
    </div>
</section>
<p v-else>{{ t('ui.k0595') }}</p>

<!-- 屏幕底部固定操作底栏 (屏幕Y坐标永久固定，零位移，绝不被答案挤压) -->
<footer v-if="question" class="ergonomic-action-bar" data-testid="practice-action-bar">
  <div class="action-bar-inner">
    <div class="action-left">
      <button
        type="button"
        class="secondary-btn btn-prev-question"
        :disabled="index === 0"
        @click="prev"
        :title="t('ui.k0089')"
      >
        {{ t('ui.k0596') }}
        <kbd class="hotkey-badge">←</kbd>
      </button>
    </div>

    <!-- 键盘盲操指南条 (直观呈现，无需猜测，移动端自动隐藏) -->
    <div class="hotkey-helper-bar">
      <span class="hotkey-item"><kbd>A-D</kbd> {{ t('ui.k0597') }}</span>
      <span class="hotkey-item"><kbd>Enter</kbd> {{ t('ui.k0598') }}</span>
      <span class="hotkey-item"><kbd>Space</kbd> {{ t('ui.k0092') }}</span>
      <span class="hotkey-item"><kbd>←</kbd> {{ t('ui.k0090') }}</span>
      <span class="hotkey-item"><kbd>F</kbd> {{ t('ui.k0599') }}</span>
    </div>

    <div class="action-right">
      <!-- 次要操作：未作答时提供跳过按钮 -->
      <button
        v-if="!result && index < questions.length - 1"
        type="button"
        class="secondary-btn btn-skip-unanswered"
        @click="next"
        :title="t('ui.k0091')"
      >
        <span>{{ t('ui.k0600') }}</span>
      </button>

      <!-- 核心主按钮：提交与下一题锁定在相同物理基准位置，消除跳动与误触 -->
      <button
        v-if="!result"
        type="button"
        class="primary btn-submit-answer btn-action-fixed-primary"
        :disabled="!hasAnswer && question.options?.length"
        @click="submit"
        :title="t('ui.k0601')"
      >
        <span>{{ t('ui.k0580') }}</span>
        <kbd class="hotkey-badge">Enter ↵</kbd>
      </button>

      <!-- 已作答状态：原位推进到下一题或交卷 -->
      <template v-else>
        <button
          v-if="index < questions.length - 1"
          type="button"
          class="primary btn-next-question btn-action-fixed-primary"
          @click="next"
          :title="t('ui.k0091')"
        >
          <span>{{ t('ui.k0602') }}</span>
          <kbd class="hotkey-badge">Space ␣</kbd>
        </button>
        <button
          v-else
          type="button"
          class="primary btn-finish-session btn-action-fixed-primary"
          @click="complete"
          :title="t('ui.k0601')"
        >
          <span>{{ t('ui.k0603') }}</span>
        </button>
      </template>
    </div>
  </div>
</footer>

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

function handleBack() {
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
    isEditingQuestion.value = false
    return
  }
  try {
    const currentToken = authToken.value
    const updated = await updateQuestion(currentToken, question.value.id, payload)
    triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
    isEditingQuestion.value = false
    questions.value[index.value] = updated
    questionVersions.value = await listQuestionVersions(currentToken, updated.id)
    const conf = await getQuestionConflict(currentToken, updated.id)
    activeConflict.value = conf?.has_conflict ? conf.conflict : null
  } catch {
    const queue = JSON.parse(localStorage.getItem(storageKey) || '[]')
    queue.push(queueItem)
    localStorage.setItem(storageKey, JSON.stringify(queue))
    localStorage.setItem(userScopedKey, JSON.stringify(queue))
    offlineNotice.value = t('ui.k0632')
    isEditingQuestion.value = false
  }
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
  offlineNotice.value = t('ui.k0633')

  // Process atomically item-by-item: NEVER wipe queue before confirmed completion!
  while (queue.length > 0) {
    const item = queue[0]
    const match = !item.userId || item.userId === uid || item.userId === auth.user?.value?.id || item.userId === auth.user?.value?.username || item.userId === 'user'
    if (!match) {
      break
    }
    try {
      let updated
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          updated = await updateQuestion(currentToken, item.questionId, item.payload)
          break
        } catch (err) {
          if (attempt < 2 && (err?.code === 'NETWORK_ERROR' || !err?.status)) {
            await new Promise(r => setTimeout(r, 150))
            continue
          }
          throw err
        }
      }
      triggerSyncEvent('QUESTION_UPDATED', 'QUESTION', updated.id, { version_number: updated.version_number })
      if (question.value && question.value.id === item.questionId) {
        questions.value[index.value] = updated
        questionVersions.value = await listQuestionVersions(currentToken, updated.id)
        const conf = await getQuestionConflict(currentToken, updated.id)
        activeConflict.value = conf?.has_conflict ? conf.conflict : null
      }
      // Remove item only upon confirmed success
      queue.shift()
      localStorage.setItem(storageKey, JSON.stringify(queue))
      localStorage.setItem(userScopedKey, JSON.stringify(queue))
    } catch (err) {
      console.error('Failed to sync offline question edit:', err)
      break
    }
  }
  if (queue.length) {
    offlineNotice.value = `${t('ui.k0634')} ${queue.length} ${t('ui.k0635')}`
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
.practice-page {
  width: min(100% - 2rem, 74rem);
  margin: 1.5rem auto;
  padding-bottom: 5.5rem;
}

/* 题目横向切换平滑过渡动效 */
.question-slide-wrapper.slide-next {
  animation: slideFromRight 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}
.question-slide-wrapper.slide-prev {
  animation: slideFromLeft 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideFromRight {
  from {
    opacity: 0.6;
    transform: translateX(18px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideFromLeft {
  from {
    opacity: 0.6;
    transform: translateX(-18px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.question-slide-wrapper {
  width: 100%;
}

/* 核心主操作锁定最右侧固定尺寸与坐标 */
.btn-action-fixed-primary {
  min-width: 8.5rem;
  height: 2.65rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  flex-shrink: 0;
}

/* 帮助提示弹窗 */
.help-tip-backdrop {
  position: fixed;
  inset: 0;
  background: color-mix(in srgb, var(--text-main) 44%, transparent);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 1rem;
}

.help-tip-dialog {
  background: var(--bg-card);
  color: var(--text-main);
  border-radius: 12px;
  padding: 1.5rem;
  width: min(100%, 30rem);
  box-shadow: var(--shadow-xl);
  animation: tipPopIn 0.18s ease-out;
}

@keyframes tipPopIn {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}

.help-tip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.65rem;
  margin-bottom: 1rem;
}

.help-tip-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-main);
}

.btn-close-tip {
  border: none;
  background: none;
  font-size: 1.25rem;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
}

.tip-section {
  margin-bottom: 0.85rem;
}

.tip-section strong {
  display: block;
  font-size: 0.875rem;
  color: var(--text-main);
  margin-bottom: 0.35rem;
}

.tip-section ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.825rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.tip-section p {
  margin: 0;
  font-size: 0.825rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.btn-help-guide {
  font-size: 0.85rem;
  padding: 0.35rem 0.65rem;
}

.btn-help-mobile {
  border: 1px solid var(--border-strong);
  background: var(--bg-card);
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.95rem;
  cursor: pointer;
  margin-right: 0.4rem;
}

/* 官方解析下方的 AI 助教入口 */
.ai-assistant-entry-block {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: var(--success-light);
  border: 1px solid var(--success-border);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.ai-entry-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.ai-badge {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--success);
}

.ai-desc {
  font-size: 0.785rem;
  color: var(--success-hover);
}

.btn-toggle-ai-card {
  padding: 0.4rem 0.85rem;
  font-size: 0.825rem;
  font-weight: 500;
  background: var(--bg-card);
  border: 1px solid var(--success-border);
  color: var(--success);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-toggle-ai-card:hover {
  background: var(--success-light);
}

.btn-toggle-ai-card.active {
  background: var(--success);
  color: var(--on-primary);
}

/* 专注作答状态占位卡 */
.practice-answering-placeholder {
  padding: 2.25rem 1.25rem;
  background: var(--bg-page);
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  color: var(--text-muted);
}

.placeholder-icon {
  font-size: 1.8rem;
  line-height: 1;
}

.placeholder-content h4 {
  margin: 0 0 0.35rem 0;
  font-size: 0.95rem;
  color: var(--text-main);
}

.placeholder-content p {
  margin: 0.2rem 0;
  font-size: 0.825rem;
  line-height: 1.45;
}

.compact-header {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
  padding: 0.45rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  min-height: 48px;
}

.compact-header > .header-left-bar,
.compact-header .header-left-bar {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 0.65rem !important;
  flex: 0 1 auto !important;
  min-width: 0;
}

.header-titles {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  white-space: nowrap;
}

.practice-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
}

.header-meta-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.badge-type-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  background: var(--linear-bg-subtle);
  border: 1px solid var(--border-strong);
  color: var(--linear-cyan);
  font-family: var(--linear-mono);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.badge-index-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  background: var(--linear-bg-subtle);
  border: 1px solid var(--border-strong);
  color: var(--text-muted);
  font-family: var(--linear-mono);
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-conflict-warning {
  padding: 0.2rem 0.5rem;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  color: var(--danger);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  cursor: pointer;
  font-weight: 600;
}

.compact-header > .header-actions,
.compact-header .header-actions,
.header-actions {
  display: flex !important;
  flex-direction: row !important;
  gap: 0.45rem !important;
  align-items: center !important;
  flex-wrap: nowrap !important;
  flex: 0 0 auto !important;
}

.header-actions .btn-header-complete {
  background: var(--primary);
  color: var(--on-primary);
  border-color: var(--primary);
  font-weight: 600;
  padding: 0 1rem;
}
.header-actions .btn-header-complete:hover:not(:disabled) {
  background: var(--primary-hover);
}

.btn-flag.active {
  background: var(--warning-light);
  border-color: var(--warning);
  color: var(--warning-hover);
  font-weight: 600;
}

.btn-kill {
  color: var(--danger);
  border-color: var(--danger-border);
}
.btn-kill:hover:not(:disabled) {
  background: var(--danger-light);
  border-color: var(--danger);
}

.question-card {
  padding: 1.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.stem-box {
  max-width: 100%;
  min-width: 0;
  word-break: break-all;
  overflow-wrap: anywhere;
}

.stem-box h2 {
  font-size: 1.0625rem;
  line-height: 1.65;
  margin-bottom: 1.25rem;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-wrap: anywhere;
  color: var(--text-main);
  font-weight: 500;
  max-width: 100%;
}

.options-group {
  display: grid;
  gap: 0.65rem;
  margin-bottom: 1.25rem;
  max-width: 100%;
  min-width: 0;
}

.option {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  cursor: pointer;
  transition: all 0.1s cubic-bezier(0.16, 1, 0.3, 1);
  font-size: 0.9375rem;
  line-height: 1.5;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.option .option-text-content {
  color: var(--text-main);
  flex: 1;
  min-width: 0;
  word-break: break-word;
  overflow-wrap: anywhere;
}

/* 统一底部操作栏 (Desktop Base) */
.ergonomic-action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 80;
  background: color-mix(in srgb, var(--bg-card) 95%, transparent);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.04);
  padding: 0.75rem 1.5rem;
}

.action-bar-inner {
  max-width: 74rem;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.action-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.action-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.hotkey-helper-bar {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  font-size: 0.8rem;
  color: var(--text-tertiary);
}

.hotkey-item {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.option:hover {
  border-color: var(--border-strong);
  background: var(--bg-muted);
}

.option.selected {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--text-main);
  box-shadow: 0 0 0 1px var(--primary);
}

.option.selected .key-cap {
  background: var(--primary);
  color: var(--on-primary);
  border-color: var(--primary);
}

.option input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.text-answer-box textarea {
  width: 100%;
  padding: 0.85rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  resize: vertical;
  margin-top: 0.5rem;
  font-size: 0.95rem;
  line-height: 1.5;
}

.practice-split-grid {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

@media (min-width: 1024px) {
  .practice-split-grid {
    display: grid;
    grid-template-columns: 1fr;
    max-width: 52rem;
    margin: 0 auto;
    width: 100%;
    gap: 1.5rem;
    align-items: start;
    transition: max-width 0.2s ease;
  }

  .practice-split-grid.has-result {
    grid-template-columns: 1.15fr 0.85fr;
    max-width: none;
    margin: 0;
  }

  .practice-split-grid:not(.has-result) .practice-split-right {
    display: none;
  }

  .practice-split-right {
    position: sticky;
    top: 1rem;
    max-height: calc(100vh - 7.5rem);
    overflow-y: auto;
    padding-right: 0.25rem;
  }
}

.practice-split-left {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.practice-split-right {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.practice-side-guide {
  padding: 1.25rem;
  background: var(--bg-page);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
}

.practice-side-guide h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  color: var(--text-main);
}

.practice-side-guide p {
  margin: 0.35rem 0;
  font-size: 0.875rem;
  line-height: 1.5;
}

.quick-verdict-bar {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-lg);
  border: 1.5px solid;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  animation: fadeIn 0.2s ease-in-out;
}

.quick-verdict-bar.correct {
  background: var(--success-light);
  border-color: var(--success-border);
  color: var(--success);
}

.quick-verdict-bar.incorrect {
  background: var(--danger-light);
  border-color: var(--danger-border);
  color: var(--danger);
}

.quick-verdict-bar.partial {
  background: var(--warning-light);
  border-color: var(--warning-border);
  color: var(--warning);
}

.verdict-status-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.95rem;
}

.verdict-text-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.875rem;
}

.text-correct {
  color: var(--success);
}

.text-danger {
  color: var(--danger);
}

.option.option-correct {
  border-color: var(--success);
  background: var(--success-light);
  color: var(--text-main);
}

.option.option-wrong {
  border-color: var(--danger);
  background: var(--danger-light);
  color: var(--text-main);
}

:global(:root[data-theme="dark"]) .option.option-correct {
  background: color-mix(in srgb, var(--success) 18%, var(--bg-card));
}

:global(:root[data-theme="dark"]) .option.option-wrong {
  background: color-mix(in srgb, var(--danger) 18%, var(--bg-card));
}

.inline-verdict-badge {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
  font-family: var(--linear-mono);
}

.inline-verdict-badge.correct {
  background: var(--success-light);
  color: var(--success);
  border: 1px solid var(--success-border);
}

.inline-verdict-badge.wrong {
  background: var(--danger-light);
  color: var(--danger);
  border: 1px solid var(--danger-border);
}


.submit-bar {
  margin: 1.5rem 0 0.5rem;
}

.result-card {
  margin-top: 1.5rem;
  padding: 1.35rem;
  border-radius: var(--radius-lg);
  background: var(--bg-page);
  border: 1px solid var(--border);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.result-header strong.correct {
  color: var(--success);
}
.result-header strong.partial {
  color: var(--warning);
}
.result-header strong.incorrect {
  color: var(--danger);
}

.official-explanation {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  border-left: 4px solid var(--primary);
  line-height: 1.6;
}

.official-explanation h4 {
  font-size: 0.95rem;
  margin-bottom: 0.35rem;
  color: var(--text-main);
}

.btn-ai-toggle.active {
  background: var(--primary-light);
  color: var(--primary);
  border-color: var(--primary-border);
}

.option:active {
  transform: scale(0.99);
}

.fsrs-rating-box {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}

.fsrs-rating-box h4 {
  margin: 0 0 0.65rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.fsrs-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.rating-btn {
  padding: 0.45rem 0.85rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  background: var(--bg-card);
  transition: all 0.15s ease;
}

.rating-btn.again {
  color: var(--danger);
  border-color: var(--danger-border);
}
.rating-btn.again:hover:not(:disabled) {
  background: var(--danger-light);
}

.rating-btn.hard {
  color: var(--warning);
  border-color: var(--warning-border);
}
.rating-btn.hard:hover:not(:disabled) {
  background: var(--warning-light);
}

.rating-btn.good {
  color: var(--primary);
  border-color: var(--primary-border);
}
.rating-btn.good:hover:not(:disabled) {
  background: var(--primary-light);
}

.rating-btn.easy {
  color: var(--success);
  border-color: var(--success-border);
}
.rating-btn.easy:hover:not(:disabled) {
  background: var(--success-light);
}

.rating-btn.selected {
  font-weight: 700;
  box-shadow: 0 0 0 2px currentColor;
}

.rating-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fsrs-status {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: var(--primary);
}

.ai-panel {
  margin-top: 1.5rem;
  padding: 1.35rem;
  border: 1px solid var(--primary-border);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
}

.ai-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.ai-btn-group {
  display: flex;
  gap: 0.5rem;
}

.ai-ask-box {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.ai-ask-box input {
  flex: 1;
}

.ai-status {
  color: var(--warning);
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.ai-history {
  display: grid;
  gap: 0.85rem;
  margin-top: 1rem;
}

.version-card {
  padding: 1rem 1.15rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.version-card.adopted {
  border-color: var(--success);
  box-shadow: 0 0 0 1px var(--success);
}

.version-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.source-tag {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  background: var(--bg-muted);
  border-radius: var(--radius-sm);
  color: var(--text-main);
}

.badge-adopted {
  font-size: 0.75rem;
  color: var(--success);
  font-weight: 700;
  background: var(--success-light);
  border: 1px solid var(--success-border);
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-sm);
}

.content-text {
  white-space: pre-wrap;
  line-height: 1.6;
  margin-bottom: 0.5rem;
  font-size: 0.925rem;
}

.evidence-box {
  margin: 0.5rem 0;
  padding: 0.65rem 0.85rem;
  background: var(--bg-page);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  border: 1px solid var(--border);
}

.evidence-box ul {
  margin-left: 1.25rem;
  margin-top: 0.35rem;
}

.version-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.btn-adopt {
  color: var(--success);
  border-color: var(--success-border);
}
.btn-adopt:hover:not(:disabled) {
  background: var(--success-light);
  border-color: var(--success);
}

.version-edit-box textarea {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.version-edit-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 0.5rem;
}

.ai-chat-thread {
  margin: 1rem 0;
  display: grid;
  gap: 0.75rem;
}

.ai-chat-thread h4 {
  margin: 0;
  font-size: 0.95rem;
}

.chat-bubble {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--bg-card);
}

.chat-bubble.user {
  background: var(--primary-light);
  border-color: var(--primary-border);
  margin-left: 1.5rem;
}

.chat-bubble.assistant {
  background: var(--bg-card);
  border-color: var(--border);
  margin-right: 1.5rem;
}

.chat-sender {
  display: flex;
  justify-content: space-between;
  font-size: 0.8125rem;
  margin-bottom: 0.35rem;
  font-weight: 600;
  color: var(--text-muted);
}

.chat-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.55;
  font-size: 0.925rem;
}

.conflict-banner {
  margin-bottom: 1.25rem;
  padding: 1.15rem;
  border: 1px solid var(--warning);
  background: var(--warning-light);
  border-radius: var(--radius-lg);
}

.conflict-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.conflict-badge {
  font-weight: 600;
  color: var(--warning-hover);
  font-size: 0.925rem;
}

.btn-conflict-toggle {
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--warning);
  background: var(--warning-light);
  color: var(--warning);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
}

.conflict-resolved-msg {
  margin-top: 0.5rem;
  color: var(--success);
  font-weight: 600;
  font-size: 0.9rem;
}

.conflict-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.conflict-version-item {
  padding: 0.85rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.conflict-version-item.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary);
}

.conflict-version-meta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.5rem;
}

.badge-current {
  font-size: 0.75rem;
  background: var(--primary-light);
  color: var(--primary);
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
}

.conflict-version-body p {
  margin: 0.25rem 0;
  font-size: 0.875rem;
}

.conflict-version-actions {
  margin-top: 0.5rem;
  display: flex;
  justify-content: flex-end;
}

.btn-adopt-version {
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
}

.offline-banner {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  color: var(--danger);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
}

.btn-sync-offline {
  padding: 0.3rem 0.65rem;
  border: 1px solid var(--danger);
  background: var(--bg-card);
  color: var(--danger);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
}

.question-edit-panel {
  margin-bottom: 1.25rem;
  padding: 1.25rem;
  background: var(--bg-page);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  display: grid;
  gap: 0.75rem;
}

.question-edit-panel h3 {
  margin: 0;
  font-size: 1.05rem;
}

.question-edit-panel label {
  display: grid;
  gap: 0.35rem;
  font-weight: 600;
  font-size: 0.9rem;
}

.input-edit-stem, .input-edit-exp {
  padding: 0.5rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.95rem;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.btn-edit-question {
  border: 1px solid var(--border-strong);
  background: var(--bg-card);
  cursor: pointer;
}

/* Visibility utilities */
.mobile-only-inline, .mobile-only-btn {
  display: none !important;
}
.desktop-only-btn {
  display: inline-flex !important;
}

.btn-sheet-trigger-pill {
  border: 1px solid var(--primary-border);
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-sheet-trigger-pill:hover {
  background: var(--primary-light);
}

.mobile-more-wrapper {
  position: relative;
}

.btn-more-menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-main);
  font-size: 1.15rem;
  font-weight: 800;
  cursor: pointer;
}

.mobile-dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.35rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  min-width: 8.5rem;
  z-index: 100;
  overflow: hidden;
}

.dropdown-item {
  padding: 0.6rem 0.85rem;
  text-align: left;
  background: none;
  border: none;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 0.85rem;
  color: var(--text-main);
  cursor: pointer;
}
.dropdown-item:last-child {
  border-bottom: none;
}
.dropdown-item:active {
  background: var(--bg-muted);
}

/* Question Sheet Drawer (答题卡) & Modals */
.sheet-modal-backdrop {
  position: fixed;
  inset: 0;
  background: color-mix(in srgb, var(--text-main) 44%, transparent);
  backdrop-filter: blur(2px);
  z-index: 100;
  display: flex;
  justify-content: center;
  align-items: flex-end;
}

.sheet-modal-drawer {
  background: var(--bg-card);
  width: 100%;
  max-width: 42rem;
  max-height: 80vh;
  border-radius: 1rem 1rem 0 0;
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  padding: 1.15rem 1.25rem;
  overflow-y: auto;
  animation: slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@media (min-width: 768px) {
  .sheet-modal-backdrop {
    align-items: center;
    padding: 1.5rem;
  }

  .sheet-modal-drawer {
    margin: auto;
    border-radius: var(--radius-xl);
    max-height: 75vh;
    animation: modalScaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
}

/* 练习结算结果卡片模态框 */
.practice-result-card-modal {
  background: var(--bg-card);
  width: 100%;
  max-width: 28rem;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: 2rem 1.75rem 1.5rem;
  text-align: center;
  margin: auto;
  border: 1px solid var(--border);
  animation: modalScaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.result-card-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: var(--success-light);
  color: var(--success);
  border: 1px solid var(--success-border);
  border-radius: 9999px;
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.practice-result-card-modal h2 {
  font-size: 1.35rem;
  font-weight: 700;
  margin: 0 0 1.25rem 0;
  color: var(--text-main);
}

.result-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.result-stat-box {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.result-stat-box small {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.result-stat-box strong {
  font-size: 1.35rem;
  font-weight: 700;
}

.result-counts-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.6rem;
  margin-bottom: 1.5rem;
  padding: 0.5rem;
  background: var(--bg-muted);
  border-radius: var(--radius-md);
}

.count-tag {
  font-size: 0.82rem;
  font-weight: 600;
}

.result-card-actions {
  display: flex;
  gap: 0.75rem;
}

.result-card-actions button {
  flex: 1;
  padding: 0.7rem 1rem;
  font-size: 0.95rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  cursor: pointer;
}

/* 确认提前交卷对话框 */
.confirm-submit-dialog {
  background: var(--bg-card);
  width: 100%;
  max-width: 26rem;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: 1.75rem;
  margin: auto;
  border: 1px solid var(--border);
  animation: modalScaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.confirm-submit-dialog h3 {
  margin: 0 0 0.75rem 0;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-main);
}

.confirm-warning-desc,
.confirm-info-desc {
  font-size: 0.92rem;
  line-height: 1.5;
  color: var(--text-muted);
  margin-bottom: 1.5rem;
}

.confirm-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.confirm-dialog-actions button {
  padding: 0.6rem 1.15rem;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  cursor: pointer;
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

@keyframes modalScaleIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.sheet-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.85rem;
}

.sheet-drawer-title {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}
.sheet-drawer-title h3 {
  margin: 0;
  font-size: 1.15rem;
}
.sheet-stats-pill {
  font-size: 0.8rem;
  color: var(--text-muted);
  background: var(--bg-muted);
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.btn-close-sheet {
  border: none;
  background: var(--bg-muted);
  width: 42px;
  height: 42px;
  min-width: 42px;
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  cursor: pointer;
  font-weight: 700;
  color: var(--text-muted);
  transition: background-color 0.15s ease;
}

.btn-close-sheet:hover {
  background: var(--border);
}

.sheet-quick-actions {
  margin-bottom: 0.75rem;
}
.btn-jump-next-unanswered {
  width: 100%;
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55rem;
  background: var(--primary-light);
  border: 1px dashed var(--primary);
  color: var(--primary);
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
}

.sheet-legend-bar {
  display: flex;
  gap: 0.85rem;
  margin-bottom: 0.85rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  flex-wrap: wrap;
}
.sheet-legend-bar .legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.legend-dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  display: inline-block;
}
.legend-dot.unanswered { background: var(--border-strong); }
.legend-dot.correct { background: var(--success); }
.legend-dot.incorrect { background: var(--danger); }
.legend-dot.partial { background: var(--warning); }

.sheet-numbers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(2.6rem, 1fr));
  gap: 0.5rem;
  margin-top: 0.35rem;
}

.sheet-num-btn {
  height: 2.6rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--text-main);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.sheet-num-btn.current {
  border: 2px solid var(--primary) !important;
  box-shadow: 0 0 0 2px var(--primary-border);
}
.sheet-num-btn.answered {
  background: var(--bg-muted);
  border-color: var(--text-tertiary);
}
.sheet-num-btn.correct {
  background: var(--success);
  border-color: var(--success-hover);
  color: var(--on-primary);
}
.sheet-num-btn.incorrect {
  background: var(--danger);
  border-color: var(--danger-hover);
  color: var(--on-primary);
}
.sheet-num-btn.partial {
  background: var(--warning);
  border-color: var(--warning-hover);
  color: var(--on-primary);
}

/* ==========================================================================
   Mobile Responsive Overhaul (< 768px)
   ========================================================================== */
@media (max-width: 767px) {
  .practice-page {
    width: 100%;
    margin: 0;
    padding: 0.25rem 0.5rem 4.5rem;
  }

  .compact-header {
    display: flex !important;
    flex-direction: row !important;
    justify-content: space-between !important;
    align-items: center !important;
    padding: 0.35rem 0.5rem !important;
    margin-bottom: 0.75rem !important;
    gap: 0.35rem !important;
    height: auto !important;
    min-height: 44px !important;
    border-radius: var(--radius-md) !important;
    box-sizing: border-box !important;
    flex-wrap: nowrap !important;
    justify-content: space-between !important;
    align-items: center !important;
  }

  .header-left-bar {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.35rem !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
  }

  .header-titles {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.3rem !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }

  .btn-back {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 42px !important;
    height: 42px !important;
    padding: 0 0.65rem !important;
    font-size: 0.85rem !important;
    white-space: nowrap !important;
    border-radius: var(--radius-md) !important;
    flex-shrink: 0 !important;
  }

  .practice-title {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    margin: 0 !important;
  }

  .badge-type-pill {
    font-size: 0.72rem !important;
    padding: 0.15rem 0.35rem !important;
  }

  .btn-sheet-trigger-pill {
    font-size: 0.75rem !important;
    padding: 0.2rem 0.5rem !important;
    min-height: 42px !important;
    display: inline-flex !important;
    align-items: center !important;
    border-radius: var(--radius-md) !important;
  }

  .header-actions {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0.35rem !important;
    flex: 0 0 auto !important;
    width: auto !important;
    flex-wrap: nowrap !important;
  }

  .btn-header-complete {
    padding: 0.25rem 0.6rem !important;
    font-size: 0.8rem !important;
    height: 2rem !important;
    min-height: 2rem !important;
    border-radius: var(--radius-sm) !important;
  }

  .desktop-only-btn,
  .desktop-only-block,
  .practice-answering-placeholder {
    display: none !important;
  }

  /* 消除移动端重复的判分结果头部（已有 quick-verdict-bar 呈现完整判分） */
  .result-card .result-header {
    display: none !important;
  }

  /* 移动端无障碍隐藏原生 radio/checkbox，保持屏幕阅读器与辅助技术可达 */
  .option input {
    position: absolute !important;
    opacity: 0 !important;
    pointer-events: none !important;
    width: 1px !important;
    height: 1px !important;
    margin: -1px !important;
    clip: rect(0, 0, 0, 0) !important;
    overflow: hidden !important;
  }

  .btn-help-mobile,
  .btn-more-menu {
    min-width: 42px !important;
    min-height: 42px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
  }

  .mobile-only-inline {
    display: inline-flex !important;
  }
  .mobile-only-btn {
    display: inline-flex !important;
  }

  /* 消除桌面端键盘提示框在手机端的空间占用 */
  .practice-side-guide,
  .practice-tips {
    display: none !important;
  }

  .question-card {
    padding: 0.75rem 0.75rem 0.85rem;
    border-radius: var(--radius-md);
  }

  .stem-box h2 {
    font-size: 1rem;
    line-height: 1.45;
    margin-bottom: 0.75rem;
  }

  .options-group {
    gap: 0.5rem;
  }

  .option {
    padding: 0.6rem 0.75rem;
    border-radius: var(--radius-md);
    margin-bottom: 0;
  }

  .key-cap {
    min-width: 1.5rem;
    height: 1.5rem;
    font-size: 0.8rem;
  }

  .quick-verdict-bar {
    padding: 0.5rem 0.75rem;
    margin-top: 0.65rem;
    border-radius: var(--radius-md);
  }

  .result-actions {
    flex-direction: column;
  }
  .ai-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .ai-btn-group {
    flex-direction: column;
  }

  /* 底部固定底栏极简化与安全区适配 */
  .ergonomic-action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 80;
    padding: 0.5rem 0.75rem max(0.5rem, env(safe-area-inset-bottom, 12px)) !important;
    background: color-mix(in srgb, var(--bg-card) 96%, transparent) !important;
    backdrop-filter: blur(12px) !important;
    border-top: 1px solid var(--border) !important;
    min-height: 52px;
  }

  .action-bar-inner {
    width: 100%;
    gap: 0.5rem;
  }

  .btn-prev-question,
  .btn-next-question,
  .btn-submit-answer,
  .btn-skip-unanswered,
  .btn-finish-session,
  .btn-ai-toggle {
    min-height: 42px !important;
    padding: 0.45rem 0.85rem !important;
    font-size: 0.875rem !important;
  }

  .hotkey-badge,
  .hotkey-helper-bar {
    display: none !important;
  }
}
</style>
