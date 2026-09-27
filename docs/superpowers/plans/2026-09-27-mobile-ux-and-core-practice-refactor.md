# Implementation Plan: Mobile UX Space Overhaul & Core Practice Engine Fixes

**Date**: 2026-09-27
**Scope**: Frontend mobile ergonomics, responsive breakpoints, touch gestures, session answers preservation, navigation improvements, question jump sheet, login persistence, and scoring labels.

---

## 1. Objectives & Confirmed Requirements
1. **Space Ergonomics**: Compress mobile top header from 176px to 44px single-line bar, hide desktop hotkey tips, compact bottom action bar with `safe-area-inset-bottom`, and make explanation visible on mobile first fold.
2. **Navigation Fix**: Unanswered questions must have Next / Skip button. Space / Right Arrow must work when unanswered. Last question guides to submit.
3. **Touch Swipe**: Implement horizontal swipe gestures (`>50px`, angle guard `|deltaX| > |deltaY| * 1.5`, left-edge 20px guard for iOS Safari swipe-back).
4. **Login Persistence**: Stop wiping token on transient network errors or offline launches in `authStore.js`; only 401 Unauthorized triggers logout; persist `easyexam_user` in `localStorage`.
5. **Answer History**: Preserve answer, textAnswer, result, and AI panel states across navigation using a session answer map (`sessionAnswers[qid]`), preventing answered questions from being cleared when clicking "上一题".
6. **Question Jump Sheet (答题卡)**: Add responsive question sheet / bottom drawer in both `PracticeViewV1` and `ExamView` with color-coded question pills (unanswered, correct, wrong, weak flag) and next-unanswered shortcut.
7. **Scoring Labels**: Correctly distinguish single-choice/judge wrong answers as "回答错误", reserve "部分得分（漏选）" strictly for multi-choice omissions, and show "回答正确" for correct.

---

## 2. Implementation Tasks

- [x] **Task 1: Unit & Regression Tests for Core Engine Improvements**
  - Added domain functions `formatVerdictTitle`, `findNextUnansweredIndex`, `isSwipeGestureValid` in [exam.js](../../../frontend/src/domain/exam.js).
  - Added 3 suites of unit tests in [exam.test.js](../../../frontend/tests/exam.test.js); 11/11 tests pass.

- [x] **Task 2: Fix Auth Persistence & Mobile Reconnect (`frontend/src/stores/authStore.js`, `frontend/src/views/LoginView.vue`)**
  - Distinguish 401 from transient network/offline errors in `loadCurrentUser()`.
  - Cache user info in `localStorage.getItem('easyexam_user')`.
  - Added cross-tab `storage` event listener for session sync.

- [x] **Task 3: Fix Question Navigation & Answer Preservation (`frontend/src/views/PracticeViewV1.vue`)**
  - Implemented `sessionAnswers` reactive map.
  - Retain answers, text answers, results, and AI panel states when navigating back and forth.
  - Render Next / Skip button even when unanswered (`!result`).
  - Space / ArrowRight / J now skip to next question when unanswered.

- [x] **Task 4: Add Mobile & Desktop Question Palette / Bottom Sheet (`frontend/src/views/PracticeViewV1.vue`, `frontend/src/features/exam/ExamView.vue`)**
  - Added responsive question palette drawer (`.sheet-modal-drawer`) with color coding (⚪未答、🟢正确、🔴错误、🟡漏选).
  - Quick jump to any question index.
  - "⏭ 跳至下一道未做题" shortcut button.
  - Unanswered confirmation dialog on completion.

- [x] **Task 5: Add Touch Swipe Gestures with Edge Protection (`frontend/src/views/PracticeViewV1.vue`, `frontend/src/features/exam/ExamView.vue`)**
  - Implemented `handleTouchStart` and `handleTouchEnd`.
  - Angle guard (`|deltaX| > |deltaY| * 1.5`) and iOS Safari left-edge 25px guard.

- [x] **Task 6: Precision Scoring Verdict Text (`frontend/src/views/PracticeViewV1.vue`, `frontend/src/domain/exam.js`)**
  - Fixed single-choice/judge wrong answers to display "回答错误 ❌".
  - Multi partial display "部分得分（漏选） ⚠️".
  - Correct answers display "🎉 回答正确！".

- [x] **Task 7: Mobile CSS & Space Ergonomics (`frontend/src/style.css`, `frontend/src/views/PracticeViewV1.vue`, `frontend/src/features/exam/ExamView.vue`)**
  - Compact 44px top navbar on `@media (max-width: 767px)`.
  - Collapsed secondary buttons into "⋯" dropdown.
  - Hidden `.practice-side-guide`, `.practice-tips`, and `.hotkey-helper-bar` on mobile.
  - Compact ergonomic action bar with `env(safe-area-inset-bottom)`.
  - Header height reduced from 175.8px to 44px; question + options + explanation fully visible on first fold.

- [x] **Task 8: Verification & E2E Validation**
  - Frontend unit tests: `npm --prefix frontend test` -> 11/11 passed.
  - Mobile screenshot capture: `node frontend/tests/capture_mobile.mjs` -> metrics verified.
  - Full mobile interaction suite: `node frontend/tests/mobile_interaction_suite.mjs` -> 11/11 E2E browser checks passed.
  - Frontend build: `npm --prefix frontend run build` -> 0 errors.
