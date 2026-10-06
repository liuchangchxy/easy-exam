# Cleanup: obsolete Reviewer marker transport and terminal labels

## Scope and evidence

At base `e905c184ab7f2a4cefdb00e735da18168f2654b9`, `ci.yml` contains five required CI jobs plus a sixth non-required `reviewer-wake` job that posts `[easyexam-review-ready:<SHA>]` after all five jobs finish. Repository search found no consumer for the marker, no Sidecar/dispatcher implementation, and no issue-close cleanup workflow. GitHub reports PR #27 MERGED and `main` at its merge commit; Issue #26 is CLOSED with `agent-working` still present. PR #25 is CLOSED / NOT MERGED.

## File map

- `.github/workflows/ci.yml`: preserve all five CI jobs and PR triggers; remove only the legacy marker job.
- `.github/workflows/coordination-label-cleanup.yml`: handle GitHub's `issues.closed` event, re-read current issue labels, preserve terminal blocker labels, and remove only active coordination labels after successful completion.
- `.github/scripts/cleanup-coordination-labels.js`: implement the small, directly testable label decision.
- `tests/test_coordination_workflows.py` and `tests/coordination-label-cleanup.test.js`: parse workflow YAML and exercise success/blocked label behavior.
- `docs/superpowers/plans/2026-10-06-native-reviewer-transport-cleanup.md`: this batch plan and acceptance checklist.

## Implementation sequence

1. Add regression tests for both workflows: exactly the five required CI job IDs remain in `ci.yml`; the marker transport is absent; the cleanup workflow only handles `issues.closed`, has `issues: write`, preserves `infra-blocked` and `needs-human`, and targets `agent-ready`, `agent-working`, and `changes-requested` only.
2. Run the focused tests and confirm they fail against the current source.
3. Remove the `reviewer-wake` job from `ci.yml` without changing the `pull_request` trigger or any of its five CI jobs.
4. Add the small issue-close workflow. On a closed issue, re-read current labels; if either terminal blocker label exists, leave all labels alone. Otherwise remove only the active coordination labels that are present. Do not add polling, a service, a secret, or a new orchestration layer.
5. Run focused tests, YAML parse checks, repository guard checks, and all existing workflow/dispatcher-related tests (the repository currently contains no dispatcher implementation or workflow-specific test suite). Run affected tests as required by repository policy.
6. Review the final diff against all constraints: no Reviewer automation, Ruleset, branch protection, App permissions, Frozen Spec model, repair policy, dispatch architecture, native Auto-merge, review identity, or business code changes.
7. Create a control-plane PR through the approved app-mediated write path; do not enable auto-merge or merge it. Do not delete `master` or `poc/native-reviewer-event` until a later, explicitly authorized post-merge verification can establish the required conditions.

## Acceptance checklist

- [ ] PR #27 merged and main ancestry verified.
- [ ] Exactly five required CI jobs retained.
- [ ] Legacy Reviewer Wake / marker producer removed; native Reviewer uses PR opened/synchronize and no marker dependency.
- [ ] Closed successful issues lose active coordination labels.
- [ ] Issues closed with `infra-blocked` or `needs-human` retain their existing labels unchanged.
- [ ] No polling, service, API key, or additional orchestration layer added.
- [ ] Relevant tests and guard checks report pass/fail/skipped separately.
- [ ] Control-plane PR created, not auto-merged and not merged.
- [ ] Temporary branches remain because this task stops before merging; remove them only after a later successful merge and post-merge verification.
