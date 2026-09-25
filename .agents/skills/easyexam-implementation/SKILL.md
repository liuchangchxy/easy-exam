---
name: easyexam-implementation
description: Implement a scoped EasyExam code plan in this repository while preserving confirmed SPEC requirements, using audited open-source code responsibly, TDD, and honest test reporting.
---

# EasyExam implementation workflow

Use this skill for code implementation tasks in this repository.

1. Read root `AGENTS.md`, `SPEC.md`, `TESTING.md`, `docs/ANTIGRAVITY_WORKFLOW.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, `docs/research/OSS_REUSE_AUDIT.md`, and the one plan the user named.
2. Inspect `git status` and relevant diffs. Preserve all pre-existing changes. Never reset, clean, restore, or expand into unrelated files.
3. Confirm the plan is still valid against current source paths and dependencies. If the task needs a new product decision, license decision, external service credential, or undocumented behavior, stop and ask the user.
4. For each plan task: add a regression test, run it and observe RED, implement, run it GREEN, then inspect sibling paths for the same defect. Do not edit old expected results to get a pass.
5. Before copying/adapting external source, inspect exact pinned source and license; prefer a suitable existing implementation over rewriting it. Preserve notices and update the OSS audit with exact file mappings. Treat GPL/AGPL, missing-license, and ambiguous files as non-copyable absent explicit approval.
6. At the end run the plan's acceptance commands. For stage completion run backend unittest, frontend unit, build, real browser E2E, and `git diff --check`; list actual pass/fail/skipped counts and don't claim tests not run.
7. Update traceability and plan checkboxes from observed evidence, not intention. Report changes, source reuse status, tests, skipped cases, remaining gaps, and any blocked decision.

See `docs/ANTIGRAVITY_WORKFLOW.md` for the complete sequence and report format.
