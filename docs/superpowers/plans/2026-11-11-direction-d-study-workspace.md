# Direction D Study Workspace implementation plan

**Goal:** Apply the approved Direction D visual and layout delta to PR #90 while preserving its production behavior and four theme families.

**Source:** Open Design `directions/d/HANDOFF.md`, `index.html`, `skin.css`, `dir.js`, and sibling `shared/`; current production PR #90 supplies behavior. Prototype files remain outside the repository.

**Baseline:** PR #90 `ceac0c6ccf17a475a38b281962406beeb265bf0a`; checkpoint 48. Local and remote baseline trees match.

## Ownership and tasks

- [ ] Shell owner: global `style.css`, AppLayout, AppSidebar, MobileNav, HomeView and BanksView; HANDOFF Steps 1–5 and 10. Own shared tokens, surface widths and breakpoint ordering. Preserve live values and actions; no fabricated statistics.
- [ ] Learning owner: PracticeViewV1, ReviewView and dedicated report components; Step 6, focused shell, feedback and responsive answer sheet. Preserve all offline, conflict, scoring and FSRS logic.
- [ ] Exam owner: ExamCenterView, exam feature components and blueprint presentation; Step 7, runner, answer sheet and report. Preserve timing, submission, conflict and timeout semantics.
- [ ] Content owner: BankManageView, BankDetailView, ImportView, NotesView, SettingsView and their dedicated components; Steps 8–9, responsive layouts, density and existing palette controls. Preserve permissions and transactions.
- [ ] Integration: review ownership boundaries, merge responsive rules, assess 14 pages against running prototype at requested widths, verify all eight palettes on representative pages and run functional regression. Never modify `themePreference.js`, router, stores, i18n, API or backend for this visual delta.

## Acceptance

Work surface `calc(100% - 40px)` with 1120px default / 1320px maximum on dense or manage/import/notes; 1440px gives 1120px default and 1164px dense. Apply HANDOFF breakpoints in order (practice collapses at ≤1100, icon-only 236px spine at 769–1024, context columns below at ≤900, mobile shell at ≤768). Preserve full functionality, theme mode/palette and user data. Run `scripts/verify.py fast`, `ui`, `full`, CI and real-browser interaction/comparison. Deploy only the exact current PR HEAD after passing validation, verify migration and preserved data, do not merge or declare user UI acceptance.
