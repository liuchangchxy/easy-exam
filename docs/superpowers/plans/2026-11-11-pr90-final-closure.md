# PR 90 final closure implementation plan

**Goal:** Deliver the requested Editorial Precision fixes on PR 90 and verify the exact deployed revision for manual acceptance.

**Architecture:** Preserve existing APIs and semantic tokens; assign shared files to one owner and integrate contracts centrally. Protect existing data and the untracked research file.

**Spec:** `SPEC.md`; user-provided PR 90 final-closure requirements.

## Task matrix

- [ ] Learning: PracticeViewV1, practice domain, offline queue, practice backend; protect drafts, account isolation, conflict handling, regrade and report; Today and Review flows and kill consistency. Targeted regression tests.
- [ ] Exam: exam feature and blueprint components; runner, answer sheet, submission, report and blueprint configuration. Coordinate shared conflict contract with learning owner. Targeted tests.
- [ ] Content: bank views, question editor, import, bank/question APIs and batch backend. Permission/lock, conflicts, regrade choice, duplicate strategies, mobile, batch atomicity. Targeted tests.
- [ ] Supporting: AI, notes/assets, login/settings/members and their backend services. AI contracts and access; localized errors; note/PDF flows. Avoid files owned by content/learning.
- [ ] UI system: theme preferences, shared styles and theme tests; semantic palette presets and legibility/responsive improvements. Avoid editing owned feature views.
- [ ] Integration: review changes and contracts; traceability/SPEC for confirmed behavior; run targeted checks, `scripts/verify.py fast`, `ui`, `full`, CI, real browser scenarios and exact-HEAD fnOS deployment. Preserve real data; no merge.

## Acceptance

Verify each requested issue with observable outcomes, including persisted results, permissions and conflicts. Record pass, fail, skipped and not run separately. Real browser desktop/mobile, offline recovery and all eight themes at requested widths are required; mocks do not substitute. Deploy only after checks pass, re-read PR HEAD and verify live revision, migration, login and data. Stop for actual unresolved blockers; never mark manual UI acceptance yourself.
