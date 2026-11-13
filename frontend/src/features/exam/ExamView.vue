<template>
  <main class="exam-mode exam-shell" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
    <header class="exam-topbar exam-bar" :class="{ 'is-report': Boolean(report) || reportLoadFailed }">
      <div class="exam-top-left">
        <button type="button" class="exam-back" @click="handleBack">
          <LinearIcon name="arrow-left" :size="15" />
          <span>{{ t('ep.exam.runner_exit') }}</span>
        </button>
        <span class="exam-sep" aria-hidden="true"></span>
        <div class="exam-identity">
          <span class="exam-kicker">{{ report || reportLoadFailed ? t('ep.exam.report') : t('ep.exam.runner_title') }}</span>
          <span v-if="!report && question" class="exam-sub">{{ formatQuestionTypeName(question.type) }} · {{ currentIndex + 1 }} / {{ questions.length }}</span>
        </div>
      </div>

      <div class="exam-bar-center">
        <div v-if="!report && !reportLoadFailed" class="exam-timer" :class="{ low: session?.time_limit && remainingSeconds <= 300 }" data-testid="exam-timer" role="timer" aria-live="off">
          <span class="timer-cap">{{ session?.time_limit ? t('ep.exam.remaining') : t('ep.exam.elapsed') }}</span>
          <strong class="mono">{{ formatRemainingTime(session?.time_limit ? remainingSeconds : elapsedSeconds) }}</strong>
        </div>
      </div>

      <div class="exam-top-right">
        <div v-if="!report && !reportLoadFailed" class="exam-utils">
          <ThemeToggle compact />
          <LocaleToggle compact />
        </div>
        <button v-if="!report && !reportLoadFailed" type="button" class="btn btn-sm btn-primary exam-submit" :disabled="loading || isSubmitting || Boolean(report) || syncExpired" @click="showSubmitConfirm = true">
          {{ t('ep.exam.submit') }}
        </button>
      </div>
    </header>

    <p v-if="error" class="notice bad exam-error" role="alert">{{ error }}</p>
    <div v-if="!report && syncExpired" class="notice bad exam-expired" role="alert" data-testid="exam-expired-banner">
      <div class="exam-expired-body">
        <strong>{{ expiredCopy.notice }}</strong>
        <p v-if="unsubmittedQuestionNumbers.length" data-testid="exam-expired-unsubmitted">
          {{ expiredCopy.unsubmitted }}
          <span v-for="number in unsubmittedQuestionNumbers" :key="number" class="exam-expired-number">{{ t('ep.practice.question_no', { current: number }) }}</span>
        </p>
        <p v-else>{{ expiredCopy.none }}</p>
        <p class="exam-expired-kept">{{ expiredCopy.kept }}</p>
      </div>
      <div class="exam-expired-actions">
        <button type="button" class="btn btn-sm btn-primary" data-testid="exam-expired-submit-server" :disabled="isSubmitting" @click="showExpiredSubmitConfirm = true">
          {{ expiredCopy.submit_server }}
        </button>
      </div>
    </div>
    <div v-if="!report && connectionNotice" class="notice warn exam-offline" role="status" data-testid="exam-offline-banner" :data-pending="String(pendingSubmit)">
      <span>{{ connectionNotice }}</span>
      <button type="button" class="btn btn-sm btn-quiet" data-testid="exam-offline-retry" @click="retrySync">{{ t('ep.practice.offline_retry') }}</button>
    </div>
    <div v-if="!report && draftConflicts.length" class="notice warn exam-conflict" role="status" data-testid="exam-draft-conflicts">
      <div class="exam-conflict-body">
        <strong>{{ t('ep.exam.draft_conflict', { count: draftConflicts.length }) }}</strong>
        <ul class="exam-conflict-list">
          <li v-for="conflict in draftConflicts" :key="conflict.question_id">
            {{ t('ep.practice.question_no', { current: conflict.question_number }) }} ·
            {{ t('ep.exam.your_answer') }} {{ displayAnswer(conflict.incoming_answer) }} ·
            {{ t('ep.exam.saved_answer') }} {{ displayAnswer(conflict.existing_answer) }}
          </li>
        </ul>
      </div>
      <div class="exam-conflict-actions">
        <button type="button" class="btn btn-sm" @click="restoreMyAnswers">{{ t('ep.exam.draft_conflict_restore') }}</button>
        <button type="button" class="btn btn-sm btn-quiet" @click="dismissDraftConflicts">{{ t('ep.exam.draft_conflict_dismiss') }}</button>
      </div>
    </div>
    <div v-if="loading" class="exam-loading skeleton-rows">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </div>

    <div v-else-if="reportLoadFailed" class="exam-loading" data-testid="exam-report-load-failed" role="alert">
      <div class="empty-title">{{ t('ep.common.load_failed') }}</div>
      <div class="empty-desc">{{ t('ep.exam.report_unavailable') }}</div>
      <button type="button" class="btn" data-testid="exam-report-retry" @click="retryLoadReport">{{ t('ep.common.retry') }}</button>
    </div>

    <section v-else-if="report" class="exam-report" aria-labelledby="exam-report-title">
      <header class="report-head">
        <div>
          <div class="rule-label">{{ t('ep.exam.report') }}</div>
          <h1 id="exam-report-title" class="report-score">{{ report.score }}</h1>
          <p class="report-score-cap">{{ t('ep.exam.score') }}</p>
        </div>
        <dl class="report-facts">
          <div><dt>{{ t('ep.exam.accuracy') }}</dt><dd class="mono">{{ report.accuracy }}%</dd></div>
          <div><dt>{{ t('ep.exam.answered') }}</dt><dd class="mono">{{ report.answered_count }} / {{ report.total_questions }}</dd></div>
          <div><dt>{{ t('ep.exam.time_used') }}</dt><dd class="mono">{{ formatRemainingTime(report.time_spent ?? elapsedSeconds) }}</dd></div>
        </dl>
      </header>

      <div class="report-counts">
        <span class="tag ok">{{ t('ep.exam.correct') }} {{ report.correct_count }}</span>
        <span v-if="report.partial_count" class="tag warn">{{ t('ep.exam.partial') }} {{ report.partial_count }}</span>
        <span class="tag bad">{{ t('ep.exam.wrong') }} {{ report.incorrect_count }}</span>
        <span class="tag">{{ t('ep.exam.blank') }} {{ report.unanswered_count }}</span>
      </div>

      <section v-if="report.type_stats && Object.keys(report.type_stats).length" class="report-section">
        <h2 class="section-title">{{ t('ep.exam.by_type') }}</h2>
        <div class="etable-wrap">
          <table class="etable">
            <thead>
              <tr>
                <th>{{ t('ep.exam.section_type') }}</th>
                <th>{{ t('ep.exam.answered') }}</th>
                <th>{{ t('ep.exam.correct') }}</th>
                <th>{{ t('ep.exam.partial') }}</th>
                <th>{{ t('ep.exam.wrong') }}</th>
                <th>{{ t('ep.exam.accuracy') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(val, type) in report.type_stats" :key="type">
                <td>{{ formatQuestionTypeName(type) }}</td>
                <td class="mono">{{ val.attempted }}</td>
                <td class="mono">{{ val.correct }}</td>
                <td class="mono">{{ val.partial }}</td>
                <td class="mono">{{ val.incorrect }}</td>
                <td class="mono">{{ calculateAccuracy(val.correct, val.attempted) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="report.tag_stats && Object.keys(report.tag_stats).length" class="report-section">
        <h2 class="section-title">{{ t('ep.exam.by_tag') }}</h2>
        <div class="etable-wrap">
          <table class="etable">
            <thead>
              <tr>
                <th>{{ t('ep.exam.by_tag') }}</th>
                <th>{{ t('ep.exam.answered') }}</th>
                <th>{{ t('ep.exam.correct') }}</th>
                <th>{{ t('ep.exam.wrong') }}</th>
                <th>{{ t('ep.exam.accuracy') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(val, tag) in report.tag_stats" :key="tag">
                <td>{{ tag }}</td>
                <td class="mono">{{ val.attempted }}</td>
                <td class="mono">{{ val.correct }}</td>
                <td class="mono">{{ val.incorrect }}</td>
                <td class="mono">{{ calculateAccuracy(val.correct, val.attempted) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="reviewQuestions.length" class="report-section exam-review">
        <h2 class="section-title">{{ t('ep.exam.wrong_detail') }}</h2>
        <article v-for="item in reviewQuestions" :key="item.id" class="review-item">
          <h3 class="review-stem">
            <span v-if="isBlankReportItem(item.id)" class="tag">{{ t('ep.exam.blank') }}</span>
            {{ item.stem }}
          </h3>
          <div class="review-answers">
            <p><span>{{ t('ep.exam.your_answer') }}</span><strong>{{ displayAnswer(report.answers[item.id]?.user_answer) }}</strong></p>
            <p><span>{{ t('ep.exam.right_answer') }}</span><strong>{{ displayAnswer(report.answers[item.id]?.correct_answer) }}</strong></p>
          </div>
          <p v-if="report.answers[item.id]?.explanation" class="review-explain">{{ report.answers[item.id].explanation }}</p>
          <p v-else class="review-explain is-empty">{{ t('ep.exam.no_analysis') }}</p>
        </article>
      </section>

      <div class="report-actions">
        <button type="button" class="btn btn-primary" @click="handleBack">{{ t('ep.exam.back_center') }}</button>
      </div>
    </section>

    <template v-else-if="question">
      <div class="exam-layout">
        <section class="exam-paper">
          <div class="exam-q-meta">
            <span>{{ t('ep.practice.question_no', { current: currentIndex + 1 }) }}</span>
            <span>{{ formatQuestionTypeName(question.type) }}</span>
            <span v-if="isFlagged" class="tag warn">{{ t('ep.exam.flagged') }}</span>
          </div>
          <h2 class="exam-stem">{{ question.stem }}</h2>

          <div v-if="question.options?.length" class="exam-options">
            <label
              v-for="option in question.options"
              :key="option.key"
              class="exam-option"
              :class="{ selected: isOptionSelected(option.key) }"
            >
              <kbd class="key-cap" :title="`${t('ep.practice.edit_option_key')} ${option.key}`">{{ option.key }}</kbd>
              <input
                :type="question.type === 'MULTI' ? 'checkbox' : 'radio'"
                :name="`question-${question.id}`"
                :checked="isOptionSelected(option.key)"
                :disabled="answersLocked"
                @change="selectOption(option.key, $event.target.checked)"
              />
              <span class="option-content-text">{{ option.content }}</span>
              <span class="option-indicator" aria-hidden="true"></span>
            </label>
          </div>
          <label v-else class="field exam-text-answer">
            <span class="label">{{ ['ESSAY', 'SUBJECTIVE'].includes(question.type) ? t('ep.exam.your_answer') : t('ep.practice.your_answer') }}</span>
            <textarea
              :value="currentTextAnswer"
              :rows="['ESSAY', 'SUBJECTIVE'].includes(question.type) ? 8 : 2"
              :placeholder="['ESSAY', 'SUBJECTIVE'].includes(question.type) ? t('ep.practice.essay_placeholder') : t('ep.practice.essay_placeholder')"
              :disabled="answersLocked"
              @input="setTextAnswer($event.target.value)"
            />
          </label>
        </section>

        <aside class="exam-sheet" data-testid="exam-answer-sheet" :aria-label="t('ep.exam.sheet')">
          <div class="sheet-head">
            <span class="sheet-title">{{ t('ep.exam.sheet') }}</span>
            <span class="sheet-count mono">{{ answeredCount }} / {{ questions.length }}</span>
          </div>
          <div class="sheet-progress"><i :style="{ width: Math.min(100, (answeredCount / Math.max(1, questions.length)) * 100) + '%' }"></i></div>
          <dl class="sheet-facts">
            <div><dt>{{ t('ep.exam.answered') }}</dt><dd class="mono">{{ answeredCount }}</dd></div>
            <div><dt>{{ t('ep.exam.blank') }}</dt><dd class="mono">{{ Math.max(0, questions.length - answeredCount) }}</dd></div>
            <div><dt>{{ t('ep.exam.flagged') }}</dt><dd class="mono">{{ flaggedCount }}</dd></div>
          </dl>
          <div class="answer-grid">
            <button
              v-for="(item, index) in questions"
              :key="item.id"
              type="button"
              class="answer-cell mono"
              :class="answerButtonClass(item.id, index)"
              :aria-label="`${t('ep.practice.question_no', { current: index + 1 })} ${answerState(item.id).answered ? t('ep.exam.answered') : t('ep.exam.blank')}${answerState(item.id).flagged ? ' ' + t('ep.exam.flagged') : ''}`"
              @click="goTo(index)"
            >{{ index + 1 }}</button>
          </div>
          <p class="sheet-note">{{ t('ep.exam.sheet_note') }}</p>
        </aside>
      </div>

      <footer class="exam-actionbar">
        <div class="exam-action-inner">
          <button type="button" class="btn btn-sm exam-sheet-trigger" @click="showMobileSheet = true">
            <LinearIcon name="layers" :size="14" />{{ t('ep.exam.sheet') }}
            <span class="mono">{{ answeredCount }} / {{ questions.length }}</span>
          </button>
          <button type="button" class="btn btn-sm exam-flag" data-testid="exam-flag-toggle" :aria-pressed="isFlagged" :disabled="answersLocked" :class="{ 'is-on': isFlagged }" @click="toggleCurrentFlag">
            <LinearIcon name="flag" :size="13" />{{ isFlagged ? t('ep.exam.flagged') : t('ep.exam.flag') }}
            <kbd>F</kbd>
          </button>
          <span class="exam-action-spacer"></span>
          <button type="button" class="btn btn-sm" :disabled="currentIndex === 0" :title="t('ep.practice.prev')" @click="goTo(currentIndex - 1)">
            <LinearIcon name="arrow-left" :size="14" /><span class="nav-label">{{ t('ep.practice.prev') }}</span>
          </button>
          <button type="button" class="btn btn-sm btn-primary" :disabled="currentIndex >= questions.length - 1" :title="t('ep.practice.next')" @click="goTo(currentIndex + 1)">
            <span class="nav-label">{{ t('ep.practice.next') }}</span><LinearIcon name="arrow-right" :size="14" />
          </button>
        </div>
      </footer>
    </template>

    <div v-else-if="!loading" class="exam-loading">
      <div class="empty-title">{{ t('ep.practice.no_questions') }}</div>
      <div class="empty-desc">{{ t('ep.exam.papers_empty_hint') }}</div>
      <button type="button" class="btn" @click="handleBack">{{ t('ep.exam.back_center') }}</button>
    </div>

    <!-- Mobile answer sheet -->
    <div v-if="showMobileSheet" class="exam-sheet-backdrop" @click.self="showMobileSheet = false">
      <div class="exam-sheet-drawer" role="dialog" aria-modal="true" :aria-label="t('ep.exam.sheet')">
        <div class="sheet-head">
          <div>
            <span class="sheet-title">{{ t('ep.exam.sheet') }}</span>
            <span class="sheet-count mono">{{ answeredCount }} / {{ questions.length }}</span>
          </div>
          <button type="button" class="icon-btn" :aria-label="t('ep.common.close')" @click="showMobileSheet = false"><LinearIcon name="x" :size="16" /></button>
        </div>
        <div class="sheet-legend">
          <span><i class="dot answered"></i>{{ t('ep.exam.answered') }}</span>
          <span><i class="dot flagged"></i>{{ t('ep.exam.flagged') }}</span>
          <span><i class="dot current"></i>{{ t('ep.exam.sheet') }}</span>
        </div>
        <div class="answer-grid">
          <button
            v-for="(item, index) in questions"
            :key="item.id"
            type="button"
            class="answer-cell mono"
            :class="answerButtonClass(item.id, index)"
            :aria-label="`${t('ep.practice.question_no', { current: index + 1 })} ${answerState(item.id).answered ? t('ep.exam.answered') : t('ep.exam.blank')}${answerState(item.id).flagged ? ' ' + t('ep.exam.flagged') : ''}`"
            @click="goTo(index); showMobileSheet = false"
          >{{ index + 1 }}</button>
        </div>
        <div class="sheet-drawer-foot">
          <ThemeToggle compact />
          <LocaleToggle compact />
        </div>
      </div>
    </div>

    <!-- Explicit deadline recovery: only this action may finalise a late paper -->
    <div v-if="showExpiredSubmitConfirm" class="exam-overlay" @click.self="showExpiredSubmitConfirm = false" data-testid="exam-expired-confirm">
      <section class="exam-dialog" role="dialog" aria-modal="true" aria-labelledby="exam-expired-title">
        <div class="dialog-head">
          <span id="exam-expired-title" class="dialog-title">{{ expiredCopy.submit_server }}</span>
          <button type="button" class="icon-btn" :aria-label="t('ep.common.close')" @click="showExpiredSubmitConfirm = false"><LinearIcon name="x" :size="16" /></button>
        </div>
        <div class="exam-dialog-body">
          <p>{{ expiredCopy.confirm }}</p>
          <p v-if="unsubmittedQuestionNumbers.length" class="exam-dialog-warn" data-testid="exam-expired-confirm-unsubmitted">
            {{ expiredCopy.unsubmitted }}
            <span v-for="number in unsubmittedQuestionNumbers" :key="number">{{ t('ep.practice.question_no', { current: number }) }}</span>
          </p>
        </div>
        <div class="dialog-actions">
          <button type="button" class="btn" @click="showExpiredSubmitConfirm = false">{{ expiredCopy.cancel }}</button>
          <button type="button" class="btn btn-primary" data-testid="exam-expired-confirm-submit" :disabled="isSubmitting" @click="submitWithServerAnswers">{{ expiredCopy.confirm_submit }}</button>
        </div>
      </section>
    </div>

    <!-- Submit confirmation -->
    <div v-if="showSubmitConfirm" class="exam-overlay" @click.self="showSubmitConfirm = false" data-testid="exam-submit-confirm">
      <section class="exam-dialog" role="dialog" aria-modal="true" aria-labelledby="exam-submit-title">
        <div class="dialog-head">
          <span id="exam-submit-title" class="dialog-title">{{ t('ep.exam.submit') }}</span>
          <button type="button" class="icon-btn" :aria-label="t('ep.common.close')" @click="showSubmitConfirm = false"><LinearIcon name="x" :size="16" /></button>
        </div>
        <div class="exam-dialog-body">
          <p>{{ t('ep.exam.submit_confirm') }}</p>
          <p class="exam-dialog-stats">
            {{ t('ep.exam.submit_stats', { answered: answeredCount, blank: questions.length - answeredCount, flagged: flaggedCount }) }}
          </p>
          <p v-if="questions.length - answeredCount > 0" class="exam-dialog-warn">
            {{ t('ep.exam.submit_blank_warn', { count: questions.length - answeredCount }) }}
            <button type="button" class="link-btn" @click="jumpToFirstUnanswered">{{ t('ep.exam.sheet') }}</button>
          </p>
        </div>
        <div class="dialog-actions">
          <button type="button" class="btn" :disabled="isSubmitting" @click="showSubmitConfirm = false">{{ t('ep.common.cancel') }}</button>
          <button type="button" class="btn btn-primary" :disabled="isSubmitting" @click="submitExam(false)">{{ isSubmitting ? t('ep.common.loading') : t('ep.exam.submit') }}</button>
        </div>
      </section>
    </div>

    <!-- Exit confirmation -->
    <div v-if="showExitConfirmModal" class="exam-overlay" @click.self="handleCancelExit" data-testid="exam-exit-confirm-modal">
      <section class="exam-dialog" role="dialog" aria-modal="true" aria-labelledby="exam-exit-title">
        <div class="dialog-head">
          <span id="exam-exit-title" class="dialog-title">{{ t('ep.exam.abandon') }}</span>
        </div>
        <div class="exam-dialog-body">
          <p>{{ t('ep.exam.abandon_confirm') }}</p>
        </div>
        <div class="dialog-actions">
          <button type="button" class="btn" @click="handleCancelExit">{{ t('ep.exam.resume') }}</button>
          <button type="button" class="btn btn-primary" @click="handleConfirmExit">{{ t('ep.exam.runner_exit') }}</button>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import LinearIcon from '../../components/LinearIcon.vue'
import ThemeToggle from '../../components/ThemeToggle.vue'
import LocaleToggle from '../../components/LocaleToggle.vue'
import { useLocale, getCurrentLocale } from '../../composables/useLocale.js'
import { useKeyboardInset } from '../../composables/useKeyboardInset.js'
import { useAuthStore } from '../../stores/authStore'
import { completeSession, getSession, getSessionQuestions, submitAttempt, syncDraft, toggleFlag } from '../../api/practice'
import { buildExamDraftBase, buildExamDraftPayload, buildExamLocalDraft, calculateAccuracy, examAnswerState, examAnswersToBase, examLocalDraftDiffers, examLocalDraftKey, examRecoveryBase, findFirstUnansweredIndex, formatQuestionTypeName, formatRemainingTime, isExamNetworkError, isExamTimeExpiredError, isExamReviewItem, isSwipeGestureValid, mergeExamLocalDraft, normalizeDraftConflicts, resolveExamUserKey, unsubmittedExamAnswers } from '../../domain/exam'

const { t } = useLocale()
useKeyboardInset()
const router = useRouter()
const auth = useAuthStore()
const examUserKey = computed(() => resolveExamUserKey(auth.user?.value || auth.user))

const props = defineProps({ token: { type: String, required: true }, sessionId: { type: String, required: true } })
const emit = defineEmits(['back'])

const showExitConfirmModal = ref(false)

function handleBack() {
  if (report.value || reportLoadFailed.value || isSessionCompleted(session.value)) {
    doExit()
    return
  }
  showExitConfirmModal.value = true
}

function isSessionCompleted(value) {
  return Boolean(value?.is_completed) || value?.status === 'completed'
}

async function handleConfirmExit() {
  showExitConfirmModal.value = false
  await persistDraft(true)
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
const session = ref(null)
const questions = ref([])
const answers = ref({})
const flags = ref([])
const currentIndex = ref(0)
const elapsedSeconds = ref(0)
const report = ref(null)
const reportLoadFailed = ref(false)
const loading = ref(true)
const error = ref('')
const showMobileSheet = ref(false)
const draftConflicts = ref([])
const draftBase = ref({})
const pendingSubmit = ref(false)
const offlineNotice = ref('')
const offlineRetryAvailable = ref(false)
// Set only when the server answered EXAM_TIME_EXPIRED. It is terminal: no
// automatic retry, no silent submission. The user must explicitly choose to
// finalise with the answers the server already saved.
const syncExpired = ref(false)
const showExpiredSubmitConfirm = ref(false)

// Kept local to this runner because the shared locale files are owned by other
// work in this batch; both shipped languages must still be complete.
const EXPIRED_COPY = {
  'zh-CN': {
    notice: '模考已超过截止时间，服务器不再接受这台设备上的答案同步。',
    unsubmitted: '以下本地答案未能提交：',
    none: '本机没有未提交的答案。',
    kept: '未提交的答案仍保留在这台设备上。',
    submit_server: '以服务器已保存的答案交卷',
    confirm: '将以服务器在截止前已保存的答案交卷，本机未提交的答案不会计入成绩。交卷后不可撤销。',
    confirm_submit: '确认交卷',
    cancel: '暂不交卷',
  },
  'en-US': {
    notice: 'The exam deadline has passed and the server no longer accepts answer syncs from this device.',
    unsubmitted: 'These local answers were not submitted:',
    none: 'This device has no unsubmitted answers.',
    kept: 'The unsubmitted answers remain saved on this device.',
    submit_server: 'Submit with the answers saved on the server',
    confirm: 'The paper will be finalised with the answers the server saved before the deadline. Local unsubmitted answers will not be scored. This cannot be undone.',
    confirm_submit: 'Submit now',
    cancel: 'Not yet',
  },
}

const expiredCopy = computed(() => EXPIRED_COPY[getCurrentLocale() === 'en-US' ? 'en-US' : 'zh-CN'])
const unsubmittedAnswers = computed(() => unsubmittedExamAnswers(answers.value, draftBase.value))
const unsubmittedQuestionNumbers = computed(() => {
  const order = new Map(questions.value.map((item, index) => [item?.id, index + 1]))
  return unsubmittedAnswers.value
    .map(item => order.get(item.question_id))
    .filter(number => number !== undefined)
})

let touchStartX = 0
let touchStartY = 0
function handleTouchStart(e) {
  if (!e.touches || e.touches.length !== 1) return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
}
function handleTouchEnd(e) {
  if (!e.changedTouches || e.changedTouches.length !== 1) return
  const touchEndX = e.changedTouches[0].clientX
  const touchEndY = e.changedTouches[0].clientY
  const gesture = isSwipeGestureValid(touchStartX, touchStartY, touchEndX, touchEndY)
  if (gesture === 'prev' && currentIndex.value > 0) {
    goTo(currentIndex.value - 1)
  } else if (gesture === 'next' && currentIndex.value < questions.value.length - 1) {
    goTo(currentIndex.value + 1)
  }
}

const isSubmitting = ref(false)
const showSubmitConfirm = ref(false)
let tickHandle
let draftHandle
let draftPromise = null
const question = computed(() => questions.value[currentIndex.value])
const remainingSeconds = computed(() => Math.max(0, Number(session.value?.time_limit || 0) * 60 - elapsedSeconds.value))
const timeExpired = computed(() => Boolean(session.value?.time_limit) && remainingSeconds.value <= 0)
// Once the clock runs out the server rejects further draft writes, so the paper
// becomes read-only even if the auto-submit is still pending on this device.
const answersLocked = computed(() => Boolean(report.value) || timeExpired.value || pendingSubmit.value || syncExpired.value)
const connectionNotice = computed(() => {
  if (syncExpired.value) return ''
  if (pendingSubmit.value) return t('ep.practice.draft_offline_notice')
  return offlineRetryAvailable.value ? offlineNotice.value : ''
})
const answeredCount = computed(() => questions.value.filter(item => answerState(item.id).answered).length)
const flaggedCount = computed(() => flags.value.length)
const isFlagged = computed(() => question.value ? flags.value.includes(question.value.id) : false)
const currentTextAnswer = computed(() => {
  const value = question.value ? answerValue(question.value.id) : ''
  return Array.isArray(value) ? value.join('') : String(value ?? '')
})
const reviewQuestions = computed(() => questions.value.filter(item => isExamReviewItem(item.id, report.value?.answers)))

function answerValue(questionId) {
  const saved = answers.value[questionId]
  return saved && typeof saved === 'object' && !Array.isArray(saved)
    ? saved.user_answer ?? saved.answer ?? ''
    : saved ?? ''
}

function answerState(questionId) { return examAnswerState(questionId, answers.value, flags.value) }
function isOptionSelected(key) {
  const value = answerValue(question.value.id)
  return question.value.type === 'MULTI' ? Array.isArray(value) && value.includes(key) : value === key
}
function answerButtonClass(questionId, index) {
  const state = answerState(questionId)
  return { current: index === currentIndex.value, answered: state.answered, flagged: state.flagged }
}
function displayAnswer(value) {
  if (Array.isArray(value)) return value.join('、') || t('ui.k0112')
  return value === undefined || value === null || value === '' ? t('ui.k0112') : String(value)
}

function isBlankReportItem(questionId) {
  const entry = report.value?.answers?.[questionId]
  return !entry || entry.correctness === 'UNANSWERED'
}

function dismissDraftConflicts() {
  // The server keeps the value saved elsewhere, so dismissing means accepting
  // it. A paper that was already waiting on its time-up submission can then
  // finish; nothing is dropped silently because the user made the choice.
  draftConflicts.value = []
  saveLocalExamDraft()
  if (pendingSubmit.value) void submitExam(true)
  else scheduleDraftSave()
}

function restoreMyAnswers() {
  // With optimistic draft sync the server keeps the answer saved elsewhere and
  // reports this device's value as rejected. "Keep my answer" re-applies the
  // rejected value now that the baseline matches the server.
  for (const conflict of draftConflicts.value) {
    answers.value[conflict.question_id] = conflict.incoming_answer
  }
  draftConflicts.value = []
  saveLocalExamDraft()
  if (pendingSubmit.value) void submitExam(true)
  else scheduleDraftSave()
}

function draftStorageKeys() {
  const scoped = examLocalDraftKey(props.sessionId, examUserKey.value)
  const legacy = examLocalDraftKey(props.sessionId)
  return { scoped, legacy: legacy && legacy !== scoped ? legacy : '' }
}

function readStoredDraft(key) {
  if (!key || typeof localStorage === 'undefined') return null
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || 'null')
    if (!parsed || typeof parsed !== 'object' || !parsed.answers || typeof parsed.answers !== 'object') return null
    return parsed
  } catch (_) {
    return null
  }
}

function readLocalExamDraft() {
  const { scoped, legacy } = draftStorageKeys()
  // A draft written before per-account scoping is still this user's (session ids
  // are issued per account); reading it lets the next write migrate it.
  return readStoredDraft(scoped) || (legacy ? readStoredDraft(legacy) : null)
}

function saveLocalExamDraft() {
  const { scoped, legacy } = draftStorageKeys()
  if (!scoped || typeof localStorage === 'undefined' || !session.value || report.value || isSessionCompleted(session.value)) return
  try {
    localStorage.setItem(scoped, JSON.stringify(buildExamLocalDraft({
      answers: answers.value,
      baseAnswers: draftBase.value,
      flags: flags.value,
      currentIndex: currentIndex.value,
      timeSpent: elapsedSeconds.value,
      pendingSubmit: pendingSubmit.value,
    })))
    if (legacy) localStorage.removeItem(legacy)
  } catch (_) { /* quota / private mode: the server sync remains the fallback */ }
}

function clearLocalExamDraft() {
  const { scoped, legacy } = draftStorageKeys()
  for (const key of [scoped, legacy]) {
    if (!key || typeof localStorage === 'undefined') continue
    try { localStorage.removeItem(key) } catch (_) {}
  }
  offlineNotice.value = ''
  offlineRetryAvailable.value = false
}

function markPendingSubmit() {
  if (report.value) return
  pendingSubmit.value = true
  saveLocalExamDraft()
}

/**
 * The server rejected a late draft/answer with EXAM_TIME_EXPIRED. This is a
 * terminal state: stop every automatic retry, keep the device copy, and wait
 * for the user to explicitly choose the server-saved answers.
 */
function enterExpiredState() {
  if (report.value) return
  syncExpired.value = true
  pendingSubmit.value = false
  offlineNotice.value = ''
  offlineRetryAvailable.value = false
  clearTimeout(draftHandle)
  clearInterval(tickHandle)
  saveLocalExamDraft()
}

/**
 * Explicit, user-triggered finalisation after the deadline. Only the answers
 * the server saved before the deadline are scored; this is never called
 * automatically, so a late paper is never silently submitted.
 */
async function submitWithServerAnswers() {
  if (isSubmitting.value || report.value || !syncExpired.value) return
  isSubmitting.value = true
  error.value = ''
  showExpiredSubmitConfirm.value = false
  try {
    report.value = await completeSession(props.token, props.sessionId)
    report.value.time_spent = elapsedSeconds.value
    syncExpired.value = false
    pendingSubmit.value = false
    clearLocalExamDraft()
  } catch (err) {
    if (isExamTimeExpiredError(err)) {
      enterExpiredState()
      error.value = err.detail || err.message
    } else {
      error.value = `${t('ui.k0115')}${err.detail || err.message}`
    }
  } finally {
    isSubmitting.value = false
  }
}

function retrySync() {
  if (isSubmitting.value || report.value || syncExpired.value) return
  if (pendingSubmit.value || timeExpired.value) void recoverPendingSubmit()
  else void persistDraft()
}

async function recoverPendingSubmit() {
  if (isSubmitting.value || report.value || syncExpired.value) return
  if (pendingSubmit.value) {
    // A previous complete may have succeeded while its response was lost (or
    // another device finalised the paper). Completing is idempotent; prefer the
    // server's final report instead of replaying a draft the server will reject.
    try {
      const fresh = await getSession(props.token, props.sessionId)
      if (fresh?.is_completed) {
        report.value = await completeSession(props.token, props.sessionId)
        report.value.time_spent = elapsedSeconds.value
        pendingSubmit.value = false
        clearLocalExamDraft()
        return
      }
    } catch (_) { /* fall through to the normal draft-then-complete path */ }
  }
  await submitExam(true)
}

function handleOnline() {
  if (report.value || reportLoadFailed.value || !session.value) return
  // After the deadline the server will keep rejecting drafts; retrying on every
  // reconnect is the endless loop this guard prevents.
  if (syncExpired.value) return
  if (pendingSubmit.value) {
    void recoverPendingSubmit()
    return
  }
  if (!draftConflicts.value.length && offlineRetryAvailable.value) void persistDraft()
}

function scheduleDraftSave() {
  clearTimeout(draftHandle)
  draftHandle = setTimeout(() => { void persistDraft() }, 400)
}

async function persistDraft(force = false) {
  if (!session.value || isSessionCompleted(session.value) || (isSubmitting.value && !force) || report.value) return false
  if (draftPromise) {
    try { await draftPromise } catch (_) { /* reported by the owning call */ }
  }
  if (!session.value || isSessionCompleted(session.value) || (isSubmitting.value && !force) || report.value) return false
  const changedAnswers = buildExamDraftPayload(answers.value, draftBase.value)
  const payload = {
    current_index: currentIndex.value,
    flags: flags.value,
    time_spent: elapsedSeconds.value,
  }
  if (Object.keys(changedAnswers).length) {
    payload.answers = changedAnswers
    payload.base_answers = buildExamDraftBase(changedAnswers, draftBase.value)
  }
  // Persist before the request so a reload during a slow/failed sync still
  // restores what the user typed.
  saveLocalExamDraft()
  draftPromise = syncDraft(props.token, props.sessionId, payload)
  try {
    const saved = await draftPromise
    offlineNotice.value = ''
    offlineRetryAvailable.value = false
    if (saved?.answers) draftBase.value = examAnswersToBase(saved.answers)
    if (saved?.has_conflict) {
      const conflicts = normalizeDraftConflicts(saved.conflicts, questions.value)
      // The service keeps the value saved elsewhere, so the paper must show it;
      // the notice offers an explicit way to re-apply this device's answer.
      for (const conflict of conflicts) {
        answers.value[conflict.question_id] = conflict.existing_answer
      }
      draftConflicts.value = conflicts
      // Keep the device backup aligned with the server's resolved value so a
      // reload does not resurrect the rejected answer as a fresh "local" edit.
      saveLocalExamDraft()
    }
    saveLocalExamDraft()
    return true
  } catch (err) {
    if (isExamTimeExpiredError(err)) {
      enterExpiredState()
      return false
    }
    if (isExamNetworkError(err)) {
      offlineNotice.value = t('ep.practice.draft_offline_notice')
      offlineRetryAvailable.value = true
    } else {
      error.value = `${t('ui.k0113')}${err.detail || err.message}`
    }
    saveLocalExamDraft()
    return false
  } finally {
    draftPromise = null
  }
}

function selectOption(key, checked) {
  if (!question.value || answersLocked.value) return
  if (question.value.type === 'MULTI') {
    const selected = Array.isArray(answerValue(question.value.id)) ? [...answerValue(question.value.id)] : []
    answers.value[question.value.id] = checked ? [...new Set([...selected, key])].sort() : selected.filter(value => value !== key)
  } else {
    answers.value[question.value.id] = key
  }
  saveLocalExamDraft()
  scheduleDraftSave()
}

function setTextAnswer(value) {
  if (!question.value || answersLocked.value) return
  answers.value[question.value.id] = value
  saveLocalExamDraft()
  scheduleDraftSave()
}

function goTo(index) {
  if (index < 0 || index >= questions.value.length) return
  currentIndex.value = index
  scheduleDraftSave()
}

async function toggleCurrentFlag() {
  if (!question.value || answersLocked.value) return
  error.value = ''
  try {
    const result = await toggleFlag(props.token, props.sessionId, question.value.id)
    flags.value = result.flags
    saveLocalExamDraft()
    scheduleDraftSave()
  } catch (err) {
    error.value = err.detail || err.message
  }
}

function restartTicker() {
  clearInterval(tickHandle)
  if (!report.value) tickHandle = setInterval(tick, 1000)
}

async function submitExam(automatic) {
  if (isSubmitting.value || report.value) return
  // Once the server has declared the deadline passed, only the explicit
  // server-answer action may finalise the paper.
  if (syncExpired.value) return
  if (!automatic && draftConflicts.value.length) {
    // Do not finalise a paper while a draft conflict is unresolved: the user
    // must decide whether to keep this device's answer first.
    showSubmitConfirm.value = false
    error.value = t('ep.exam.draft_conflict_submit')
    return
  }
  isSubmitting.value = true
  error.value = ''
  showSubmitConfirm.value = false
  clearTimeout(draftHandle)
  clearInterval(tickHandle)
  try {
    const saved = await persistDraft(true)
    if (!saved) {
      // A terminal EXAM_TIME_EXPIRED must never fall through to completing with
      // the server copy; the banner asks the user to decide explicitly.
      if (syncExpired.value) return
      // Never complete with the server's older draft. The user's answers stay
      // in the device backup and a time-up submission stays pending until the
      // connection returns (or the user retries explicitly).
      if (automatic || timeExpired.value) markPendingSubmit()
      else restartTicker()
      return
    }
    if (draftConflicts.value.length) {
      // A cross-device conflict is the user's call. Surface it and hold the
      // submission instead of picking a side silently.
      if (!automatic) error.value = t('ep.exam.draft_conflict_submit')
      if (automatic || timeExpired.value) markPendingSubmit()
      else restartTicker()
      return
    }
    pendingSubmit.value = false
    try {
      report.value = await completeSession(props.token, props.sessionId)
      report.value.time_spent = elapsedSeconds.value
      clearLocalExamDraft()
      if (automatic) error.value = t('ui.k0114')
    } catch (err) {
      if (isExamTimeExpiredError(err)) {
        enterExpiredState()
        return
      }
      // The draft is already saved on the server, so completing later is safe
      // and idempotent; keep the local copy until the report actually arrives.
      error.value = `${t('ui.k0115')}${err.detail || err.message}`
      if (automatic || timeExpired.value) markPendingSubmit()
      else restartTicker()
    }
  } finally {
    isSubmitting.value = false
  }
}

function tick() {
  if (syncExpired.value) return
  elapsedSeconds.value += 1
  if (session.value?.time_limit && remainingSeconds.value <= 0) {
    // A pending submission is retried by the online event / retry button, not
    // every second, so an offline device does not hammer the network.
    if (!pendingSubmit.value) void submitExam(true)
  } else if (elapsedSeconds.value % 10 === 0) {
    void persistDraft()
  }
}

function jumpToFirstUnanswered() {
  const idx = findFirstUnansweredIndex(questions.value, answers.value)
  if (idx >= 0) {
    goTo(idx)
    showSubmitConfirm.value = false
  }
}

function handleKeyDown(e) {
  const targetTag = e.target?.tagName?.toLowerCase()
  if (targetTag === 'input' || targetTag === 'textarea' || targetTag === 'select') {
    return
  }

  const key = e.key.toUpperCase()

  // While a dialog or the mobile answer sheet is open, only Escape is handled
  // below; keystrokes must not silently change the answer behind the overlay.
  if ((showSubmitConfirm.value || showExitConfirmModal.value || showMobileSheet.value) && e.key !== 'Escape') {
    return
  }

  // 1. Select options via A, B, C, D... or 1, 2, 3, 4...
  if (question.value?.options?.length && !report.value && !answersLocked.value) {
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
        const currentSelected = isOptionSelected(optKey)
        selectOption(optKey, !currentSelected)
        return
      }
    }
  }

  // 2. Next on Space, ArrowRight, J
  if (e.key === ' ' || e.key === 'ArrowRight' || key === 'J') {
    if (currentIndex.value < questions.value.length - 1) {
      e.preventDefault()
      goTo(currentIndex.value + 1)
      return
    }
  }

  // 3. Prev on ArrowLeft, K
  if (e.key === 'ArrowLeft' || key === 'K') {
    if (currentIndex.value > 0) {
      e.preventDefault()
      goTo(currentIndex.value - 1)
      return
    }
  }

  // 4. Toggle flag on F
  if (key === 'F') {
    e.preventDefault()
    if (!answersLocked.value) toggleCurrentFlag()
    return
  }

  // 5. Esc closes confirm modal
  if (e.key === 'Escape' && showSubmitConfirm.value) {
    e.preventDefault()
    showSubmitConfirm.value = false
    return
  }
}

async function retryLoadReport() {
  if (loading.value) return
  reportLoadFailed.value = false
  loading.value = true
  try {
    const fresh = await getSession(props.token, props.sessionId)
    session.value = fresh
    if (fresh?.report) {
      report.value = fresh.report
    } else {
      reportLoadFailed.value = true
    }
  } catch (_) {
    reportLoadFailed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('online', handleOnline)
  try {
    session.value = await getSession(props.token, props.sessionId)
    if (session.value?.mode !== 'EXAM') {
      router.replace(`/practice/${props.sessionId}`)
      return
    }
    if (isSessionCompleted(session.value)) {
      // A finished paper is a report, not a runner. Starting the ticker or the
      // draft pipeline here would treat it as an active exam again.
      if (session.value?.report) {
        report.value = session.value.report
        clearLocalExamDraft()
      } else {
        reportLoadFailed.value = true
      }
      return
    }
    questions.value = await getSessionQuestions(props.token, props.sessionId)
    const serverAnswers = session.value.answers || {}
    const localDraft = session.value.is_completed ? null : readLocalExamDraft()
    answers.value = localDraft ? mergeExamLocalDraft(serverAnswers, localDraft) : { ...serverAnswers }
    // The baseline is always what the server last showed us, so a local edit
    // that now differs from another device is reported as a conflict by the
    // next sync instead of silently overwriting it. Unsynced device edits keep
    // their older baseline so that difference stays detectable.
    draftBase.value = localDraft ? examRecoveryBase(serverAnswers, localDraft) : examAnswersToBase(serverAnswers)
    flags.value = [...((Array.isArray(localDraft?.flags) ? localDraft.flags : session.value.flags) || [])]
    const restoredIndex = Number(localDraft?.currentIndex ?? session.value.current_index ?? 0)
    currentIndex.value = Math.min(Math.max(0, restoredIndex), Math.max(0, questions.value.length - 1))
    elapsedSeconds.value = Math.max(Number(session.value.time_spent || 0), Number(localDraft?.timeSpent || 0))
    pendingSubmit.value = Boolean(localDraft?.pendingSubmit)
    const localDiverged = Boolean(localDraft) && examLocalDraftDiffers(localDraft, serverAnswers)
    if (!report.value && session.value.time_limit > 0) {
      const createdAt = Date.parse(`${session.value.created_at}Z`)
      if (Number.isFinite(createdAt)) elapsedSeconds.value = Math.max(elapsedSeconds.value, Math.floor((Date.now() - createdAt) / 1000))
    }
    if (!report.value) {
      if (session.value.is_expired) {
        // The server already considers the deadline passed. Enter the terminal
        // state instead of replaying the device draft and retrying forever.
        enterExpiredState()
      } else {
        tickHandle = setInterval(tick, 1000)
        saveLocalExamDraft()
        if (pendingSubmit.value) {
          // A time-up submission that could not be delivered before the reload:
          // recover it safely once this device is back online.
          if (navigator?.onLine !== false) void submitExam(true)
        } else if (localDiverged && navigator?.onLine !== false) {
          // Push the restored device answers to the server; any cross-device
          // difference comes back as an explicit conflict notice.
          void persistDraft()
        }
      }
    }
  } catch (err) {
    error.value = err.detail || err.message
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('online', handleOnline)
  clearInterval(tickHandle)
  clearTimeout(draftHandle)
  if (session.value && !report.value && !reportLoadFailed.value && !isSessionCompleted(session.value)) {
    saveLocalExamDraft()
    void persistDraft()
  }
})
</script>

<style scoped>
.exam-mode {
  --exam-bar-h: 60px;
  min-height: 100vh;
  background: var(--paper);
  color: var(--ink);
  padding-top: var(--exam-bar-h);
  padding-bottom: 76px;
}

/* ---------- instrument top bar ---------- */
.exam-topbar {
  --exam-chrome-bg: var(--d-spine, var(--ink));
  --exam-chrome-ink: var(--d-spine-ink, var(--brand-contrast));
  --exam-chrome-quiet: var(--d-spine-ink-2, color-mix(in srgb, var(--brand-contrast) 68%, transparent));
  --exam-chrome-line: var(--d-spine-line, color-mix(in srgb, var(--brand-contrast) 22%, transparent));
  --exam-accent-bg: var(--d-spine-accent, var(--brand-contrast));
  --exam-accent-ink: var(--d-spine, var(--ink));
  --exam-warn-ink: color-mix(in srgb, var(--bad) 58%, var(--d-spine-ink, var(--brand-contrast)));
  position: fixed;
  inset: 0 0 auto;
  z-index: 40;
  height: var(--exam-bar-h);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  background: var(--exam-chrome-bg);
  color: var(--exam-chrome-ink);
  border-bottom: 1px solid var(--exam-chrome-line);
}
.exam-top-left,
.exam-top-right {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.exam-top-left { gap: 12px; justify-content: flex-start; }
.exam-top-right { justify-content: flex-end; }
.exam-bar-center {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
}
.exam-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--exam-chrome-quiet);
  font-family: var(--font-sans);
  font-size: 12.5px;
  padding: 4px 2px;
  cursor: pointer;
}
.exam-back:hover { color: var(--exam-chrome-ink); }
.exam-sep { width: 1px; height: 18px; background: var(--exam-chrome-line); }
.exam-identity { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.exam-kicker {
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 650;
  letter-spacing: .02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--exam-chrome-ink);
}
.exam-sub {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--exam-chrome-quiet);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.exam-topbar .exam-timer {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 16px;
  border: 0;
  border-left: 1px solid var(--exam-chrome-line);
  border-right: 1px solid var(--exam-chrome-line);
  border-radius: 0;
  background: transparent;
  color: var(--exam-chrome-ink);
}
.exam-topbar .exam-timer .timer-cap {
  font-family: var(--font-sans);
  font-size: 12px;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--exam-chrome-quiet);
}
.exam-topbar .exam-timer strong { font-size: 22px; font-weight: 600; letter-spacing: .04em; }
.exam-topbar .exam-timer.low {
  border-color: color-mix(in srgb, var(--bad) 58%, transparent);
  background: color-mix(in srgb, var(--bad) 16%, transparent);
}
.exam-topbar .exam-timer.low strong { color: var(--exam-warn-ink); }
.exam-utils { display: flex; align-items: center; gap: 6px; color: var(--exam-chrome-ink); }
.exam-topbar .theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border: 1px solid transparent;
  border-radius: var(--r-xs);
  background: transparent;
  color: var(--exam-chrome-quiet);
  font-family: var(--font-sans);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
}
.exam-topbar .theme-toggle:hover {
  color: var(--exam-chrome-ink);
  border-color: var(--exam-chrome-line);
  background: color-mix(in srgb, var(--exam-chrome-ink) 12%, transparent);
}
.exam-topbar .btn {
  background: transparent;
  border-color: var(--exam-chrome-line);
  color: var(--exam-chrome-ink);
}
.exam-topbar .btn:hover {
  background: color-mix(in srgb, var(--exam-chrome-ink) 12%, transparent);
  border-color: var(--exam-chrome-quiet);
  color: var(--exam-chrome-ink);
}
.exam-topbar .btn-primary {
  background: var(--exam-accent-bg);
  border-color: var(--exam-accent-bg);
  color: var(--exam-accent-ink);
}
.exam-topbar .btn-primary:hover {
  background: color-mix(in srgb, var(--exam-accent-bg) 86%, var(--exam-chrome-bg));
  border-color: color-mix(in srgb, var(--exam-accent-bg) 86%, var(--exam-chrome-bg));
  color: var(--exam-accent-ink);
}
.exam-submit { white-space: nowrap; }

/* ---------- runner layout ---------- */
.exam-mode .exam-layout {
  display: grid;
  grid-template-columns: minmax(0, var(--reading-w)) var(--rail-exam, 232px);
  gap: clamp(32px, 5vw, 72px);
  justify-content: center;
  align-items: start;
  width: min(100% - 48px, 1120px);
  max-width: none;
  margin: 0 auto;
  padding: 40px 0 48px;
}
.exam-paper { min-width: 0; }
.exam-q-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
  font-family: var(--font-sans);
  font-size: 12px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.exam-stem {
  font-family: var(--font-serif);
  font-size: 20px;
  line-height: 1.72;
  letter-spacing: .01em;
  margin: 0 0 30px;
  white-space: pre-wrap;
}
.exam-options { display: flex; flex-direction: column; border-top: 1px solid var(--line); }
.exam-option {
  position: relative;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) 18px;
  align-items: start;
  gap: 10px;
  padding: 14px 10px;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  transition: background .14s var(--ease);
}
.exam-option:hover { background: var(--surface-2); }
.exam-option input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}
.exam-option .key-cap {
  border: 0;
  background: transparent;
  padding: 0;
  min-width: 0;
  height: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-3);
  padding-top: 5px;
}
.option-content-text {
  font-family: var(--font-serif);
  font-size: 16.5px;
  line-height: 1.65;
  white-space: pre-wrap;
}
.option-indicator {
  width: 11px;
  height: 11px;
  margin-top: 7px;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  background: transparent;
}
.exam-option.selected { background: var(--brand-soft); }
.exam-option.selected .key-cap { color: var(--brand); font-weight: 700; }
.exam-option.selected .option-indicator {
  border-color: var(--brand);
  background: var(--brand);
  box-shadow: inset 0 0 0 2px var(--brand-soft);
}
.exam-text-answer { margin-top: 4px; }
.exam-text-answer textarea { width: 100%; resize: vertical; }

/* ---------- answer sheet rail ---------- */
.exam-sheet {
  position: sticky;
  top: calc(var(--exam-bar-h) + 24px);
  padding-top: 4px;
}
.sheet-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.sheet-title {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.sheet-count { font-size: 12px; color: var(--ink-2); }
.sheet-progress {
  height: 3px;
  background: var(--surface-3);
  overflow: hidden;
  margin-bottom: 14px;
}
.sheet-progress i { display: block; height: 100%; background: var(--brand); transition: width .3s var(--ease); }
.sheet-facts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 0 0 16px;
}
.sheet-facts div { display: flex; flex-direction: column; gap: 2px; }
.sheet-facts dt {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--ink-4);
  letter-spacing: .04em;
}
.sheet-facts dd { margin: 0; font-size: 13px; color: var(--ink); }
.answer-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 5px;
}
.answer-cell {
  height: 30px;
  border: 1px solid var(--line);
  border-radius: var(--r-xs);
  background: transparent;
  color: var(--ink-3);
  font-size: 12px;
  cursor: pointer;
}
.answer-cell:hover { border-color: var(--line-strong); color: var(--ink); }
.answer-cell.answered { background: var(--surface-2); color: var(--ink-2); border-color: var(--line-strong); }
.answer-cell.flagged { box-shadow: inset 0 -2px var(--flag); }
.answer-cell.current { border-color: var(--ink); color: var(--ink); font-weight: 700; }
.sheet-note {
  margin: 16px 0 0;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-4);
}

/* ---------- bottom instrument bar ---------- */
.exam-actionbar {
  position: fixed;
  inset: auto 0 var(--kb-inset, 0px);
  z-index: 40;
  background: color-mix(in srgb, var(--paper) 94%, transparent);
  backdrop-filter: blur(10px);
  border-top: 1px solid var(--line);
  padding: 9px 18px calc(9px + env(safe-area-inset-bottom, 0px));
}
.exam-action-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(100%, 1120px);
  margin: 0 auto;
}
.exam-action-spacer { flex: 1; }
.exam-flag.is-on { border-color: var(--warn-line); background: var(--warn-soft); color: var(--warn); }
.exam-flag kbd { margin-left: 2px; }
.exam-sheet-trigger { display: none; }
.exam-sheet-trigger .mono { margin-left: 2px; color: var(--ink-3); font-size: 12px; }

/* ---------- report ---------- */
.exam-report {
  width: min(100% - 48px, 820px);
  margin: 0 auto;
  padding: 48px 0 72px;
}
.report-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 40px;
  padding-bottom: 26px;
  border-bottom: 1px solid var(--line-strong);
}
.report-score {
  margin: 8px 0 0;
  font-family: var(--font-serif);
  font-size: 64px;
  line-height: 1;
  letter-spacing: -.02em;
  font-weight: 500;
}
.report-score-cap {
  margin: 6px 0 0;
  font-family: var(--font-sans);
  font-size: 12px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.report-facts {
  display: flex;
  gap: 28px;
  margin: 0;
}
.report-facts div { display: flex; flex-direction: column; gap: 4px; }
.report-facts dt {
  font-family: var(--font-sans);
  font-size: 12px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.report-facts dd { margin: 0; font-size: 15px; color: var(--ink); }
.report-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 18px 0 4px;
}
.report-section { margin-top: 34px; }
.section-title {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--ink-3);
  margin: 0 0 12px;
}
.etable-wrap { overflow-x: auto; }
.etable { width: 100%; border-collapse: collapse; }
.etable th {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line-strong);
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--ink-3);
  text-align: right;
  white-space: nowrap;
}
.etable th:first-child { text-align: left; }
.etable td {
  padding: 10px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  color: var(--ink-2);
  text-align: right;
}
.etable td:first-child { text-align: left; color: var(--ink); }
.review-item { padding: 20px 0; border-bottom: 1px solid var(--line); }
.review-stem {
  margin: 0 0 10px;
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.65;
  font-weight: 500;
  white-space: pre-wrap;
}
.review-answers { display: flex; flex-wrap: wrap; gap: 8px 24px; }
.review-answers p {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0;
  font-size: 12px;
  color: var(--ink-3);
}
.review-answers strong { font-family: var(--font-mono); font-size: 12.5px; color: var(--ink); font-weight: 500; }
.review-explain {
  margin: 10px 0 0;
  font-family: var(--font-serif);
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink-2);
  white-space: pre-wrap;
}
.review-explain.is-empty { color: var(--ink-4); }
.report-actions { display: flex; justify-content: flex-end; margin-top: 32px; }

/* ---------- dialogs ---------- */
.exam-overlay {
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
.exam-dialog {
  width: min(100%, 420px);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-2);
}
.dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 17px 20px 13px;
  border-bottom: 1px solid var(--line);
}
.dialog-title {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 650;
  letter-spacing: .01em;
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px 18px;
  border-top: 1px solid var(--line);
}
.exam-dialog-body { padding: 18px 20px 6px; }
.exam-dialog-body p { margin: 0 0 10px; font-size: 13px; line-height: 1.65; color: var(--ink-2); }
.exam-dialog-stats { color: var(--ink-3); }
.exam-dialog-warn { color: var(--warn); }
.link-btn {
  border: 0;
  background: transparent;
  padding: 0 0 0 4px;
  color: var(--brand);
  font-family: var(--font-sans);
  font-size: 12.5px;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* ---------- mobile sheet ---------- */
.exam-sheet-backdrop {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: flex;
  align-items: flex-end;
  background: rgba(20, 23, 19, .42);
  backdrop-filter: blur(2px);
}
.exam-sheet-drawer {
  width: 100%;
  max-height: 82vh;
  max-height: 82dvh;
  overflow-y: auto;
  padding: 18px 18px calc(18px + env(safe-area-inset-bottom, 0px));
  background: var(--surface);
  border-top: 1px solid var(--line-strong);
  box-shadow: var(--shadow-2);
}
.sheet-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin: 6px 0 14px;
  font-size: 12px;
  color: var(--ink-3);
}
.sheet-legend span { display: inline-flex; align-items: center; gap: 6px; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot.answered { background: var(--surface-3); border: 1px solid var(--line-strong); }
.dot.flagged { background: var(--flag); }
.dot.current { background: transparent; border: 1px solid var(--ink); }
.sheet-drawer-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}

/* ---------- states ---------- */
.exam-loading {
  width: min(100% - 48px, var(--reading-w));
  margin: 48px auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  text-align: center;
}
.exam-loading.skeleton-rows { text-align: left; }
.exam-error { width: min(100% - 48px, var(--reading-w)); margin: 16px auto 0; }
.exam-offline {
  width: min(100% - 48px, 1120px);
  margin: 16px auto 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.exam-conflict {
  width: min(100% - 48px, 1120px);
  margin: 16px auto 0;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.exam-conflict-body { min-width: 0; flex: 1; }
.exam-conflict-body strong { font-family: var(--font-sans); font-size: 12.5px; color: var(--ink); }
.exam-conflict-list { margin: 4px 0 0; padding-left: 16px; font-size: 12px; color: var(--ink-3); }
.exam-conflict-list li { line-height: 1.7; }
.exam-conflict-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.exam-expired {
  width: min(100% - 48px, 1120px);
  margin: 16px auto 0;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.exam-expired-body { min-width: 0; flex: 1; }
.exam-expired-body strong { display: block; font-family: var(--font-sans); font-size: 12.5px; color: var(--ink); }
.exam-expired-body p { margin: 6px 0 0; font-size: 12px; color: var(--ink-3); }
.exam-expired-number { margin-left: 6px; font-family: var(--font-mono); font-size: 12px; color: var(--ink); }
.exam-expired-kept { font-size: 12px; }
.exam-expired-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.empty-title { font-family: var(--font-sans); font-size: 15px; font-weight: 650; }
.empty-desc { font-size: 13px; color: var(--ink-3); margin-bottom: 12px; }

/* ---------- responsive ---------- */
@media (max-width: 1280px) {
  .exam-mode .exam-layout { gap: 40px; }
}
@media (max-width: 1024px) {
  .exam-mode .exam-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
    width: 100%;
    max-width: none;
    padding: 26px 24px 48px;
  }
  .exam-sheet { display: none; }
  .exam-sheet-trigger { display: inline-flex; }
}
@media (max-width: 768px) {
  .exam-mode { --exam-bar-h: 54px; padding-bottom: 70px; }
  .exam-topbar { padding: 0 12px; gap: 8px; }
  .exam-utils,
  .exam-sep,
  .exam-sub { display: none; }
  .exam-topbar .exam-timer { padding: 2px 8px; border: 0; gap: 5px; }
  .exam-topbar .exam-timer strong { font-size: 17px; }
  .exam-mode .exam-layout { width: 100%; padding: 20px 16px 40px; }
  .exam-stem { font-size: 18.5px; }
  .option-content-text { font-size: 16px; }
  .exam-option { padding: 13px 6px; }
  .exam-actionbar { padding: 8px 12px calc(8px + env(safe-area-inset-bottom, 0px)); }
  .exam-action-inner > .btn { flex: 1; justify-content: center; }
  .exam-action-inner .exam-action-spacer { display: none; }
  .exam-action-inner .exam-flag kbd { display: none; }
  .report-head { flex-direction: column; align-items: flex-start; gap: 20px; }
  .report-score { font-size: 52px; }
  .report-facts { gap: 20px; }
  .exam-report { width: 100%; padding: 24px 16px 48px; }
}
@media (max-width: 420px) {
  .exam-back span { display: none; }
  .exam-topbar .exam-timer { padding: 4px 6px; gap: 4px; }
  .exam-topbar .exam-timer .timer-cap { display: none; }
  .exam-stem { font-size: 17.5px; line-height: 1.7; }
  .exam-option { grid-template-columns: 24px minmax(0, 1fr) 16px; }
  .option-content-text { font-size: 15.5px; }
  .exam-submit { padding-left: 10px; padding-right: 10px; }
  .exam-action-inner .nav-label { display: none; }
  .exam-action-inner .btn { flex: 0 0 auto; }
  .exam-sheet-trigger { flex: 1 1 auto !important; }
  .answer-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); }
  .exam-overlay { padding: 10px; }
  .report-facts { flex-wrap: wrap; }
}
@media (pointer: coarse) {
  /* The answer grid pins a 30px height; min-height wins over it. */
  .answer-cell { min-height: 44px; }
}
</style>
