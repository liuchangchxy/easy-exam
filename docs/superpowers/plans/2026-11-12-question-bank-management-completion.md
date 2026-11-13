# Question Bank Management Completion Plan (2026-11-12)

> Status: complete (2026-11-12). This file is the single checklist for this batch.
> Every item is checked against real run evidence recorded below; residuals are named.

## Goal

Complete question-bank management end to end: bank-object CRUD (multi-bank),
soft delete/restore, category management, member roles, chapter tree, tag
management, import history, export, question pagination/sort/search, single
question archive, history-version deletion, audit visibility, and a coherent
UI built on the project's editorial design language.

## Design basis (Open Design)

- Open Design MCP endpoint failed to connect in this session (`CONNECTION_TIMEOUT`).
- Fallback used: local Open Design daemon CLI
  `Open Design.exe .../daemon-cli.mjs`.
- Direction bound for this batch: `editorial-monocle` — serif display, sans body,
  mono metadata only, no shadows/rounded cards, borders + whitespace, one accent.
- Existing app tokens (`frontend/src/style.css`) already follow this direction;
  new UI must reuse them rather than introduce a second visual system.

## Scope checklist

### A. Backend — bank object and multi-bank

- [x] `PATCH /api/v1/banks/{id}` update name/description/category (ADMIN only)
- [x] `DELETE /api/v1/banks/{id}` soft delete (ADMIN, block active exam)
- [x] `POST /api/v1/banks/{id}/restore` restore soft-deleted bank
- [x] `GET /api/v1/banks?deleted=1` recycle-bin listing (ADMIN rows)
- [x] `POST /api/v1/banks/batch` atomic multi-bank archive/restore/delete/set_category
- [x] `GET /api/v1/banks/categories` category aggregation
- [x] `POST /api/v1/banks/categories/rename` rename category across administered banks
- [x] `POST /api/v1/banks/categories/delete` move category banks to default
- [x] `question_count` excludes archived questions; expose archived count

### B. Backend — members, structure, tags

- [x] `PATCH /api/v1/banks/{id}/members/{user_id}` change EDITOR/MEMBER role
- [x] `POST /api/v1/banks/{id}/leave` non-owner leaves a shared bank
- [x] `POST /api/v1/banks/{id}/transfer` ownership transfer (owner only)
- [x] `POST /api/v1/banks/{id}/chapters/reorder` atomic parent/sort update + cycle guard
- [x] Tag rename/merge/delete updates `question_tag_items` links; content reads
  resolve current names while `tags_json` snapshots stay immutable (P2-2)
- [x] Chapter/tag routes return 404/422 instead of 500 on missing input
- [x] `GET /api/v1/banks/{id}/audit` recent bank audit rows (ADMIN)
- [x] `GET /api/v1/banks/{id}/imports` import job history
- [x] `DELETE /api/v1/questions/{id}/versions/{version_id}` safe history deletion
  (never current, never referenced by attempts, never active-exam locked)

### C. Backend — export and questions

- [x] Export uses content list (all bank questions, not personal kill-filtered)
- [x] Export supports `include_archived`
- [x] Content search domain includes question id / code
- [x] FILL type accepted end to end (already in validators; verify)

### D. Frontend — bank list and multi-bank

- [x] Row overflow menu: open, manage, rename, edit description/category, export,
  archive/delete, restore
- [x] Multi-select banks + batch bar (archive/restore/delete/set category)
- [x] Recycled-banks view with restore
- [x] Category manager dialog (rename/delete category, counts)
- [x] List sort (recent / name / question count)
- [x] Keep existing selector contract `.bank-actions-cell button` = 2
- [x] No horizontal overflow at 375px; touch targets >= 42px

### E. Frontend — bank manage page

- [x] Settings tab: editable metadata, export (JSON/CSV/TXT/XLSX), danger zone
  (archive/delete), audit log list
- [x] Structure tab: nested chapter tree, add child, rename, delete, move up/down,
  parent selection; tag manager (create/rename/delete with counts)
- [x] Members tab: role change, remove, leave, transfer ownership
- [x] Imports tab: real import-job history table
- [x] Questions tab: FILL type, sort, client pagination, id/code search,
  single-row archive/restore
- [x] Import entry hidden/disabled for MEMBER
- [x] Export entry reachable from manage page and bank list
- [x] Question edit modal: FILL type, delete non-current history version

### F. Tests and evidence

- [x] Backend: `tests/test_bank_management_completion.py` (permissions, atomicity,
  soft delete/restore, category, roles, reorder/cycle, tag propagation, import
  history, audit, version delete, error mapping, count semantics)
- [x] Frontend: extend `bank_manage.test.js` with new pure helpers (id search,
  pagination, sorting, bank batch payload)
- [x] Frontend component tests for new bank-list menu/batch and manage settings
- [x] Real Chromium E2E: `frontend/tests/bank_management_e2e.test.js`
  (create/rename/category/member role/chapter tree/tag rename/archive/delete/
  restore/export/pagination/375px)
- [x] `python scripts/verify.py fast`
- [x] `python scripts/verify.py ui`
- [x] `python scripts/verify.py full`
- [x] Traceability matrix + DECISIONS updated with real evidence

## Stop criteria

Stop and report complete only when all of the following hold:

1. Every P0/P1 checklist item above is implemented and checked.
2. New backend tests pass; existing backend suite passes except the documented
   environment-only `test_remote_fnos_e2e` skip.
3. Frontend unit/component/localization gates pass.
4. Bank-management Chromium E2E passes against a real backend and real DB.
5. `python scripts/verify.py full` exits 0 (environment skips documented).
6. No hardcoded paths, no test tampering, whitespace clean.
7. Traceability matrix records source, tests and run evidence; every unrun or
   skipped item is named as such.
8. P0/P1 defects zero. P2/P3 residual items are listed, not disguised as done.

## Acceptance procedure

1. Run the new backend test module alone; fix forward.
2. Run `python scripts/verify.py fast`.
3. Run `python scripts/verify.py ui`.
4. Run `node frontend/tests/bank_management_e2e.test.js`.
5. Run `python scripts/verify.py full`.
6. Capture 375px/1280px screenshots from the E2E run for the new surfaces.
7. Update `docs/REQUIREMENTS_TRACEABILITY.md` and `DECISIONS.md`.
8. Report pass/fail/skipped counts, not a narrative-only "all good".

## Explicit non-goals (this batch)

- Server-side pagination for question lists (client-side paging over the already
  loaded content list; server list contract stays backward compatible).
- Cross-bank question deduplication/merge UI.
- Bank duplication (copy whole bank with questions).
- Rewriting historical `tags_json` snapshots during tag rename/merge/delete;
  current tag names are resolved at read time from tag entities instead.

## Completion evidence (2026-11-12)

| Gate | Result |
|---|---|
| `tests/test_bank_management_completion.py` | 15 passed |
| Full backend suite (`verify.py full`, isolated `DATA_DIR`) | 441 tests, 440 passed, 1 environment skip (`FNOS_BASE_URL` unset) |
| AI secret persistence (`tests/test_ai_secret_persistence.py`) | 4 passed |
| Frontend Node contracts (`test:unit`) | 116 passed |
| Frontend Vitest components | 119 passed / 21 files |
| `verify.py fast` | 4/4 steps |
| `verify.py ui` | 3/3 steps |
| `node frontend/tests/bank_management_e2e.test.js` | 1 passed; real backend + Chromium |
| `python scripts/verify.py full` | 10/10 steps passed, exit 0, 264.64s (2026-11-13 rerun) |
| Screenshots | `docs/screenshots/bank-management-20261112/` (1280×4, 375×2) |

Residual items are listed in `docs/REQUIREMENTS_TRACEABILITY.md` §10.4; no P0/P1 defect is known.
