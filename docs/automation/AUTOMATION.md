# EasyExam Automation v1

## Production flow

```text
Frozen Issue
→ Sidecar
→ AntiGravity Developer
→ chang-implementer[bot] PR
→ five required CI gates
→ ChatGPT native Reviewer
→ native Auto-merge
→ exact-SHA APPROVE
→ GitHub squash merge
```

## Repair flow

```text
REQUEST_CHANGES
→ changes-requested
→ Sidecar reclaim
→ AntiGravity same-PR repair
→ synchronize
→ Reviewer re-review after CI
→ exact-SHA APPROVE
→ squash merge
```

The Reviewer waits for the current PR run's required CI checks to reach a terminal result. Native Auto-merge is enabled before approval; review must apply to the current head SHA.

## Coordination labels

Only one coordination state should be active at a time:

- `agent-ready` — a Frozen Spec is ready for Sidecar to claim.
- `agent-working` — Sidecar has claimed the Issue and work is in progress.
- `changes-requested` — a formal `CHANGES_REQUESTED` review requires same-PR repair.
- `infra-blocked` — an infrastructure or environment failure stopped automation.
- `needs-human` — a stop condition or decision requires a person.

`infra-blocked` and `needs-human` are terminal stop states until a maintainer resolves the blocker. On Issue close, cleanup removes active coordination labels (`agent-ready`, `agent-working`, `changes-requested`) and preserves terminal blocker labels.

## Required CI

- Whitespace & Guard Checks
- Backend & Packaging Tests
- Frontend Unit & Build Tests
- Browser E2E Tests
- Mobile Interaction E2E

## Reviewer model

- The production Reviewer uses native pull request events: `opened`, `ready_for_review`, and `synchronize` (commit updates).
- Reviews are bound to the exact current head SHA; stale heads are not reviewed or approved.
- The Reviewer waits in the same run for required CI to reach a terminal result.
- The flow does not use comment-based Reviewer authorization, a comment wake, a Reviewer Wake job, or an `[easyexam-review-ready:<SHA>]` marker.
- Native Auto-merge is enabled before the exact-SHA `APPROVE`; GitHub performs the squash merge.

## Safety invariants

- PR base is `main` and PR author is `chang-implementer[bot]`.
- The linked Issue has the `frozen-spec` label before implementation begins.
- Never review or approve a stale SHA.
- Stop after at most three `REQUEST_CHANGES` rounds.
- Normal flow uses no direct merge and no admin bypass.
- The production loop requires no external paid inference/API, reverse proxy, or session hack.

## Completion cleanup

When an Issue closes, the coordination-label cleanup workflow removes active coordination labels. It preserves `infra-blocked` and `needs-human` when an Issue closes in one of those terminal states.

## Validated evidence

- [Issue #26](https://github.com/liuchangchxy/easy-exam/issues/26) / [PR #27](https://github.com/liuchangchxy/easy-exam/pull/27) — production happy path.
- [#29](https://github.com/liuchangchxy/easy-exam/pull/29) — removal of obsolete Reviewer Wake and marker transport.
- [Issue #30](https://github.com/liuchangchxy/easy-exam/issues/30) / [PR #31](https://github.com/liuchangchxy/easy-exam/pull/31) — post-cleanup happy path.
- [Issue #32](https://github.com/liuchangchxy/easy-exam/issues/32) / [PR #33](https://github.com/liuchangchxy/easy-exam/pull/33) — `REQUEST_CHANGES` and same-PR repair loop; SHA_A `2c9a227d86cf72cb9982c276ab58f1db60515786`, SHA_B `408c49ab189cfe4ed8b039de5e6045c4f032b4c5`, merge `2541c4b3cee23dab70c3d2cb0c3973efccc420f7`.
- [#25](https://github.com/liuchangchxy/easy-exam/pull/25) — native `synchronize` Reviewer POC; closed, not merged.

```text
AUTONOMOUS_PRODUCTION_LOOP_VALIDATED = YES
POST_CLEANUP_SMOKE_VALIDATED = YES
AUTONOMOUS_REPAIR_LOOP_VALIDATED = YES
```

## Current status

EasyExam Automation v1 is production-validated. Ordinary development can use this automation without creating more validation Issues. Revisit the design for a real defect, a new requirement, or a future architecture change.
