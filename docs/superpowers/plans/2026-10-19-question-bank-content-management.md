# Question Bank Content Management v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a dedicated question bank content management page (`/banks/:bankId`) allowing bank members to browse, search, and filter all bank questions (including killed questions), and allowing administrators/editors to edit questions version-by-version with active exam safety guards.

**Architecture:** Add a decoupled content read API `GET /api/v1/banks/{bank_id}/content/questions` in the FastAPI backend that returns the full question set for bank members without applying personal study/kill filters; harden `QuestionRepository.create_next_version` with active exam protection; introduce pure frontend filtering and authorization utilities in `frontend/src/domain/bankManage.js`; implement `BankManageView.vue` and `QuestionEditModal.vue` with bilingual and responsive (375px/768px/1280px) support; integrate entry navigation from `HomeView.vue`.

**Tech Stack:** Python 3.14 / FastAPI / SQLite3 / Vue 3 / Vue Router / Vanilla Node Test Runner (`node --test`) / Playwright.

**Spec:** User request `EASYEXAM_QUESTION_BANK_CONTENT_MANAGEMENT_V1_FROZEN` and root `AGENTS.md`.

## Global Constraints

- Database: No migrations allowed; reuse existing tables `questions`, `question_versions`, `bank_question_items`, `chapters`, `knowledge_tags`, `question_bank_members`, and `practice_sessions`.
- API design: Reuse `PUT /questions/{question_id}` for editing; provide a lightweight content read API `GET /api/v1/banks/{bank_id}/content/questions`.
- Authority: Backend is the ultimate authority for member read-only enforcement and active exam answer masking.
- Non-regression: No modifications to mistake records, FSRS ratings, kill states, or historical answer regrading (`regrade_history = false`).
- Active Exam Safety: If a user has an active exam for the bank, the manage view must enter read-only mode, display an active exam banner, mask answers/explanations, and backend must reject editing questions in active exams.
- Localization: All user-facing strings must exist in both `zh-CN` and `en-US` dictionaries with 100% key parity, no raw template text.
- Responsive: Zero horizontal scroll on 375px mobile, 768px tablet, and 1280px desktop.

## Review Focus

1. **Killed question retention:** When a user kills a question, `GET /api/v1/banks/{bank_id}/content/questions` must still include the question (unlike `list_for_bank`).
2. **Active exam confidentiality and tamper prevention:** When an active EXAM session exists, question answers must be masked and backend `create_next_version` must reject edits to avoid blanking real answers.
3. **MEMBER role immutability:** `MEMBER` users see no edit controls, and calling `PUT /questions/{question_id}` directly returns HTTP 403.
4. **Version increment integrity:** Editing a question with `base_version_number` creates version `N+1`, preserves version history, and does not regrade user study history.
5. **Mobile 375px ergonomics:** Filter controls wrap cleanly, question items stack vertically, touch targets are >= 42px, and modal inputs remain accessible without horizontal clipping.

---

### Task 1: Backend Content Read API and Active Exam Protection

**Files:**
- Modify: `backend/app/infrastructure/db/repositories/question_repository.py:236-320`
- Modify: `backend/app/api/routes/banks.py:65-80`
- Create: `tests/test_question_bank_content_management.py`

**Interfaces:**
- Consumes: `QuestionRepository._get_active_exam_question_ids(conn, user_id)`, `bank_question_items`, `question_bank_members`
- Produces:
  - `QuestionRepository.list_content_for_bank(bank_id: str, user_id: str) -> List[dict]`
  - `GET /api/v1/banks/{bank_id}/content/questions` returning `List[dict]`
  - Guard in `QuestionRepository.create_next_version`: raises `PermissionError` if question is in user's active exam

- [x] **Step 1: Write failing backend tests**

Create `tests/test_question_bank_content_management.py` testing:
1. Member can read content questions list from `GET /api/v1/banks/{bank_id}/content/questions`.
2. Non-member receives 403 or 404.
3. Killed questions remain visible in `content/questions` while omitted in regular `GET /banks/{bank_id}/questions`.
4. Content questions read does not alter kill, mistake, or FSRS tables.
5. ADMIN/EDITOR can update question via `PUT /questions/{id}` generating version 2.
6. MEMBER cannot update question via `PUT /questions/{id}` (returns 403).
7. When user has an active EXAM session containing a question, `GET /api/v1/banks/{bank_id}/content/questions` masks the answer/explanation, and `PUT /questions/{id}` raises 403.

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_question_bank_content_management.py -v`
Expected: FAIL with 404 on `/api/v1/banks/{bank_id}/content/questions`.

- [x] **Step 3: Implement minimal backend changes**

1. In `backend/app/infrastructure/db/repositories/question_repository.py`:
   - Implement `list_content_for_bank(bank_id: str, user_id: str) -> List[dict]`:
     Verify membership, fetch all bank questions with latest version numbers without joining `kill_records`, mask answers/explanations if question ID in `_get_active_exam_question_ids`.
   - In `create_next_version`:
     Check if `question_id in self._get_active_exam_question_ids(conn, user_id)`: raise `PermissionError("cannot edit question with active exam session")`.
2. In `backend/app/api/routes/banks.py`:
   - Add endpoint `@router.get("/{bank_id}/content/questions")` checking user bank access and calling `list_content_for_bank`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_question_bank_content_management.py -v`
Expected: PASS all 7 tests.

- [x] **Step 5: Commit Task 1**

```bash
git add backend/app/infrastructure/db/repositories/question_repository.py backend/app/api/routes/banks.py tests/test_question_bank_content_management.py
git commit -m "feat(backend): add bank content questions API with active exam protection"
```

---

### Task 2: Frontend Domain Logic for Filtering and Permissions

**Files:**
- Create: `frontend/src/domain/bankManage.js`
- Create: `frontend/tests/bank_manage.test.js`
- Modify: `frontend/package.json:10-12`

**Interfaces:**
- Produces:
  - `filterBankQuestions(questions, filters)`
  - `canEditBankContent(role)`
  - `canEditQuestionInBank({ role, hasActiveExam, isQuestionInExam })`
  - `createEmptyBankFilters()`
  - `isFilterActive(filters)`

- [x] **Step 1: Write failing frontend unit tests**

Create `frontend/tests/bank_manage.test.js` exercising:
1. `filterBankQuestions` with keyword matching stem (case-insensitive).
2. `filterBankQuestions` with keyword matching tag item in `tags`.
3. `filterBankQuestions` with question type (e.g. `SINGLE`, `MULTI`).
4. `filterBankQuestions` with difficulty rating (1~5).
5. `filterBankQuestions` with tag filter.
6. `filterBankQuestions` with chapter ID filter.
7. `filterBankQuestions` with combined multi-criteria filters.
8. `filterBankQuestions` with empty/cleared filters returning full question array.
9. `canEditBankContent` returning `true` for `ADMIN` and `EDITOR`, `false` for `MEMBER` or unknown.
10. `canEditQuestionInBank` returning `false` when `hasActiveExam` is true even if role is `ADMIN`.

- [x] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/bank_manage.test.js`
Expected: FAIL ("Cannot find module '../src/domain/bankManage.js'").

- [x] **Step 3: Implement minimal frontend domain logic**

Implement `frontend/src/domain/bankManage.js` with pure functions:
- `createEmptyBankFilters()`: `{ keyword: '', type: '', difficulty: '', tag: '', chapterId: '' }`
- `isFilterActive(filters)`: checks if any filter property is non-empty.
- `canEditBankContent(role)`: `['ADMIN', 'EDITOR'].includes(String(role).toUpperCase())`
- `canEditQuestionInBank({ role, hasActiveExam, isQuestionInExam })`: `canEditBankContent(role) && !hasActiveExam && !isQuestionInExam`
- `filterBankQuestions(questions, filters)`: filters questions by keyword, type, difficulty, tag, and chapter.
Update `frontend/package.json` `scripts.test` to include `tests/bank_manage.test.js`.

- [x] **Step 4: Run test to verify it passes**

Run: `npm test --prefix frontend`
Expected: PASS (all 51+ unit tests pass).

- [x] **Step 5: Commit Task 2**

```bash
git add frontend/src/domain/bankManage.js frontend/tests/bank_manage.test.js frontend/package.json
git commit -m "feat(frontend): add bank content management domain filters and role gates"
```

---

### Task 3: API Client and Bilingual Locale Catalog Updates

**Files:**
- Modify: `frontend/src/api/banks.js`
- Modify: `frontend/src/locales/zh-CN.js` and `frontend/src/locales/zh-CN.json`
- Modify: `frontend/src/locales/en-US.js` and `frontend/src/locales/en-US.json`

**Interfaces:**
- Produces:
  - `getBank(token, bankId)`
  - `listBankQuestionsContent(token, bankId)`
  - `listChapters(token, bankId)`
  - `listTags(token, bankId)`
  - Locale keys under `bank_manage.*` and `home.manage_questions`

- [x] **Step 1: Write failing test in locale.test.js**

Run: `npm run check:localization --prefix frontend` to establish baseline pass.

- [x] **Step 2: Add API client functions in `frontend/src/api/banks.js`**

Add:
```javascript
export const getBank = (token, bankId) => request(`/banks/${bankId}`, {
  headers: authHeaders(token)
})

export const listBankQuestionsContent = (token, bankId) => request(`/banks/${bankId}/content/questions`, {
  headers: authHeaders(token)
})

export const listChapters = (token, bankId) => request(`/banks/${bankId}/chapters`, {
  headers: authHeaders(token)
})

export const listTags = (token, bankId) => request(`/banks/${bankId}/tags`, {
  headers: authHeaders(token)
})
```

- [x] **Step 3: Update bilingual dictionaries**

Add matching keys in `zh-CN.js`, `zh-CN.json`, `en-US.js`, `en-US.json`:
- `home.manage_questions`: "管理题目" / "Manage Questions"
- `bank_manage.back_home`: "返回首页" / "Back to Home"
- `bank_manage.title`: "题库题目管理" / "Question Management"
- `bank_manage.role_admin`: "管理员" / "Admin"
- `bank_manage.role_editor`: "编辑者" / "Editor"
- `bank_manage.role_member`: "普通成员(只读)" / "Member (Read-only)"
- `bank_manage.active_exam_warning`: "当前题库存在进行中的模考，题目答案与解析已被隔离保护，管理页处于只读状态。" / "An active mock exam is currently running for this bank. Answers and explanations are protected and editing is disabled."
- `bank_manage.search_placeholder`: "按题干或标签搜索..." / "Search by stem or tag..."
- `bank_manage.filter_type`: "全部题型" / "All Types"
- `bank_manage.filter_difficulty`: "全部难度" / "All Difficulties"
- `bank_manage.filter_tag`: "全部标签" / "All Tags"
- `bank_manage.filter_chapter`: "全部章节" / "All Chapters"
- `bank_manage.reset_filters`: "重置筛选" / "Reset Filters"
- `bank_manage.filtered_count`: "已筛选 {count} / 共 {total} 题" / "Filtered {count} of {total} questions"
- `bank_manage.no_matching_questions`: "未找到匹配题目" / "No matching questions found"
- `bank_manage.edit_question`: "编辑题目" / "Edit Question"
- `bank_manage.version_badge`: "v{ver}" / "v{ver}"
- `bank_manage.save_success`: "题目已成功保存为新版本" / "Question saved as new version successfully"
- `bank_manage.save_error`: "保存失败: {error}" / "Failed to save: {error}"

- [x] **Step 4: Run localization verification gate**

Run: `npm run check:localization --prefix frontend` and `node --test frontend/tests/locale.test.js`
Expected: PASS (100% dictionary parity, identical JSON catalogs, no untranslated keys).

- [x] **Step 5: Commit Task 3**

```bash
git add frontend/src/api/banks.js frontend/src/locales/
git commit -m "feat(frontend): add bank content APIs and bilingual localization strings"
```

---

### Task 4: BankManageView and QuestionEditModal UI Components

**Files:**
- Create: `frontend/src/components/QuestionEditModal.vue`
- Create: `frontend/src/views/BankManageView.vue`
- Modify: `frontend/src/router/index.js:14-55`
- Modify: `frontend/src/views/HomeView.vue:245-256`

**Interfaces:**
- `QuestionEditModal.vue`:
  - Props: `show: Boolean`, `question: Object`, `chapters: Array`, `tags: Array`, `readOnly: Boolean`
  - Emits: `close`, `saved(updatedQuestion)`
- `BankManageView.vue`:
  - Route: `/banks/:bankId`
  - Props: `token: String`, `user: Object`
  - Calls `getBank`, `listBankQuestionsContent`, `listChapters`, `listActiveSessions(token, 'EXAM')`

- [x] **Step 1: Implement QuestionEditModal.vue**

Create `frontend/src/components/QuestionEditModal.vue`:
- Form inputs:
  - Stem (textarea)
  - Type (select: SINGLE, MULTI, JUDGE, ESSAY)
  - Difficulty (select: 1 to 5)
  - Chapter (select from bank chapters or None)
  - Answer (input for SINGLE/MULTI/JUDGE, textarea for ESSAY)
  - Options list (for SINGLE/MULTI/JUDGE): dynamic add/remove, key input and content input
  - Explanation (textarea)
  - Tags (input with comma/space split)
- Save handler calls `updateQuestion(token, question.id, payload)`:
  - `payload = { stem, type, options, answer, explanation, difficulty, tags, chapter_id, base_version_number: question.version_number, regrade_history: false }`
- Read-only guard: If `readOnly` is true, all inputs are disabled and save button is hidden.
- Close on Escape or click backdrop.

- [x] **Step 2: Implement BankManageView.vue**

Create `frontend/src/views/BankManageView.vue`:
- Top Header:
  - Back button (routes to `/`)
  - Bank Name & Category
  - Question count badge
  - User role pill (Admin, Editor, Member)
- Active Exam Alert Banner:
  - If user has active EXAM session for this bank: show warning banner, lock edit actions.
- Toolbar:
  - Keyword input (debounced or reactive model)
  - Type filter select
  - Difficulty filter select
  - Tag filter select
  - Chapter filter select
  - Clear/Reset filters button
  - Result count display (`{count} / {total}`)
- Content List:
  - Desktop: Clean, dense list row showing Stem summary, Type badge, Difficulty stars/number, Chapter pill, Tags pills, Version badge, Edit button (for Admin/Editor when not active exam).
  - Mobile (<768px): Card-based responsive view with touch targets >= 42px.
- Empty State: When no questions match filter, display "未找到匹配题目" and reset button.
- Integrate `QuestionEditModal`: when question saved, update item in reactive list, increment version number, notify user with toast/banner.

- [x] **Step 3: Update router and HomeView navigation**

1. In `frontend/src/router/index.js`:
   Register route:
   ```javascript
   {
     path: 'banks/:bankId',
     name: 'bank-manage',
     component: () => import('../views/BankManageView.vue'),
     meta: { title: '题库管理' }
   }
   ```
2. In `frontend/src/views/HomeView.vue`:
   Add "管理题目" button in bank card actions:
   ```html
   <button type="button" class="btn-util-link btn-manage-bank" @click="router.push(`/banks/${bank.id}`)">
     <LinearIcon name="list" size="12" /> {{ t('home.manage_questions') }}
   </button>
   ```

- [x] **Step 4: Verify template localization and build**

Run: `npm run check:localization --prefix frontend`
Run: `npm run build --prefix frontend`
Expected: PASS with 0 build errors and 0 localization warnings.

- [x] **Step 5: Commit Task 4**

```bash
git add frontend/src/components/QuestionEditModal.vue frontend/src/views/BankManageView.vue frontend/src/router/index.js frontend/src/views/HomeView.vue
git commit -m "feat(frontend): implement BankManageView and QuestionEditModal with responsive layout"
```

---

### Task 5: Browser E2E and Mobile Verification + Visual Evidence

**Files:**
- Create: `frontend/tests/bank_manage_e2e.test.js`
- Create: `scripts/capture_bank_manage_visuals.mjs`
- Modify: `docs/REQUIREMENTS_TRACEABILITY.md`

**Interfaces:**
- Produces:
  - Browser E2E test verifying end-to-end flow: Login -> Bank list -> Enter Bank Manage -> Filter -> Edit question -> Version increment -> Refresh -> Verify persistence -> Killed question retention -> Active exam lock.
  - Visual artifacts in `tests/visual_smoke/` at 1280px and 375px.

- [x] **Step 1: Write Playwright E2E test**

Create `frontend/tests/bank_manage_e2e.test.js`:
1. Launches test server and browser.
2. Creates a user, creates a bank, adds 3 questions with different types and chapters.
3. Kills question 1.
4. Navigates to `/banks/:bankId`.
5. Verifies question 1 is still present in content list (acceptance criterion 3).
6. Tests search filter: typing keyword filters questions down.
7. Tests multi-filter: filtering by type and difficulty works, reset button restores all.
8. Opens edit modal for question 2, modifies stem and answer, saves.
9. Verifies version increments to `v2` without page reload.
10. Reloads page, verifies new stem and `v2` persist.
11. Verifies member account sees no edit buttons.
12. Starts an active exam for the bank, navigates back to `/banks/:bankId`, verifies active exam banner is shown, editing is disabled, and answers are masked.

- [x] **Step 2: Run E2E test**

Run: `node frontend/tests/bank_manage_e2e.test.js`
Expected: PASS.

- [x] **Step 3: Create visual capture script and collect screenshots**

Create `scripts/capture_bank_manage_visuals.mjs` capturing:
1. `1280px` full bank manage page
2. `1280px` search + multi-filter state
3. `1280px` edit question modal
4. `375px` mobile list
5. `375px` mobile edit state

Run script and inspect output images.

- [x] **Step 4: Update REQUIREMENTS_TRACEABILITY.md**

Update `docs/REQUIREMENTS_TRACEABILITY.md` mapping:
- `BANK-CONTENT-MGMT-001`: Direct bank management entry `/banks/:bankId`.
- `BANK-CONTENT-MGMT-002`: Unfiltered content list preserving killed questions.
- `BANK-CONTENT-MGMT-003`: Multi-criteria search and filter.
- `BANK-CONTENT-MGMT-004`: Versioned question editing without history regrade.
- `BANK-CONTENT-MGMT-005`: Active exam answer masking and edit prevention.
- `BANK-CONTENT-MGMT-006`: Mobile 375px responsive layout and touch targets.

- [x] **Step 5: Run full regression suite**

1. `pytest tests/`
2. `npm test --prefix frontend`
3. `npm run check:localization --prefix frontend`
4. `npm run build --prefix frontend`
5. `git diff --check`

- [x] **Step 6: Commit Task 5**

```bash
git add frontend/tests/bank_manage_e2e.test.js scripts/capture_bank_manage_visuals.mjs docs/REQUIREMENTS_TRACEABILITY.md
git commit -m "test(e2e): add bank manage browser tests, visual captures, and traceability update"
```
