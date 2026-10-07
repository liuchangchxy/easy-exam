#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyExam Dispatcher Sidecar for Antigravity 2.0
Polls GitHub for frozen EasyExam agent tasks and dispatches Antigravity implementers.
"""

import ctypes
from ctypes import wintypes
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("easyexam-dispatcher")

# Environment configurations
EASYEXAM_REPO = os.environ.get("EASYEXAM_REPO", "liuchangchxy/easy-exam")
EASYEXAM_REPO_PATH = os.environ.get("EASYEXAM_REPO_PATH", str(Path(__file__).resolve().parents[2]))
EASYEXAM_POLL_SECONDS = int(os.environ.get("EASYEXAM_POLL_SECONDS", "10"))
EASYEXAM_DRY_RUN = os.environ.get("EASYEXAM_DRY_RUN", "0") in ("1", "true", "True")
EASYEXAM_RUN_ONCE = os.environ.get("EASYEXAM_RUN_ONCE", "0") in ("1", "true", "True")
GITHUB_APP_ID = os.environ.get("EASYEXAM_GITHUB_APP_ID", "5187459")
GITHUB_APP_HELPER = Path(os.environ.get(
    "EASYEXAM_GITHUB_APP_HELPER",
    str(Path.home() / ".gemini" / "credentials" / "github-app" / "github_app_credentials.py"),
))
APP_GH_EXECUTOR = Path(os.environ.get(
    "EASYEXAM_APP_GH_EXECUTOR",
    str(Path.home() / ".gemini" / "credentials" / "github-app" / "app_gh.py"),
))
APP_GIT_PUSH_EXECUTOR = Path(os.environ.get(
    "EASYEXAM_APP_GIT_PUSH_EXECUTOR",
    str(Path.home() / ".gemini" / "credentials" / "github-app" / "app_git_push.py"),
))
GITHUB_APP_EXPECTED_PERMISSIONS = {
    "contents": "write", "pull_requests": "write", "issues": "write",
    "metadata": "read", "actions": "read", "checks": "read",
}
GITHUB_APP_SLUG = os.environ.get("EASYEXAM_GITHUB_APP_SLUG", "chang-implementer")
DISPATCHER_VERSION = "2026-10-07.01-closure-v1"
DISPATCH_AUDIT_PATH = Path(
    os.environ.get(
        "EASYEXAM_DISPATCH_AUDIT_PATH",
        str(Path.home() / ".gemini" / "config" / "sidecars" / "easyexam-dispatcher" / "dispatch_audit.jsonl"),
    )
)
LEDGER_DB_PATH = Path(
    os.environ.get(
        "EASYEXAM_LEDGER_DB_PATH",
        str(Path.home() / ".gemini" / "config" / "sidecars" / "easyexam-dispatcher" / "execution_ledger.db"),
    )
)

# Unified repair budget frozen by Spec
MAX_AUTOMATED_REPAIRS = 3

# Watchdog deadlines in seconds
DEFAULT_LEASE_TTL_SECONDS = 300.0
LAUNCH_CONFIRMATION_DEADLINE_SECONDS = 120.0
IMPLEMENTER_DEADLINE_SECONDS = 1800.0
CI_TERMINALIZATION_DEADLINE_SECONDS = 1800.0
REVIEWER_COMPLETION_DEADLINE_SECONDS = 1800.0
AUTO_MERGE_DEADLINE_SECONDS = 600.0

COORDINATION_LABELS = {
    "agent-ready",
    "agent-working",
    "changes-requested",
    "infra-blocked",
    "needs-human",
}

CLAIM_BACKOFF_MAP: dict[int, dict] = {}

# Timeouts in seconds
GITHUB_TIMEOUT_SECONDS = 30
AGENTAPI_TIMEOUT_SECONDS = 60

ERROR_ALREADY_EXISTS = 183


class RecoverySpec:
    """Explicit, trusted repo-external specification for a recovery task."""

    def __init__(
        self,
        issue_number: int,
        preserved_sha: str,
        recovery_branch: str,
        allowed_changed_files: list[str],
        allow_reimplementation: bool = False,
        allow_new_implementation_commit: bool = False,
        push_executor: str = "app-git-push",
        github_write_executor: str = "app-gh",
    ):
        self.issue_number = int(issue_number)
        self.preserved_sha = str(preserved_sha).strip()
        self.recovery_branch = str(recovery_branch).strip()
        self.allowed_changed_files = list(allowed_changed_files)
        self.allow_reimplementation = bool(allow_reimplementation)
        self.allow_new_implementation_commit = bool(allow_new_implementation_commit)
        self.push_executor = str(push_executor).strip()
        self.github_write_executor = str(github_write_executor).strip()


TRUSTED_RECOVERY_JOBS: dict[int, RecoverySpec] = {
    4: RecoverySpec(
        issue_number=4,
        preserved_sha="4428ef14bffd0bf94fc28bff508e7be5ec2a30f0",
        recovery_branch="agent/issue-4-self-contained-mobile-e2e-bot",
        allowed_changed_files=[
            "frontend/tests/mobile_interaction_suite.mjs",
            "frontend/tests/fixtures/mobile_interaction_questions.md",
        ],
        allow_reimplementation=False,
        allow_new_implementation_commit=False,
        push_executor="app-git-push",
        github_write_executor="app-gh",
    )
}


def get_recovery_spec(issue_number):
    """
    Retrieve trusted repo-external recovery specification for an issue.
    Not controllable by caller environment or repo files.
    """
    try:
        num = int(issue_number)
    except (TypeError, ValueError):
        return None
    return TRUSTED_RECOVERY_JOBS.get(num)


def get_dispatch_mode(issue_number):
    """Return 'recovery' if issue has a trusted recovery spec, else 'normal'."""
    return "recovery" if get_recovery_spec(issue_number) is not None else "normal"


def is_valid_canonical_pr_author(rest_pull_request):
    """Validate the PR author using canonical GitHub REST pull_request.user fields."""
    user = (rest_pull_request or {}).get("user") or {}
    return (
        user.get("login") == "chang-implementer[bot]"
        and user.get("type") == "Bot"
    )


def check_pr_canonical_author_runtime(repo=EASYEXAM_REPO, pr_number=15):
    """
    Read-only check of canonical REST author for a PR.
    Calls GET /repos/{repo}/pulls/{pr_number} and validates with is_valid_canonical_pr_author.
    """
    gh_bin = shutil.which("gh") or "gh"
    cmd = [gh_bin, "api", f"repos/{repo}/pulls/{pr_number}"]
    code, stdout, stderr, timeout = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
    if code != 0 or timeout or not stdout.strip():
        logger.warning(f"Could not check PR #{pr_number} runtime canonical author")
        return {"checked": False, "login": None, "type": None, "valid": False}
    try:
        data = json.loads(stdout)
        user = data.get("user") or {}
        login = user.get("login")
        user_type = user.get("type")
        valid = is_valid_canonical_pr_author(data)
        return {"checked": True, "login": login, "type": user_type, "valid": valid}
    except Exception as exc:
        logger.warning(f"Failed to parse PR #{pr_number} REST response: {exc}")
        return {"checked": False, "login": None, "type": None, "valid": False}


# ============================================================================
# Automation Closure v1 Engines (Durable Ledger, Ownership, Fencing, Repair)
# ============================================================================

def compute_repair_key(repo: str, pr_number: int, head_sha: str) -> str:
    """
    Unified repair idempotency key matching Frozen Spec Section 11:
    repair:<repo>:pr:<pr_number>:head:<failed_or_rejected_head_sha>
    """
    sha = (head_sha or "").strip()
    return f"repair:{repo}:pr:{pr_number}:head:{sha}"


def verify_exact_head_sha(actual_head_sha: str, expected_head_sha: str) -> bool:
    """
    Exact-SHA fencing matching Frozen Spec Section 15:
    actual current PR head == expected repair baseline.
    """
    if not actual_head_sha or not expected_head_sha:
        return False
    return actual_head_sha.strip().lower() == expected_head_sha.strip().lower()


def classify_ci_failure(failure_info: dict) -> tuple[str, str]:
    """
    Classify a CI check run failure according to Frozen Spec Section 12:
    - 'code_failure': clearly caused by this implementation (test/lint/guard/build error) -> eligible for repair
    - 'infra_failure': GitHub Actions runner outage, runner timeout, host crash -> infra-blocked
    - 'ambiguous': semantic ambiguity, cancelled without reason, unclassifiable -> needs-human
    """
    if not failure_info:
        return "ambiguous", "empty_failure_info"

    name = str(failure_info.get("name") or failure_info.get("job") or "").lower()
    conclusion = str(failure_info.get("conclusion") or "").lower()
    output = str(failure_info.get("output") or failure_info.get("message") or failure_info.get("title") or "").lower()
    log_snippet = str(failure_info.get("log_snippet") or failure_info.get("details") or "").lower()
    description = str(failure_info.get("description") or "").lower()

    combined = f"{name} {conclusion} {output} {log_snippet} {description}"

    # Infrastructure failures
    infra_markers = [
        "runner disconnected", "lost communication with the server", "hosted runner",
        "github actions outage", "infrastructure failure", "internal error in runner",
        "unable to contact runner", "runner image provisioning failed", "runner timeout",
    ]
    if any(m in combined for m in infra_markers):
        return "infra_failure", "github_actions_infrastructure_error"

    # Cancellation / Ambiguity
    if conclusion in ("cancelled", "action_required"):
        return "ambiguous", f"check_conclusion_{conclusion}"

    # Implementation / Code failures
    code_markers = [
        "failed", "failure", "assertionerror", "exit code 1", "exit code 2",
        "whitespace", "guard", "scan_hardcoded_paths", "tampering",
        "test failed", "syntaxerror", "compilation error", "npm test",
        "unittest", "pytest", "build error",
    ]
    if any(m in combined for m in code_markers) or conclusion == "failure":
        return "code_failure", "implementation_check_failure"

    return "ambiguous", "unrecognized_failure_classification"


def check_cancellation_fencing(issue_details: dict) -> tuple[bool, str]:
    """
    Cancellation fencing matching Frozen Spec Section 19:
    If issue is closed, not planned, infra-blocked, needs-human, or authorization revoked:
    strictly do NOT launch Implementer, repair, APPROVE, or Auto-merge.
    """
    if not issue_details:
        return True, "issue_details_missing"

    state = str(issue_details.get("state") or "").upper()
    if state != "OPEN":
        return True, "issue_not_open"

    labels = {
        l.get("name") if isinstance(l, dict) else str(l)
        for l in issue_details.get("labels", [])
    }

    if "infra-blocked" in labels:
        return True, "infra_blocked"
    if "needs-human" in labels:
        return True, "needs_human"
    if "frozen-spec" not in labels:
        return True, "frozen_spec_missing"

    return False, "authorized"


def adopt_existing_pr(repo: str, issue_number: int, pulls_list: list[dict] = None) -> tuple[str, dict | None]:
    """
    Existing PR adoption matching Frozen Spec Section 17:
    When local state is lost but GitHub already has PR:
    find linked bot PR; author must be chang-implementer[bot];
    repo/base/branch/Issue relationship must be correct.
    Exactly one valid candidate -> adopt;
    multiple plausible PR -> needs-human.
    """
    if pulls_list is None:
        gh_bin = shutil.which("gh") or "gh"
        cmd = [gh_bin, "api", f"repos/{repo}/pulls?state=open", "--paginate"]
        code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
        if code != 0 or timed_out or not stdout.strip():
            logger.warning("Could not fetch open PRs for adoption")
            return "fetch_failed", None
        try:
            pulls_list = json.loads(stdout)
        except json.JSONDecodeError:
            return "fetch_failed", None

    candidates = []
    issue_tag = f"#{issue_number}"
    issue_branch_tag = f"issue-{issue_number}"

    for pr in pulls_list:
        base_ref = ((pr.get("base") or {}).get("ref")) or ""
        head_ref = ((pr.get("head") or {}).get("ref")) or ""
        title = pr.get("title") or ""
        body = pr.get("body") or ""

        matches_branch = issue_branch_tag in head_ref
        matches_text = issue_tag in title or issue_tag in body
        if not (matches_branch or matches_text):
            continue

        if not is_valid_canonical_pr_author(pr):
            logger.warning(
                f"PR #{pr.get('number')} relates to Issue #{issue_number} but author is not canonical bot: {pr.get('user')}"
            )
            return "invalid_author", None

        if base_ref not in ("main", "master"):
            continue

        candidates.append(pr)

    if len(candidates) == 1:
        logger.info(f"Adopted existing bot PR #{candidates[0].get('number')} for Issue #{issue_number}")
        return "adopted", candidates[0]
    elif len(candidates) > 1:
        logger.warning(
            f"Multiple candidate PRs found for Issue #{issue_number} ({[p.get('number') for p in candidates]}). Needs human."
        )
        return "needs_human_multiple_candidates", None
    else:
        return "none_found", None


HEX_40_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def get_review_target_commit_sha(review: dict) -> str | None:
    """
    Extract the target commit SHA from a review:
    1. Formal marker [easyexam-review:<40-hex-SHA>] in review body
    2. 'Reviewed head: <40-hex-SHA>' in review body (plain or backtick-wrapped)
    3. Native GitHub review commit_id (40 hex)

    Requires an exact normalized 40-hex equality from native commit_id or the formal full-SHA marker.
    Rejects abbreviated or prefix-only markers (< 40 hex).
    Rejects conflicting body-marker and native-commit values.
    Returns normalized 40-hex lowercase string, or None if invalid, abbreviated, or conflicting.
    """
    if not review or not isinstance(review, dict):
        return None

    body = review.get("body") or ""
    body_shas = set()

    # Search for [easyexam-review:...] markers
    for m in re.finditer(r"\[easyexam-review:([^\]\s]+)\]", body):
        token = m.group(1).strip()
        if not HEX_40_RE.match(token):
            return None
        body_shas.add(token.lower())

    # Search for Reviewed head: markers (supports optional backticks)
    for m in re.finditer(r"Reviewed head:\s*`?([^`\s\r\n]+)`?", body):
        token = m.group(1).strip()
        if not HEX_40_RE.match(token):
            return None
        body_shas.add(token.lower())

    if len(body_shas) > 1:
        return None

    native_commit = (review.get("commit_id") or "").strip()
    if native_commit:
        if not HEX_40_RE.match(native_commit):
            return None
        native_norm = native_commit.lower()
        if body_shas and native_norm not in body_shas:
            return None
        return native_norm

    if body_shas:
        return next(iter(body_shas))

    return None


def is_review_anchored_to_sha(review: dict, expected_sha: str) -> bool:
    """
    Determine if a review is anchored to expected_sha via commit_id or exact formal marker.
    Requires exact normalized 40-hex equality between the review's target SHA and expected_sha.
    Abbreviated or prefix-only matches are strictly rejected.
    """
    if not review or not expected_sha:
        return False
    e_sha = str(expected_sha).strip()
    if not HEX_40_RE.match(e_sha):
        return False
    target = get_review_target_commit_sha(review)
    if not target or not HEX_40_RE.match(target):
        return False
    return target == e_sha.lower()


def get_latest_changes_requested_review(
    repo: str, pr_number: int, reviews_list: list[dict] = None, target_head_sha: str = None
) -> dict | None:
    """
    Fetch reviews for the given PR and return the latest CHANGES_REQUESTED review.
    Enforces exact review baseline matching Frozen Spec Sections 13-15.
    If target_head_sha is specified, only reviews anchored to target_head_sha are considered.
    """
    if reviews_list is None:
        gh_bin = shutil.which("gh") or "gh"
        cmd = [gh_bin, "api", f"repos/{repo}/pulls/{pr_number}/reviews", "--paginate"]
        code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
        if code != 0 or timed_out or not stdout.strip():
            logger.error(f"Failed to fetch reviews for PR #{pr_number}: {stderr}")
            return None
        try:
            reviews_list = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse reviews for PR #{pr_number}: {exc}")
            return None

    if not isinstance(reviews_list, list):
        return None

    cr_reviews = [r for r in reviews_list if r.get("state") == "CHANGES_REQUESTED"]
    if target_head_sha:
        cr_reviews = [r for r in cr_reviews if is_review_anchored_to_sha(r, target_head_sha)]
    if not cr_reviews:
        return None
    cr_reviews.sort(key=lambda r: (r.get("submitted_at") or "", r.get("id") or 0))
    return cr_reviews[-1]


def evaluate_watchdog_timeout(attempt: dict, now_ts: float = None) -> tuple[bool, str | None, str | None]:
    """
    Watchdog evaluation matching Frozen Spec Section 18:
    Active flow has configurable deadlines.
    Timeout must eventually transition to infra-blocked or needs-human.
    Returns (is_timed_out: bool, reason: str | None, target_state: str | None).
    """
    if not attempt:
        return False, None, None

    now = time.time() if now_ts is None else float(now_ts)
    # Prefer phase_entered_at to preserve stable phase/progress deadline
    updated_str = (
        attempt.get("phase_entered_at")
        or attempt.get("updated_at")
        or attempt.get("heartbeat_at")
        or attempt.get("created_at")
    )
    if not updated_str:
        return False, None, None

    try:
        updated_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        updated_ts = updated_dt.timestamp()
    except Exception:
        return False, None, None

    elapsed = now - updated_ts
    phase = attempt.get("phase")

    if phase in ("CLAIM_INTENT", "CLAIMED") and elapsed > LAUNCH_CONFIRMATION_DEADLINE_SECONDS:
        return True, "claim_confirmation_timeout", "infra-blocked"

    if phase == "LAUNCH_INTENT" and elapsed > LAUNCH_CONFIRMATION_DEADLINE_SECONDS:
        return True, "launch_confirmation_timeout", "infra-blocked"

    if phase in ("LAUNCH_CONFIRMED", "PR_BOUND"):
        # For implementer phases, check elapsed time since latest heartbeat (or phase_entered_at if no heartbeat)
        hb_str = attempt.get("heartbeat_at") or updated_str
        try:
            hb_dt = datetime.fromisoformat(hb_str.replace("Z", "+00:00"))
            hb_elapsed = now - hb_dt.timestamp()
        except Exception:
            hb_elapsed = elapsed
        if hb_elapsed > IMPLEMENTER_DEADLINE_SECONDS:
            return True, "implementer_heartbeat_timeout", "infra-blocked"

    if phase == "WAITING_CI" and elapsed > CI_TERMINALIZATION_DEADLINE_SECONDS:
        return True, "ci_terminalization_timeout", "infra-blocked"

    if phase == "WAITING_REVIEW" and elapsed > REVIEWER_COMPLETION_DEADLINE_SECONDS:
        return True, "reviewer_completion_timeout", "needs-human"

    if phase == "WAITING_MERGE" and elapsed > AUTO_MERGE_DEADLINE_SECONDS:
        return True, "auto_merge_timeout", "infra-blocked"

    return False, None, None


class ExecutionLedger:
    """
    Durable execution ledger backed by SQLite.
    Guarantees persistence of ownership leases, dispatch lifecycles, and repair accounting.
    """

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = LEDGER_DB_PATH
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._init_db()
        return self._conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    owner_id TEXT NOT NULL,
                    lease_token TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    phase_entered_at TEXT,
                    heartbeat_at TEXT NOT NULL,
                    attempt_id TEXT NOT NULL UNIQUE,
                    attempt_kind TEXT NOT NULL,
                    trigger_key TEXT NOT NULL,
                    repair_key TEXT,
                    repair_ordinal INTEGER DEFAULT 0,
                    repair_cause_type TEXT,
                    repair_cause_id TEXT,
                    expected_base_sha TEXT,
                    expected_pr_head_sha TEXT,
                    conversation_id TEXT,
                    launch_confirmed INTEGER DEFAULT 0,
                    pr_number INTEGER,
                    branch TEXT,
                    resulting_head_sha TEXT,
                    outcome TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            try:
                conn.execute("ALTER TABLE execution_ledger ADD COLUMN phase_entered_at TEXT")
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_leases (
                    repo TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    owner_id TEXT NOT NULL,
                    lease_token TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    PRIMARY KEY (repo, issue_number)
                )
            """)
            conn.commit()

    def acquire_lease(
        self,
        repo: str,
        issue_number: int,
        owner_id: str,
        ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
    ) -> tuple[bool, str | None, str]:
        """
        Acquire an exclusive ownership lease for an issue.
        Two-worker claim race: exactly one worker wins.
        Expired leases held by another worker do NOT automatically transfer (requires confirmation/fencing).
        Returns (success: bool, lease_token: str | None, reason: str).
        """
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        expires_iso = datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM active_leases WHERE repo = ? AND issue_number = ?", (repo, issue_number))
            row = cur.fetchone()
            if row is not None:
                if row["owner_id"] == owner_id:
                    cur.execute(
                        "UPDATE active_leases SET expires_at = ?, heartbeat_at = ? WHERE repo = ? AND issue_number = ?",
                        (expires_iso, now_iso, repo, issue_number),
                    )
                    conn.commit()
                    return True, row["lease_token"], "renewed"
                else:
                    return False, None, "lease_held_by_other_worker"

            token = str(uuid.uuid4())
            try:
                cur.execute(
                    """
                    INSERT INTO active_leases (repo, issue_number, owner_id, lease_token, acquired_at, expires_at, heartbeat_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (repo, issue_number, owner_id, token, now_iso, expires_iso, now_iso),
                )
                conn.commit()
                return True, token, "acquired"
            except sqlite3.IntegrityError:
                return False, None, "lease_race_lost"

    def renew_lease(self, lease_token: str, ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS) -> bool:
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        expires_iso = datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE active_leases SET expires_at = ?, heartbeat_at = ? WHERE lease_token = ?",
                (expires_iso, now_iso, lease_token),
            )
            conn.commit()
            return cur.rowcount > 0

    def release_lease(self, lease_token: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM active_leases WHERE lease_token = ?", (lease_token,))
            conn.commit()
            return cur.rowcount > 0

    def release_issue_lease(self, repo: str, issue_number: int) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM active_leases WHERE repo = ? AND issue_number = ?", (repo, issue_number))
            conn.commit()
            return cur.rowcount > 0

    def get_active_lease(self, repo: str, issue_number: int) -> dict | None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM active_leases WHERE repo = ? AND issue_number = ?", (repo, issue_number))
            row = cur.fetchone()
            return dict(row) if row else None

    def record_claim_intent(
        self,
        repo: str,
        issue_number: int,
        owner_id: str,
        lease_token: str,
        attempt_id: str,
        attempt_kind: str,
        trigger_key: str,
        expected_base_sha: str = None,
        expected_pr_head_sha: str = None,
        repair_key: str = None,
        repair_ordinal: int = 0,
        repair_cause_type: str = None,
        repair_cause_id: str = None,
        pr_number: int = None,
        branch: str = None,
    ) -> dict:
        now_iso = datetime.now(timezone.utc).isoformat()
        entry = {
            "repo": repo,
            "issue_number": issue_number,
            "owner_id": owner_id,
            "lease_token": lease_token,
            "phase": "CLAIM_INTENT",
            "phase_entered_at": now_iso,
            "heartbeat_at": now_iso,
            "attempt_id": attempt_id,
            "attempt_kind": attempt_kind,
            "trigger_key": trigger_key,
            "repair_key": repair_key,
            "repair_ordinal": repair_ordinal,
            "repair_cause_type": repair_cause_type,
            "repair_cause_id": repair_cause_id,
            "expected_base_sha": expected_base_sha,
            "expected_pr_head_sha": expected_pr_head_sha,
            "conversation_id": None,
            "launch_confirmed": 0,
            "pr_number": pr_number,
            "branch": branch,
            "resulting_head_sha": None,
            "outcome": "in_progress",
            "last_error": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO execution_ledger (
                    repo, issue_number, owner_id, lease_token, phase, phase_entered_at, heartbeat_at,
                    attempt_id, attempt_kind, trigger_key, repair_key, repair_ordinal,
                    repair_cause_type, repair_cause_id, expected_base_sha, expected_pr_head_sha,
                    conversation_id, launch_confirmed, pr_number, branch, resulting_head_sha,
                    outcome, last_error, created_at, updated_at
                ) VALUES (
                    :repo, :issue_number, :owner_id, :lease_token, :phase, :phase_entered_at, :heartbeat_at,
                    :attempt_id, :attempt_kind, :trigger_key, :repair_key, :repair_ordinal,
                    :repair_cause_type, :repair_cause_id, :expected_base_sha, :expected_pr_head_sha,
                    :conversation_id, :launch_confirmed, :pr_number, :branch, :resulting_head_sha,
                    :outcome, :last_error, :created_at, :updated_at
                )
                """,
                entry,
            )
            conn.commit()
        return entry

    def record_claimed(self, attempt_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE execution_ledger SET phase = 'CLAIMED', phase_entered_at = ?, updated_at = ?, heartbeat_at = ? WHERE attempt_id = ?",
                (now_iso, now_iso, now_iso, attempt_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def record_launch_intent(self, attempt_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE execution_ledger SET phase = 'LAUNCH_INTENT', phase_entered_at = ?, updated_at = ?, heartbeat_at = ? WHERE attempt_id = ?",
                (now_iso, now_iso, now_iso, attempt_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def record_launch_confirmed(self, attempt_id: str, conversation_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE execution_ledger
                SET phase = 'LAUNCH_CONFIRMED', phase_entered_at = ?, conversation_id = ?, launch_confirmed = 1,
                    updated_at = ?, heartbeat_at = ?
                WHERE attempt_id = ?
                """,
                (now_iso, conversation_id, now_iso, now_iso, attempt_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def record_pr_bound(
        self, attempt_id: str, pr_number: int, branch: str, resulting_head_sha: str = None, phase_entered_at: str = None
    ) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        p_entered = phase_entered_at or now_iso
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE execution_ledger
                SET phase = 'PR_BOUND', phase_entered_at = ?, pr_number = ?, branch = ?,
                    resulting_head_sha = COALESCE(?, resulting_head_sha),
                    updated_at = ?, heartbeat_at = ?
                WHERE attempt_id = ?
                """,
                (p_entered, pr_number, branch, resulting_head_sha, now_iso, now_iso, attempt_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def record_outcome(
        self, attempt_id: str, outcome: str, resulting_head_sha: str = None, last_error: str = None
    ) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE execution_ledger
                SET phase = 'EXECUTION_OUTCOME', outcome = ?,
                    resulting_head_sha = COALESCE(?, resulting_head_sha),
                    last_error = ?, updated_at = ?, heartbeat_at = ?
                WHERE attempt_id = ?
                """,
                (outcome, resulting_head_sha, last_error, now_iso, now_iso, attempt_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_attempt(self, attempt_id: str) -> dict | None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM execution_ledger WHERE attempt_id = ?", (attempt_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_repair_count(self, repo: str, pr_number: int) -> int:
        """
        Count automated repairs on this PR across BOTH CI failures and Reviewer REQUEST_CHANGES.
        Aborted stale attempts and duplicates do not consume the budget.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) as cnt FROM execution_ledger
                WHERE repo = ? AND pr_number = ?
                  AND attempt_kind IN ('ci_repair', 'reviewer_repair')
                  AND outcome NOT IN ('aborted_stale', 'duplicate_ignored')
                """,
                (repo, pr_number),
            )
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0

    def can_attempt_repair(self, repo: str, pr_number: int, max_repairs: int = MAX_AUTOMATED_REPAIRS) -> tuple[bool, int]:
        current = self.get_repair_count(repo, pr_number)
        if current >= max_repairs:
            return False, current
        return True, current + 1

    def is_repair_key_processed(self, repair_key: str) -> bool:
        if not repair_key:
            return False
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 1 FROM execution_ledger
                WHERE repair_key = ?
                  AND outcome NOT IN ('failed_to_claim', 'aborted_stale')
                LIMIT 1
                """,
                (repair_key,),
            )
            return cur.fetchone() is not None

    def get_active_repair_attempt(self, repair_key: str) -> dict | None:
        """Return the active in-progress attempt record for this repair key, if any."""
        if not repair_key:
            return None
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM execution_ledger
                WHERE repair_key = ?
                  AND phase != 'EXECUTION_OUTCOME'
                  AND outcome = 'in_progress'
                ORDER BY id DESC LIMIT 1
                """,
                (repair_key,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_all_attempts_for_issue(self, repo: str, issue_number: int) -> list[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM execution_ledger WHERE repo = ? AND issue_number = ? ORDER BY id ASC",
                (repo, issue_number),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_active_attempts(self, repo: str = None) -> list[dict]:
        """Return all active in-progress attempts for bounded runtime watchdog evaluation."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            if repo:
                cur.execute(
                    "SELECT * FROM execution_ledger WHERE repo = ? AND phase != 'EXECUTION_OUTCOME' AND outcome = 'in_progress' ORDER BY id ASC",
                    (repo,),
                )
            else:
                cur.execute(
                    "SELECT * FROM execution_ledger WHERE phase != 'EXECUTION_OUTCOME' AND outcome = 'in_progress' ORDER BY id ASC"
                )
            return [dict(r) for r in cur.fetchall()]

    def record_phase(self, attempt_id: str, phase: str, resulting_head_sha: str = None, phase_entered_at: str = None) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        p_entered = phase_entered_at or now_iso
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE execution_ledger
                SET phase = ?,
                    phase_entered_at = ?,
                    resulting_head_sha = COALESCE(?, resulting_head_sha),
                    updated_at = ?, heartbeat_at = ?
                WHERE attempt_id = ?
                """,
                (phase, p_entered, resulting_head_sha, now_iso, now_iso, attempt_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def update_heartbeat(self, attempt_id: str, heartbeat_at: str | None = None) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        hb_iso = heartbeat_at or now_iso
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT heartbeat_at FROM execution_ledger WHERE attempt_id = ?", (attempt_id,))
            row = cur.fetchone()
            if row and row["heartbeat_at"] and heartbeat_at:
                try:
                    existing_ts = datetime.fromisoformat(row["heartbeat_at"].replace("Z", "+00:00")).timestamp()
                    new_ts = datetime.fromisoformat(hb_iso.replace("Z", "+00:00")).timestamp()
                    if new_ts <= existing_ts:
                        return False
                except Exception:
                    pass
            cur.execute(
                "UPDATE execution_ledger SET heartbeat_at = ?, updated_at = ? WHERE attempt_id = ?",
                (hb_iso, now_iso, attempt_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def renew_issue_lease(self, repo: str, issue_number: int, ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS) -> bool:
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        expires_iso = datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE active_leases SET expires_at = ?, heartbeat_at = ? WHERE repo = ? AND issue_number = ?",
                (expires_iso, now_iso, repo, issue_number),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_active_attempt_for_issue(self, repo: str, issue_number: int) -> dict | None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM execution_ledger
                WHERE repo = ? AND issue_number = ? AND phase != 'EXECUTION_OUTCOME' AND outcome = 'in_progress'
                ORDER BY id DESC LIMIT 1
                """,
                (repo, issue_number),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def close(self):
        if hasattr(self, "_conn") and self._conn:
            self._conn.close()
            self._conn = None


_LEDGER_INSTANCE = None


def get_ledger(db_path=None) -> ExecutionLedger:
    global _LEDGER_INSTANCE
    if _LEDGER_INSTANCE is None or db_path is not None or getattr(_LEDGER_INSTANCE, "_conn", None) is None:
        _LEDGER_INSTANCE = ExecutionLedger(db_path=db_path or LEDGER_DB_PATH)
    return _LEDGER_INSTANCE


def set_ledger(ledger: ExecutionLedger):
    global _LEDGER_INSTANCE
    _LEDGER_INSTANCE = ledger


def fail_closed_to_needs_human(repo: str, issue_number: int, reason: str, attempt_id: str = None) -> bool:
    """
    Transition issue to needs-human when automated repair budget is exhausted
    or human architectural decision is required.
    """
    category = str(reason or "needs_human_required")
    logger.warning(
        f"Switching #{issue_number} to needs-human. Category: {category}"
    )

    details = get_issue_details(repo, issue_number)
    labels = {
        l.get("name") if isinstance(l, dict) else str(l)
        for l in (details or {}).get("labels", [])
    }
    remove_labels = [l for l in ("agent-working", "changes-requested", "agent-ready") if l in labels]

    cmd_edit = [
        "issue",
        "edit",
        str(issue_number),
        "--repo",
        repo,
        "--add-label",
        "needs-human",
    ]
    for rl in remove_labels:
        cmd_edit.extend(["--remove-label", rl])

    code, _, stderr, timed_out = execute_coordination_write(cmd_edit, repo=repo)
    label_ok = code == 0 and not timed_out
    if not label_ok:
        logger.critical(f"Failed to label #{issue_number} as needs-human: {stderr}")

    marker = f"<!-- easyexam-needs-human:{attempt_id} -->" if attempt_id else None
    comment_body = (
        f"**[EasyExam Dispatcher Alert — Human Decision Required]**\n\n"
        f"This task requires human judgment or has exhausted automated repairs:\n"
        f"- Reason: `{category}`\n"
        f"- Target coordination state: `needs-human`.\n"
        f"Please inspect the issue and PR, then re-authorize with `agent-ready` or resolve manually."
    )
    if marker:
        comment_body += f"\n\n{marker}"

    cmd_comment = [
        "issue",
        "comment",
        str(issue_number),
        "--repo",
        repo,
        "--body",
        comment_body,
    ]
    comment_code, _, _, comment_timeout = execute_coordination_write(cmd_comment, repo=repo)
    return label_ok and comment_code == 0 and not comment_timeout


def dispatch_automated_repair(
    repo: str,
    issue_number: int,
    pr_number: int,
    current_pr_head_sha: str,
    expected_repair_baseline_sha: str,
    repair_kind: str,
    cause_type: str,
    cause_id: str,
    failure_detail: dict = None,
    ledger: ExecutionLedger = None,
    owner_id: str = None,
    branch: str = None,
) -> tuple[bool, str, dict]:
    """
    Unified repair workflow matching Frozen Spec Sections 10-15:
    1. Cancellation fencing check.
    2. Exact-SHA fencing check: current_pr_head_sha == expected_repair_baseline_sha.
    3. Failure classification: if infra -> infra-blocked; if ambiguous -> needs-human.
    4. Deduplication via repair_key: repair:<repo>:pr:<pr_number>:head:<sha>.
    5. Unified budget enforcement: MAX_AUTOMATED_REPAIRS = 3 (CI + Reviewer combined).
    6. Acquire exclusive lease.
    7. CAS transition if needed.
    8. Launch AntiGravity Implementer.
    9. Durable ledger persistence across all phases.
    """
    ledger = ledger or get_ledger()
    owner_id = owner_id or f"dispatcher-{os.getpid()}"
    attempt_id = str(uuid.uuid4())

    # 1. Cancellation check
    issue_details = get_issue_details(repo, issue_number)
    is_blocked, block_reason = check_cancellation_fencing(issue_details)
    if is_blocked:
        logger.warning(f"Repair aborted due to cancellation fencing: #{issue_number} ({block_reason})")
        return False, f"cancellation_fenced_{block_reason}", {}

    # 2. Exact-SHA fencing
    if not verify_exact_head_sha(current_pr_head_sha, expected_repair_baseline_sha):
        logger.warning(
            f"Stale repair abort for #{issue_number} / PR #{pr_number}: "
            f"head SHA changed (expected {expected_repair_baseline_sha}, actual {current_pr_head_sha})"
        )
        return False, "stale_head_sha_mismatch", {}

    # 3. Failure classification (if CI repair)
    if cause_type == "ci_failure":
        classification, class_reason = classify_ci_failure(failure_detail or {})
        if classification == "infra_failure":
            fail_closed_to_infra_blocked(repo, issue_number, f"ci_infra_{class_reason}", attempt_id)
            return False, "infra_failure_blocked", {}
        elif classification == "ambiguous":
            fail_closed_to_needs_human(repo, issue_number, f"ci_ambiguous_{class_reason}", attempt_id)
            return False, "ambiguous_failure_needs_human", {}

    # 4. Repair Key & Idempotency
    repair_key = compute_repair_key(repo, pr_number, expected_repair_baseline_sha)
    if ledger.is_repair_key_processed(repair_key):
        logger.info(f"Duplicate repair ignored for #{issue_number} / PR #{pr_number} (key: {repair_key})")
        return False, "duplicate_repair_ignored", {"repair_key": repair_key}

    # 5. Unified Budget Check
    can_repair, ordinal = ledger.can_attempt_repair(repo, pr_number, max_repairs=MAX_AUTOMATED_REPAIRS)
    if not can_repair:
        logger.critical(
            f"Repair budget exhausted for #{issue_number} / PR #{pr_number}: "
            f"{ordinal} repairs recorded, max is {MAX_AUTOMATED_REPAIRS}. Switching to needs-human."
        )
        fail_closed_to_needs_human(repo, issue_number, "repair_budget_exhausted_max_3", attempt_id)
        return False, "repair_budget_exhausted_needs_human", {"repair_ordinal": ordinal}

    # 6. Acquire Lease
    acquired, lease_token, lease_reason = ledger.acquire_lease(repo, issue_number, owner_id)
    if not acquired:
        logger.warning(f"Could not acquire lease for #{issue_number} repair: {lease_reason}")
        return False, f"lease_unavailable_{lease_reason}", {}

    # 7. Record claim intent in ledger
    trigger_key = f"repair_trigger:{repair_key}:{attempt_id}"
    ledger_entry = ledger.record_claim_intent(
        repo=repo,
        issue_number=issue_number,
        owner_id=owner_id,
        lease_token=lease_token,
        attempt_id=attempt_id,
        attempt_kind=repair_kind,
        trigger_key=trigger_key,
        expected_pr_head_sha=expected_repair_baseline_sha,
        repair_key=repair_key,
        repair_ordinal=ordinal,
        repair_cause_type=cause_type,
        repair_cause_id=cause_id,
        pr_number=pr_number,
        branch=branch,
    )

    try:
        append_dispatch_audit({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "attempt_id": attempt_id,
            "event": "claim_intent",
            "repo": repo,
            "issue_number": issue_number,
            "source_label": "changes-requested" if repair_kind == "reviewer_repair" else "agent-working",
            "repair_key": repair_key,
            "repair_ordinal": ordinal,
            "final_coordination_state": "agent-working",
        })
    except Exception:
        pass

    # 7b. Mutation boundary re-check: fresh canonical PR read
    # Require the live PR to remain open, canonical, and live head == expected_repair_baseline_sha.
    live_pr = get_pull_request_details(repo, pr_number)
    live_state = str((live_pr or {}).get("state") or "").lower()
    live_head_sha = ((live_pr or {}).get("head") or {}).get("sha") or ""
    is_canonical = is_valid_canonical_pr_author(live_pr)
    head_matches = verify_exact_head_sha(live_head_sha, expected_repair_baseline_sha) if live_head_sha else False

    if not live_pr or live_state != "open" or not is_canonical or not head_matches:
        logger.warning(
            f"Stale repair abort at mutation boundary for #{issue_number} / PR #{pr_number}: "
            f"live_state={live_state}, is_canonical={is_canonical}, "
            f"live_head={live_head_sha}, expected={expected_repair_baseline_sha}"
        )
        ledger.record_outcome(
            attempt_id,
            "aborted_stale",
            resulting_head_sha=live_head_sha or current_pr_head_sha,
            last_error=f"mutation_boundary_mismatch:live_head={live_head_sha},expected={expected_repair_baseline_sha},state={live_state},canonical={is_canonical}",
        )
        ledger.release_lease(lease_token)
        ledger.release_issue_lease(repo, issue_number)
        try:
            append_dispatch_audit({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "attempt_id": attempt_id,
                "event": "aborted_stale",
                "repo": repo,
                "issue_number": issue_number,
                "source_label": "changes-requested" if repair_kind == "reviewer_repair" else "agent-working",
                "repair_key": repair_key,
                "repair_ordinal": ordinal,
                "live_head_sha": live_head_sha,
                "expected_pr_head_sha": expected_repair_baseline_sha,
                "final_coordination_state": "changes-requested" if repair_kind == "reviewer_repair" else "agent-working",
            })
        except Exception:
            pass
        return False, "aborted_stale", {
            "live_head_sha": live_head_sha,
            "expected_repair_baseline_sha": expected_repair_baseline_sha,
            "live_state": live_state,
            "is_canonical": is_canonical,
        }

    # 8. CAS transition if reviewer repair
    if repair_kind == "reviewer_repair":
        transitioned, trans_reason = cas_transition_coordination_state(
            repo, issue_number, "changes-requested", "agent-working"
        )
        if not transitioned:
            ledger.record_outcome(attempt_id, "failed_to_claim", last_error=trans_reason)
            ledger.release_lease(lease_token)
            return False, f"transition_failed_{trans_reason}", {}

    ledger.record_claimed(attempt_id)
    ledger.record_launch_intent(attempt_id)

    # 9. Launch Agent
    title = (issue_details or {}).get("title", "")
    source_label = "changes-requested" if repair_kind == "reviewer_repair" else "ci-repair"
    launch_result = dispatch_agent(
        repo,
        EASYEXAM_REPO_PATH,
        issue_number,
        title,
        source_label,
        repair_ordinal=ordinal,
        repair_kind=repair_kind,
        failure_detail=failure_detail,
    )

    if launch_result.get("launch_confirmed") and launch_result.get("conversation_id"):
        conv_id = launch_result["conversation_id"]
        ledger.record_launch_confirmed(attempt_id, conv_id)
        logger.info(
            f"Automated repair #{ordinal} launched successfully for #{issue_number} / PR #{pr_number}: {conv_id}"
        )
        try:
            append_dispatch_audit({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "attempt_id": attempt_id,
                "event": "launch_confirmed",
                "repo": repo,
                "issue_number": issue_number,
                "source_label": source_label,
                "repair_key": repair_key,
                "repair_ordinal": ordinal,
                "conversation_id": conv_id,
                "launch_confirmed": True,
                "final_coordination_state": "agent-working",
            })
        except Exception:
            pass
        return True, "repair_launched", {
            "attempt_id": attempt_id,
            "repair_ordinal": ordinal,
            "conversation_id": conv_id,
            "repair_key": repair_key,
        }
    else:
        err_cat = launch_result.get("error_category") or "launch_unconfirmed"
        ledger.record_outcome(attempt_id, "failed_to_launch", last_error=err_cat)
        fail_closed_to_infra_blocked(repo, issue_number, err_cat, attempt_id)
        ledger.release_lease(lease_token)
        try:
            append_dispatch_audit({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "attempt_id": attempt_id,
                "event": "finalized",
                "repo": repo,
                "issue_number": issue_number,
                "source_label": source_label,
                "repair_key": repair_key,
                "repair_ordinal": ordinal,
                "launch_confirmed": False,
                "final_coordination_state": "infra-blocked",
                "error_category": err_cat,
            })
        except Exception:
            pass
        return False, f"launch_failed_{err_cat}", {"attempt_id": attempt_id}



class WindowsSingleInstanceLock:
    """Named Mutex / file lock to ensure single dispatcher instance across Windows and Unix hosts."""

    def __init__(self, mutex_name="Local\\EasyExamDispatcherMutex"):
        self.mutex_name = mutex_name
        self.mutex_handle = None
        self._unix_fd = None

    def acquire(self):
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            self.mutex_handle = kernel32.CreateMutexW(None, False, self.mutex_name)
            last_error = kernel32.GetLastError()
            if last_error == ERROR_ALREADY_EXISTS:
                logger.error(
                    f"Another instance of dispatcher is already running (Mutex {self.mutex_name} exists). Exiting immediately."
                )
                return False
            return True
        else:
            try:
                import fcntl
                import tempfile
                safe_name = self.mutex_name.replace("\\", "_").replace(":", "_").replace("/", "_")
                lock_file = os.path.join(tempfile.gettempdir(), f"{safe_name}.lock")
                self._unix_fd = open(lock_file, "w")
                fcntl.flock(self._unix_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (BlockingIOError, OSError):
                if self._unix_fd:
                    try:
                        self._unix_fd.close()
                    except Exception:
                        pass
                    self._unix_fd = None
                logger.error(
                    f"Another instance of dispatcher is already running (Lock {self.mutex_name} exists). Exiting immediately."
                )
                return False
            except Exception as exc:
                logger.warning(f"Could not initialize single-instance lock on non-Windows host ({exc}); permitting execution.")
                return True

    def release(self):
        if sys.platform == "win32":
            if self.mutex_handle:
                ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
                self.mutex_handle = None
        else:
            if self._unix_fd:
                try:
                    import fcntl
                    fcntl.flock(self._unix_fd.fileno(), fcntl.LOCK_UN)
                    self._unix_fd.close()
                except Exception:
                    pass
                self._unix_fd = None


def get_agentapi_cmd_prefix():
    """
    Locate language_server.exe directly to avoid cmd.exe shell wrapper.
    Returns argv prefix list, e.g. [language_server_path, 'agentapi']
    """
    lang_server = os.environ.get(
        "ANTIGRAVITY_LANGUAGE_SERVER_PATH",
        str(Path.home() / "AppData" / "Local" / "Programs" / "antigravity" / "resources" / "bin" / "language_server.exe"),
    )
    if os.path.exists(lang_server):
        return [lang_server, "agentapi"]

    bat_path = shutil.which("agentapi.bat") or shutil.which("agentapi")
    if bat_path and os.path.exists(bat_path):
        try:
            with open(bat_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if "language_server.exe" in line and not line.startswith("@") and not line.startswith("REM"):
                    parts = line.split('"')
                    if len(parts) >= 2 and os.path.exists(parts[1]):
                        return [parts[1], "agentapi"]
        except Exception as exc:
            logger.warning(f"Could not parse agentapi.bat for language_server.exe: {exc}")
        return [bat_path]

    return ["agentapi"]


def _redact_secrets(value, env):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value or "")
    for key in ("GH_TOKEN", "GITHUB_APP_TOKEN", "GITHUB_TOKEN"):
        secret = (env or {}).get(key)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text.strip()


def extract_conversation_id(stdout):
    """Return the durable Antigravity conversation ID from agentapi JSON output."""
    try:
        payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return None

    pending = [payload]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            try:
                pending.append(json.loads(current))
            except (TypeError, json.JSONDecodeError):
                continue
        elif isinstance(current, dict):
            conversation_id = current.get("conversationId") or current.get("conversation_id")
            if isinstance(conversation_id, str) and re.fullmatch(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                conversation_id,
            ):
                return conversation_id
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return None


_CONVERSATION_PROGRESS_CACHE: dict[str, float] = {}


def reset_conversation_progress_cache() -> None:
    """Clear in-memory conversation progress cache (useful for tests)."""
    _CONVERSATION_PROGRESS_CACHE.clear()


def check_implementer_conversation_progress(
    conversation_id: str,
    last_activity_ts: float | str | None = None,
    custom_root: Path | str | None = None,
) -> tuple[bool, float | None]:
    """
    Check if the Antigravity Implementer conversation has observable progress on disk.
    Inspects conversation SQLite db and/or transcript logs.
    Distinguishes new activity from static conversation artifacts by comparing against
    an observed activity timestamp (last_activity_ts) or an internal monotonic marker.
    Returns (has_progress: bool, latest_activity_ts: float | None).
    """
    if not conversation_id or not re.fullmatch(r"[0-9a-zA-Z_-]+", conversation_id):
        return False, None

    candidate_roots = []
    if custom_root:
        candidate_roots.append(Path(custom_root))
    env_root = os.environ.get("EASYEXAM_ANTIGRAVITY_ROOT")
    if env_root:
        candidate_roots.append(Path(env_root))
    candidate_roots.append(Path.home() / ".gemini" / "antigravity")
    if sys.platform == "win32" or os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidate_roots.append(Path(local_app_data) / "Programs" / "antigravity")
        app_data = os.environ.get("APPDATA")
        if app_data:
            candidate_roots.append(Path(app_data) / "Antigravity")

    latest_mtime = None
    found_any = False

    for root in candidate_roots:
        candidates = [
            root / "conversations" / f"{conversation_id}.db",
            root / "brain" / conversation_id / ".system_generated" / "logs" / "transcript.jsonl",
            root / "brain" / conversation_id / ".system_generated" / "logs" / "transcript_full.jsonl",
            root / "brain" / conversation_id / "transcript.jsonl",
            root / "brain" / conversation_id / f"{conversation_id}.db",
        ]
        for p in candidates:
            if p.exists():
                found_any = True
                try:
                    mtime = p.stat().st_mtime
                    if latest_mtime is None or mtime > latest_mtime:
                        latest_mtime = mtime
                except OSError:
                    pass

    if not found_any or latest_mtime is None:
        return False, None

    baseline_ts = None
    if last_activity_ts is not None:
        if isinstance(last_activity_ts, (int, float)):
            baseline_ts = float(last_activity_ts)
        elif isinstance(last_activity_ts, str):
            try:
                baseline_ts = datetime.fromisoformat(last_activity_ts.replace("Z", "+00:00")).timestamp()
            except Exception:
                baseline_ts = None

    if baseline_ts is not None:
        has_progress = (latest_mtime - baseline_ts) > 0.001
        if has_progress:
            _CONVERSATION_PROGRESS_CACHE[conversation_id] = latest_mtime
        return has_progress, latest_mtime

    cached_ts = _CONVERSATION_PROGRESS_CACHE.get(conversation_id)
    if cached_ts is not None:
        has_progress = (latest_mtime - cached_ts) > 0.001
        if has_progress:
            _CONVERSATION_PROGRESS_CACHE[conversation_id] = latest_mtime
        return has_progress, latest_mtime

    _CONVERSATION_PROGRESS_CACHE[conversation_id] = latest_mtime
    return False, latest_mtime


def _audit_safe_value(value):
    """Recursively omit credential and prompt fields before writing audit data."""
    if isinstance(value, dict):
        return {
            key: _audit_safe_value(item)
            for key, item in value.items()
            if not re.search(r"private.?key|askpass|prompt|secret|password", str(key), re.IGNORECASE)
            and str(key).lower() not in {
                "gh_token", "github_app_token", "github_token", "access_token", "refresh_token", "token"
            }
        }
    if isinstance(value, list):
        return [_audit_safe_value(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(gho|ghu|ghs)_[A-Za-z0-9_]+", "[REDACTED]", value)
        return re.sub(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED]", value)
    return value


def append_dispatch_audit(record):
    """Durably append one secret-free event to the sidecar-owned JSONL journal."""
    safe_record = _audit_safe_value(record)
    DISPATCH_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DISPATCH_AUDIT_PATH, "a", encoding="utf-8", newline="\n") as audit_file:
        audit_file.write(json.dumps(safe_record, ensure_ascii=False, sort_keys=True) + "\n")
        audit_file.flush()
        os.fsync(audit_file.fileno())


def run_cmd(cmd_list, cwd=EASYEXAM_REPO_PATH, timeout=GITHUB_TIMEOUT_SECONDS, env=None):
    """
    Run an external command safely using argv list (shell=False).
    Returns (returncode, stdout, stderr, timed_out); credential values are redacted.
    """
    try:
        proc = subprocess.run(
            cmd_list,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
        )
        return proc.returncode, _redact_secrets(proc.stdout, env), _redact_secrets(proc.stderr, env), False
    except subprocess.TimeoutExpired as exc:
        stdout = _redact_secrets(exc.stdout, env)
        error_msg = f"Command timed out after {timeout}s: {' '.join(cmd_list[:3])}"
        logger.error(error_msg)
        return -1, stdout, error_msg, True
    except Exception as exc:
        error_msg = _redact_secrets(exc, env)
        logger.error(f"Command execution error: {error_msg}")
        return -1, "", error_msg, False


def get_open_issues(repo):
    """Query open issues with their labels and status using gh CLI."""
    gh_bin = shutil.which("gh") or "gh"
    cmd = [gh_bin, "issue", "list", "--repo", repo, "--state", "open", "--json", "number,title,labels,state"]
    code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
    if code != 0 or timed_out:
        logger.error(f"Failed to fetch open issues from GitHub: {stderr}")
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse JSON response from gh CLI: {exc}")
        return None


def get_issue_details(repo, issue_number):
    """Fetch current details of a specific issue to verify eligibility."""
    gh_bin = shutil.which("gh") or "gh"
    cmd = [gh_bin, "issue", "view", str(issue_number), "--repo", repo, "--json", "number,title,labels,state"]
    code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
    if code != 0 or timed_out:
        logger.error(f"Failed to view issue #{issue_number}: {stderr}")
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse JSON for issue #{issue_number}: {exc}")
        return None


def record_claim_failure(issue_number: int, reason: str, base_backoff: float = 30.0, max_backoff: float = 300.0) -> float:
    """Record a claim failure for an issue and return the backoff duration in seconds."""
    entry = CLAIM_BACKOFF_MAP.get(int(issue_number), {"failures": 0, "next_retry": 0.0, "reason": ""})
    failures = entry["failures"] + 1
    duration = min(max_backoff, base_backoff * (2 ** (failures - 1)))
    next_retry = time.time() + duration
    CLAIM_BACKOFF_MAP[int(issue_number)] = {
        "failures": failures,
        "next_retry": next_retry,
        "reason": str(reason),
    }
    logger.warning(
        f"Claim backoff for Issue #{issue_number}: failure #{failures}, backing off {duration:.1f}s. Reason: {reason}"
    )
    return duration


def is_in_claim_backoff(issue_number: int) -> tuple[bool, float]:
    """Check if an issue is currently within its claim failure backoff window."""
    entry = CLAIM_BACKOFF_MAP.get(int(issue_number))
    if not entry:
        return False, 0.0
    remaining = entry["next_retry"] - time.time()
    if remaining > 0:
        return True, remaining
    return False, 0.0


def reset_claim_backoff(issue_number: int):
    """Clear claim backoff tracking for an issue upon successful transition."""
    CLAIM_BACKOFF_MAP.pop(int(issue_number), None)


def execute_coordination_write(args: list[str], repo: str = EASYEXAM_REPO, timeout: int = GITHUB_TIMEOUT_SECONDS):
    """
    Execute a coordination-plane write using the dedicated GitHub App executor.
    Does NOT use ordinary guarded gh from PATH.
    """
    if not APP_GH_EXECUTOR.is_file():
        logger.error(f"App gh executor not found at: {APP_GH_EXECUTOR}")
        return -1, "", "app_gh_executor_not_found", False

    cmd = [sys.executable, str(APP_GH_EXECUTOR)] + args
    return run_cmd(cmd, timeout=timeout)


def cas_transition_coordination_state(
    repo: str,
    issue_number: int,
    expected_state: str,
    target_state: str,
) -> tuple[bool, str]:
    """
    Strict Compare-And-Set (CAS) transition for coordination labels.
    Guarantees:
    1. Fresh pre-read of current issue state.
    2. Validates expected_state is present in current coordination labels.
    3. Validates target_state is NOT already present.
    4. Validates no blocking labels (infra-blocked / needs-human) are present unexpectedly.
    5. Deterministic label removal and addition using coordination write executor.
    6. Post-write verification to confirm mutual exclusivity and target state presence.
    Returns (success: bool, reason_category: str).
    """
    if expected_state not in COORDINATION_LABELS or target_state not in COORDINATION_LABELS:
        return False, "invalid_coordination_labels"
    if expected_state == target_state:
        return False, "identity_transition_prohibited"

    # Step 1: Fresh read
    details = get_issue_details(repo, issue_number)
    if not details or details.get("state") != "OPEN":
        return False, "issue_not_open_or_missing"

    current_labels = {
        l.get("name") if isinstance(l, dict) else str(l)
        for l in details.get("labels", [])
    }

    # Step 2: Check target already present
    if target_state in current_labels:
        logger.warning(
            f"CAS ABORT for Issue #{issue_number}: target state '{target_state}' already present in labels: {current_labels}"
        )
        return False, "target_already_present"

    # Step 3: Validate expected state
    if expected_state not in current_labels:
        logger.warning(
            f"CAS ABORT for Issue #{issue_number}: expected '{expected_state}' not found in current labels: {current_labels}"
        )
        return False, "stale_expected_state"

    # Step 4: Check blocking labels
    blocking = {"infra-blocked", "needs-human"} - {expected_state, target_state}
    found_blocking = blocking.intersection(current_labels)
    if found_blocking:
        logger.warning(
            f"CAS ABORT for Issue #{issue_number}: blocking label(s) {found_blocking} present in labels: {current_labels}"
        )
        return False, "blocking_label_present"

    # Step 5: Deterministic label replacement using coordination executor
    cmd_edit = [
        "issue",
        "edit",
        str(issue_number),
        "--repo",
        repo,
        "--remove-label",
        expected_state,
        "--add-label",
        target_state,
    ]
    code, stdout, stderr, timed_out = execute_coordination_write(cmd_edit, repo=repo)
    if code != 0 or timed_out:
        logger.error(
            f"CAS WRITE FAILED for Issue #{issue_number} (-{expected_state}, +{target_state}): {stderr}"
        )
        return False, "github_write_failed"

    # Step 6: Post-write verification
    verified_details = get_issue_details(repo, issue_number)
    if not verified_details:
        logger.error(f"CAS POST-VERIFY FAILED: Could not read #{issue_number} after write")
        return False, "post_verify_read_failed"

    verified_labels = {
        l.get("name") if isinstance(l, dict) else str(l)
        for l in verified_details.get("labels", [])
    }
    if target_state not in verified_labels or expected_state in verified_labels:
        logger.error(
            f"CAS POST-VERIFY MISMATCH for #{issue_number}: expected +{target_state} -{expected_state}, found {verified_labels}"
        )
        return False, "post_verify_label_mismatch"

    logger.info(
        f"CAS transition SUCCESS for Issue #{issue_number}: {expected_state} -> {target_state}"
    )
    return True, "transition_succeeded"


def set_issue_labels(repo, issue_number, remove_label, add_label):
    """
    Perform claim transition on GitHub issue: remove source label and add destination label.
    Delegates to strict CAS transition.
    """
    ok, _ = cas_transition_coordination_state(repo, issue_number, remove_label, add_label)
    return ok


def fail_closed_to_infra_blocked(repo, issue_number, reason, attempt_id=None):
    """
    Fail-closed policy: Switch issue from agent-working to infra-blocked.
    Prevents duplicate Agent dispatch and requires human intervention to unblock.
    """
    category = str(reason or "dispatch_unconfirmed")
    if not re.fullmatch(r"[a-z0-9_]{1,64}", category):
        category = "dispatch_unconfirmed"
    logger.critical(
        f"Entering fail-closed: switching #{issue_number} from agent-working to infra-blocked. Category: {category}"
    )

    details = get_issue_details(repo, issue_number)
    labels = {
        l.get("name") if isinstance(l, dict) else str(l)
        for l in (details or {}).get("labels", [])
    }
    if details is not None and "infra-blocked" in labels and "agent-working" not in labels:
        label_ok = True
    else:
        cmd_edit = [
            "issue",
            "edit",
            str(issue_number),
            "--repo",
            repo,
            "--remove-label",
            "agent-working",
            "--add-label",
            "infra-blocked",
        ]
        code, _, stderr, timed_out = execute_coordination_write(cmd_edit, repo=repo)
        label_ok = code == 0 and not timed_out
        if not label_ok:
            logger.critical(f"Failed to label #{issue_number} as infra-blocked: {stderr}")

    marker = f"<!-- easyexam-dispatch-attempt:{attempt_id} -->" if attempt_id else None
    comment_body = (
        f"**[EasyExam Dispatcher Fail-Closed Alert]**\n\n"
        f"Agent dispatch failed or could not be verified:\n"
        f"- Reason category: `{category}`\n"
        f"- Target coordination state: `infra-blocked`.\n"
        f"Please check Antigravity agent logs and remove `infra-blocked` manually after resolving."
    )
    gh_bin = shutil.which("gh") or "gh"
    if marker:
        comment_body += f"\n\n{marker}"
        cmd_find_comment = [
            gh_bin,
            "api",
            f"repos/{repo}/issues/{issue_number}/comments",
            "--paginate",
            "--jq",
            f'.[] | select((.body // "") | contains("{marker}")) | .id',
        ]
        find_code, found, _, find_timeout = run_cmd(cmd_find_comment, timeout=GITHUB_TIMEOUT_SECONDS)
        comment_ok = find_code == 0 and not find_timeout and bool(found.strip())
    else:
        comment_ok = False

    if not comment_ok:
        cmd_comment = [
            "issue",
            "comment",
            str(issue_number),
            "--repo",
            repo,
            "--body",
            comment_body,
        ]
        comment_code, _, _, comment_timeout = execute_coordination_write(cmd_comment, repo=repo)
        comment_ok = comment_code == 0 and not comment_timeout
    return label_ok and comment_ok


def _build_recovery_prompt(repo, repo_path, issue_number, issue_title, source_label, spec):
    """Construct deterministic recovery prompt for authorized recovery jobs."""
    allowed_files_lines = "\n".join(f"- {f}" for f in spec.allowed_changed_files)
    prompt = f"""工作目录：{repo_path}

你是 EasyExam 的 Implementer Agent。

仓库：
{repo}

目标任务：
Issue #{issue_number}: {issue_title}
触发来源：{source_label}
协调状态：dispatcher 已将协调状态切换为 agent-working。
执行模式：RECOVERY (受控恢复模式)

====================================================
【核心指令】THIS IS A RECOVERY TASK, NOT AN IMPLEMENTATION TASK.
====================================================

这是一次受控凭证边界恢复任务（Recovery Task），绝对不是普通实现任务！
Human Architect 已经授权对 Issue #{issue_number} 执行 exact preserved commit 恢复。
Recovery must reuse the preserved implementation commit exactly. No reimplementation or product-code changes are authorized.

Preserved implementation SHA: {spec.preserved_sha}
Target recovery branch: {spec.recovery_branch}

====================
一、凭证边界与 GitHub 写入规则（红线）
====================

GitHub writes:
- NEVER use ordinary gh for writes
- NEVER use ordinary git push
- use app-gh
- use app-git-push

严禁使用普通 git push！
严禁使用普通 gh pr create / gh pr merge！
严禁使用普通 gh 进行任何写入操作（pr create/edit/merge, issue create/edit/comment, api write 等）！
严禁使用 host human 凭据 (liuchangchxy) 进行任何写操作！

Agent 终端环境已配置 FAIL-CLOSED 机械拦截 (mechanically blocked)：
- 普通 git push 会被 git shim 机械阻断；
- 普通 gh 写操作会被 gh shim 机械阻断；
- 只有 app-gh 和 app-git-push 才能写。

所有 Implementer GitHub 写操作必须显式调用受控 wrapper：
- Git Push: 必须使用 app-git-push (或 python {APP_GIT_PUSH_EXECUTOR})
- PR 创建: 必须使用 app-gh (或 python {APP_GH_EXECUTOR})

普通只读命令（git status, git diff, git log, git rev-parse, git cat-file, gh pr view, gh issue view）直接在本地执行。

====================
二、Preserved SHA 与 Diff 验证（必须首先执行）
====================

在开始任何分支或推送操作前，必须进行严格本地验证：

1. 验证 Preserved SHA 存在：
   执行：
   git rev-parse {spec.preserved_sha}
   git cat-file -e {spec.preserved_sha}^{{commit}}
   确认 commit 对象在本地仓库中完整存在。

2. 验证 Exact Diff 严格受限：
   检查 preserved commit 相对其 parent 所修改的文件：
   git show --name-only --format="" {spec.preserved_sha}
   或者：
   git diff --name-only {spec.preserved_sha}~1 {spec.preserved_sha}
   必须且仅允许包含以下文件：
{allowed_files_lines}
   如果包含任何其他文件，或者修改范围超出上述两文件限制：
   立即 STOP 并报告 blocker！

====================
三、严禁重新实现与严禁修改产品代码 (No Reimplementation)
====================

- 严禁重新实现任何业务逻辑或测试逻辑！
- 不修改上述允许文件
- 不重新编辑 fixture ({spec.allowed_changed_files[1]})
- 不重新编辑 suite ({spec.allowed_changed_files[0]})
- 不做任何“顺手修复”
- 不格式化
- 不更新 dependency
- 不修改 workflow
- 不修改 docs
- 绝对不触碰 EasyExam 产品代码！

如果发现测试不通过或需要修改代码才能继续：
立即 STOP 并报告 blocker，严禁自行修改代码或重新实现！

====================
四、Recovery Branch 准备（零新 Commit）
====================

必须使用指定的 recovery branch：
{spec.recovery_branch}

分支创建规则：
1. 必须从 exact preserved SHA 创建：
   git checkout -B {spec.recovery_branch} {spec.preserved_sha}
2. 验证 recovery branch HEAD 必须严格等于 preserved SHA：
   git rev-parse HEAD
   HEAD 必须是 {spec.preserved_sha}。
3. 【红线】Do not create any new implementation commit.
   - 不 cherry-pick 出新 SHA
   - 不 amend
   - 不 rebase
   - 不 merge
   - 不 squash
   - 不 recommit
   目标必须是同一个 commit object ({spec.preserved_sha})，绝对不是“内容等价的新 commit”。
   如果 recovery branch head 与 preserved SHA 不一致：立即 STOP！

【不要信任旧 branch 状态】：
已有旧 branch (agent/issue-4-self-contained-mobile-e2e) 来自 invalid credential chain。
可以进行只读检查，但绝对不得将其作为最终 recovery branch。
Recovery branch 必须且只能是 {spec.recovery_branch}，其 head 必须是 {spec.preserved_sha}。

====================
五、受控 App-Authenticated Push (指定 Expected SHA)
====================

必须使用 app-git-push 将 recovery branch 推送到 remote：
命令格式（--expected-sha 为强制必填项）：
app-git-push --branch {spec.recovery_branch} --expected-sha {spec.preserved_sha}
或者：
python {APP_GIT_PUSH_EXECUTOR} --branch {spec.recovery_branch} --expected-sha {spec.preserved_sha}

严禁：
- 使用普通 git push
- 更改 --expected-sha 参数
- push 到其他 repo 或其他 implementation branch

推送后必须立即验证 remote branch SHA：
git ls-remote origin refs/heads/{spec.recovery_branch}
确认 remote branch 的 SHA 严格等于 {spec.preserved_sha}。
如果 remote SHA 不匹配：立即 STOP！

====================
六、使用 app-gh 创建 Bot-Authored Replacement PR
====================

必须使用 app-gh 创建 replacement PR（严禁使用普通 gh pr create）：
PR 配置要求：
- base: main
- head: {spec.recovery_branch}
- 必须包含关键关闭/关联词：
  Closes #{issue_number}
  Relates #1
- 正文必须明确说明：
  - replacement for invalid-identity PR #14
  - credential-boundary recovery
  - implementation itself unchanged
  - preserved SHA reused exactly ({spec.preserved_sha})
  - original PR #14 invalid because it used Human identity
  - 严禁引用旧 PR #14 中错误的 #5 描述！

命令示例：
app-gh pr create --base main --head {spec.recovery_branch} --title "Infrastructure Phase 3A: Make Mobile Interaction E2E self-contained (bot replacement)" --body "Closes #{issue_number}\\nRelates #1\\n\\nThis PR is a credential-boundary recovery replacement for PR #14.\\nThe original PR #14 was invalid because it was authored using Human identity instead of GitHub App Bot identity.\\nThe implementation itself is completely unchanged, reusing preserved implementation commit {spec.preserved_sha} exactly."

====================
七、PR 身份回读校验 (Identity Validation)
====================

PR 创建后，Implementer 必须立即通过 GitHub REST canonical endpoint 回读 PR author 身份：
GET /repos/liuchangchxy/easy-exam/pulls/<PR_NUMBER>

只使用响应中的 `pull_request.user.login` 与 `pull_request.user.type` 作为身份判定字段。
必须严格验证以下条件：
- `pull_request.user.login == chang-implementer[bot]`
- `pull_request.user.type == Bot`

例如 `gh pr view --json author` 可能将 GitHub App 显示为 `app/chang-implementer`；
GraphQL / CLI 的 actor 表示仅作辅助记录，不能覆盖或替代 REST canonical author 字段。
若 REST canonical 字段不满足以上两个条件：
立即 STOP 并报告 blocker！
不得关闭 #{issue_number}！不得 merge！

====================
八、Recovery 成功与停止标准
====================

本次 Recovery 对话成功仅代表满足以下全部 7 项条件：
1. preserved SHA verified
2. diff verified
3. exact branch created
4. App-authenticated push succeeded
5. remote SHA exact match
6. Bot-authored replacement PR created
7. PR CI triggered

一旦上述 7 项完成：立即停止！
- 不要等待 Architect Review
- 不要 merge
- 不要关闭 Issue #{issue_number}

====================
九、Recovery 失败与阻断条件 (STOP Conditions)
====================

若出现以下任一情况，必须立即 STOP 并输出 BLOCKER 报告：
- preserved SHA 不存在
- preserved diff 不符合两文件限制 ({', '.join(spec.allowed_changed_files)})
- branch head 不是 preserved SHA ({spec.preserved_sha})
- branch 已存在但 SHA 冲突
- app-git-push 失败
- remote SHA mismatch
- app-gh 失败
- REST canonical PR author 无效 (`pull_request.user.type != Bot` 或 `pull_request.user.login != chang-implementer[bot]`)
- 需要修改实现代码才能继续
严禁自行尝试“修复”或变通绕过！

====================
十、最终输出
====================

执行结束只输出：
STATUS: [SUCCESS | BLOCKED]
MODE: RECOVERY
ISSUE: #{issue_number}
PRESERVED_SHA: {spec.preserved_sha}
RECOVERY_BRANCH: {spec.recovery_branch}
PR: <PR_URL or NONE>
PR_ACTOR: <ACTOR>
BLOCKERS: <NONE or REASON>
NEXT_ACTION:
"""
    return prompt.strip()


def _build_issue_4_repair_prompt(repo, repo_path, issue_number, issue_title, source_label, spec=None):
    """Construct deterministic REQUEST_CHANGES repair prompt for Issue #4 / PR #15."""
    target_pr = 15
    target_branch = "agent/issue-4-self-contained-mobile-e2e-bot"
    reviewed_sha = "4428ef14bffd0bf94fc28bff508e7be5ec2a30f0"
    allowed_file = "frontend/tests/mobile_interaction_suite.mjs"

    prompt = f"""工作目录：{repo_path}

你是 EasyExam 的 Implementer Agent。

仓库：
{repo}

目标任务：
Issue #{issue_number}: {issue_title}
触发来源：{source_label}
协调状态：dispatcher 已将协调状态切换为 agent-working。
执行模式：REQUEST_CHANGES REPAIR (正式审查修改模式)

目标 PR：PR #{target_pr}
目标分支：{target_branch}
审查基线 SHA：{reviewed_sha}

====================================================
【核心指令】THIS IS A FORMAL REQUEST_CHANGES REPAIR, NOT A RECOVERY REPLACEMENT.
====================================================

这是针对 PR #{target_pr} 最新正式原生 REQUEST_CHANGES 审查的受控修复任务（Repair Task）！
Architect (liuchangchxy) 已在 PR #{target_pr} 审查基线 SHA {reviewed_sha} 上提交了正式 REQUEST_CHANGES。
PR #{target_pr} 是合法的 GitHub App Bot PR (`pull_request.user.login == chang-implementer[bot]`, `pull_request.user.type == Bot`)。

绝对禁止以下行为：
- 严禁关闭 PR #{target_pr}！
- 严禁创建新 PR (例如 #{target_pr + 1})！
- 严禁重新创建 recovery 分支或强制覆盖！
- 严禁重新走 recovery replacement 流程！
必须直接在现有 PR #{target_pr} 分支 `{target_branch}` 上修复唯一 blocker。

====================
一、唯一授权实现修改 (Repair Scope)
====================

本次修复有且仅有一个授权修改点（Frozen Spec 验收标准 1 / Architect Formal Review Blocker）：
在 `{allowed_file}` 中：
删除 CHROME_PATH 环境变量覆盖逻辑：
```js
...(process.env.CHROME_PATH
  ? {{ executablePath: process.env.CHROME_PATH }}
  : {{}}),
```
使 Chromium 启动恢复为仅使用 package-lock 安装的 Playwright-managed Chromium，语义上：
```js
browser = await chromium.launch({{
  headless: true,
}})
```
不得传递或使用任何机器级 Chrome executablePath！

====================
二、严禁任何其他实现修改 (Strict Negative Scope)
====================

为确保最小变更与确定性，严禁以下任何修改：
- 严禁修改 fixture 题目 (frontend/tests/fixtures/mobile_interaction_questions.md)；
- 严禁修改 import 逻辑；
- 严禁修改 11 个测试断言；
- 严禁修改 threshold；
- 严禁修改 EasyExam 产品代码 (backend, frontend/src 等)；
- 严禁修改 backend；
- 严禁修改 workflow；
- 严禁修改 package dependencies / package-lock.json；
- 严禁修改 docs；
- 严禁修改任何其它文件！

预期 repair diff：
只修改 `{allowed_file}`，且只删除 CHROME_PATH override 相关代码。

====================
三、允许创建新 Repair Commit
====================

与初始 recovery 流程（要求零新 commit）不同：
本次正式 REQUEST_CHANGES repair 允许创建一个新的 repair commit！
操作要求：
1. 本地检出 PR #{target_pr} 所在分支：
   git checkout {target_branch}
2. 确认当前基线 HEAD 为 {reviewed_sha}：
   git rev-parse HEAD
   若本地不一致，拉取或重置到 {reviewed_sha}。
3. 执行唯一授权修改（仅修改 `{allowed_file}`）。
4. 本地运行测试验证：
   node frontend/tests/mobile_interaction_suite.mjs
   确认 11 个断言全部通过。
5. 创建新的 repair commit：
   git add {allowed_file}
   git commit -m "fix(test): remove CHROME_PATH override to enforce lockfile Playwright Chromium"
6. 记录新 commit SHA：
   NEW_REPAIR_SHA=$(git rev-parse HEAD)

====================
四、受控 App-Authenticated Push (绑定新 Commit SHA)
====================

GitHub writes:
- NEVER use ordinary gh for writes
- NEVER use ordinary git push
- use app-gh
- use app-git-push

严禁使用普通 git push！
严禁使用普通 gh 进行任何写操作！
Agent 终端环境已配置 FAIL-CLOSED 机械拦截 (mechanically blocked)。

所有 Implementer 推送必须使用受控 wrapper：
- Git Push: 必须使用 app-git-push (或 python {APP_GIT_PUSH_EXECUTOR})
- 必须将 --expected-sha 绑定到【新 repair commit SHA】（而不是旧 preserved SHA）：
  app-git-push --branch {target_branch} --expected-sha <NEW_REPAIR_SHA>
  或者：
  python {APP_GIT_PUSH_EXECUTOR} --branch {target_branch} --expected-sha <NEW_REPAIR_SHA>

推送后验证 remote branch SHA：
git ls-remote origin refs/heads/{target_branch}
确认 remote SHA 与新 commit SHA 完全一致。

====================
五、PR 状态与身份回读（无需新建 PR）
====================

PR #{target_pr} 已经合法存在，不得新建 PR！
推送完成后，通过 GitHub REST canonical endpoint 验证 PR #{target_pr}：
GET /repos/{repo}/pulls/{target_pr}

验证：
1. PR 状态仍为 open。
2. PR head ref 仍为 `{target_branch}`。
3. PR head sha 已更新为新 repair commit SHA。
4. PR canonical author 仍为：
   - pull_request.user.login == chang-implementer[bot]
   - pull_request.user.type == Bot
（辅助显示如 `app/chang-implementer` 不得覆盖 canonical REST 判定）。

====================
六、新 CI 运行等待与验证
====================

新 repair commit 推送后，必须在 GitHub Actions 触发新的 `pull_request` CI run。
旧 CI run (如 37267571349) 仅证明旧 SHA {reviewed_sha}。
新 repair 必须等待并核验对应于新 head SHA 的新 CI run，不能复用旧 success。

====================
七、正式 Review 轮次完成与停止
====================

这是第 1 轮 native REQUEST_CHANGES formal round。
一旦新 commit 推送成功、PR #{target_pr} head 更新已验证、新 CI 运行触发/验证完成：
立即 STOP！
由 Work / Architect 对新 SHA 进行正式审查。
严禁自行 APPROVE！严禁 merge！严禁关闭 Issue #{issue_number}！严禁启动后续 Issue！

====================
八、最终输出
====================

执行结束只输出：
STATUS: [SUCCESS | BLOCKED]
MODE: REQUEST_CHANGES_REPAIR
ISSUE: #{issue_number}
PR: #{target_pr}
BRANCH: {target_branch}
BASE_SHA: {reviewed_sha}
NEW_HEAD_SHA: <NEW_SHA>
CI_RUN: <CI_RUN_ID or TRIGGERED>
BLOCKERS: <NONE or REASON>
NEXT_ACTION: Hand back to Work / Architect for formal review of new SHA.
"""
    return prompt.strip()


def build_repair_contract_section(repair_ordinal: int, cause_type: str = "changes_requested", failure_detail: dict = None) -> str:
    """
    Construct hardened repair contract section for repair prompts matching Frozen Spec Section 7.
    Enforces:
    - Review finding / CI finding = minimum known defect, not maximum repair scope.
    - 6 mandatory repair rules (root cause, adjacent invariants, sibling paths, prior reviews, no regressions, reachability audit).
    - Repair escalation intensity (Repair #1, #2, #3).
    - MAX_AUTOMATED_REPAIRS = 3 budget reminder.
    """
    ordinal = max(1, int(repair_ordinal or 1))
    if ordinal == 1:
        intensity_title = "Repair #1 升级强度要求（Root Cause & Adjacent Invariants）"
        intensity_scope = (
            "- 必须深入排查根本原因（Root Cause），严禁停留于表面 symptom；\n"
            "- 全面核查直接相邻的 Frozen Spec 不变量（Directly adjacent invariants）；\n"
            "- 严禁仅修改 Reviewer/CI 报错行。"
        )
    elif ordinal == 2:
        intensity_title = "Repair #2 升级强度要求（Affected Subsystem Exhaustive Audit）"
        intensity_scope = (
            "- 对受影响子系统（Affected subsystem）进行穷尽式全路径审计；\n"
            "- 核查所有兄弟生产路径（Sibling production paths）、状态生产/消费闭环；\n"
            "- 必须严格回读并验证所有历史 Review findings，防止多轮修复自相矛盾。"
        )
    else:
        intensity_title = "Repair #3 升级强度要求（Last-Chance Full Frozen Spec Acceptance Matrix）"
        intensity_scope = (
            "- 这是最后一次自动化修复机会（MAX_AUTOMATED_REPAIRS = 3，绝无 Repair #4）；\n"
            "- 针对所有受重大影响的 Closure requirements 重新生成完整的验收矩阵；\n"
            "- 逐条核验 requirement -> production evidence -> test evidence，确保终局收敛。"
        )

    finding_name = "CI failure finding" if cause_type == "ci_failure" else "Review finding"
    detail_line = ""
    if failure_detail:
        detail_name = failure_detail.get("name") or failure_detail.get("title") or failure_detail.get("id") or ""
        if detail_name:
            detail_line = f"当前点名缺陷信息：`{detail_name}`\n"

    return f"""====================================================
【强制修复契约】FROZEN SPEC REPAIR CONTRACT (ROUND #{ordinal})
====================================================

【核心审计原则】：
{finding_name} = minimum known defect, not maximum repair scope.
Reviewer / CI 反馈是指出的最低已知缺陷，绝不是完整修复范围的上限！
{detail_line}
每次修复必须严格满足以下 6 项要求：
1. 深入排查并根治 Root Cause，严禁停留于表面 symptom 掩盖；
2. 检查相邻 Frozen Spec requirements，确保边缘情况与相邻语义完全一致；
3. 检查所有兄弟生产路径（sibling production paths），消除同类缺陷或遗留假实现；
4. 完整读取并核验所有 prior Review findings，确保不破坏前几轮的修复成果；
5. 不允许修复当前点同时破坏前一轮修复（Zero Regressions across all prior rounds）；
6. 在 push 前必须完成 production caller / state reachability 审计，确保所有生产状态与方法具备真实调用路径。

====================
{intensity_title}
====================
{intensity_scope}

【预算与阻断红线】：
- 当前统一自动化修复预算为 MAX_AUTOMATED_REPAIRS = 3。
- 当前轮次：Repair #{ordinal}。
- 绝无 Repair #4。若本轮未能根治或超出预算，必须 fail-closed 切换至 needs-human。"""


def render_dispatch_prompt(
    issue,
    issue_title=None,
    source_label="agent-ready",
    repo=None,
    repo_path=None,
    repair_ordinal=0,
    repair_kind=None,
    failure_detail=None,
):
    """
    Render dispatch prompt for an issue without changing labels, claiming, or launching an agent.
    Accepts either an issue dict or an integer issue number.
    Uses the exact same production prompt builder as dispatch_agent.
    """
    repo = repo or EASYEXAM_REPO
    repo_path = repo_path or EASYEXAM_REPO_PATH
    if isinstance(issue, dict):
        issue_number = issue.get("number")
        title = issue.get("title", issue_title or "")
        label_names = {l.get("name") if isinstance(l, dict) else str(l) for l in issue.get("labels", [])}
        src_label = "changes-requested" if "changes-requested" in label_names else "agent-ready"
    else:
        issue_number = int(issue)
        title = issue_title or f"Issue #{issue_number}"
        src_label = source_label
    return build_implementer_prompt(
        repo,
        repo_path,
        issue_number,
        title,
        src_label,
        repair_ordinal=repair_ordinal,
        repair_kind=repair_kind,
        failure_detail=failure_detail,
    )


def build_implementer_prompt(
    repo,
    repo_path,
    issue_number,
    issue_title,
    source_label,
    repair_ordinal=0,
    repair_kind=None,
    failure_detail=None,
):
    """Construct complete Implementer prompt for agentapi new-conversation."""
    recovery_spec = get_recovery_spec(issue_number)
    if recovery_spec is not None:
        if source_label == "changes-requested":
            return _build_issue_4_repair_prompt(
                repo, repo_path, issue_number, issue_title, source_label, recovery_spec
            )
        return _build_recovery_prompt(
            repo, repo_path, issue_number, issue_title, source_label, recovery_spec
        )

    repair_section = ""
    is_repair = source_label in ("changes-requested", "ci-repair") or repair_ordinal > 0
    if is_repair:
        repair_section = "\n\n" + build_repair_contract_section(
            repair_ordinal=repair_ordinal or 1,
            cause_type="ci_failure" if (source_label == "ci-repair" or repair_kind == "ci_repair") else "changes_requested",
            failure_detail=failure_detail,
        )

    review_context = (
        f"本次触发来源为 changes-requested。\n"
        f"请在开始前完整读取 Issue #{issue_number} 及其关联 PR 最新正式 CHANGES_REQUESTED Review，\n"
        f"只处理其中与 Frozen Spec 直接相关的事项。"
        if source_label == "changes-requested"
        else f"本次触发来源为 ci-repair。\n"
        f"请在开始前完整读取 Issue #{issue_number} 及其关联 PR 失败的 CI Check Runs，\n"
        f"只修复与本次实现相关的代码/测试缺陷。"
        if source_label == "ci-repair"
        else f"本次触发来源为 agent-ready。\n"
        f"请在开始前完整读取 Issue #{issue_number} 的正文及 Frozen Spec。"
    )

    prompt = f"""工作目录：{repo_path}

你是 EasyExam 的 Implementer Agent。

仓库：
{repo}

目标任务：
Issue #{issue_number}: {issue_title}
触发来源：{source_label}
协调状态：dispatcher 已将协调状态切换为 agent-working。

{review_context}{repair_section}

你的唯一职责是实现 GitHub 中已经冻结并明确交给你的任务。
GitHub Issue、PR、Labels、Checks 是唯一事实源。
不得根据聊天记忆、自己的想法或历史任务扩大需求。

每次运行按以下协议执行。

====================
一、仓库与 GitHub 预检
====================

1. 确认当前目录属于 EasyExam 仓库。
2. 确认 remote 指向 {repo}。
3. 确认 gh 已认证。
4. 如果本地存在无法解释的未提交改动：
   - 不覆盖；
   - 不自动清理；
   - 不继续实现；
   - 输出 LOCAL_WORKTREE_DIRTY 并停止。

====================
二、任务资格检查
====================

完整读取 Issue #{issue_number}：
- Issue 正文
- labels
- 父 Issue / 关联 Issue
- 当前关联 PR（如有）
- 最新正式 Review（如有）

只有满足以下条件才能执行：
1. Issue 有 frozen-spec。
2. Frozen Spec 足够明确。
3. 没有 infra-blocked 或 needs-human。
4. 当前要求不存在明显自相矛盾。

如果不满足：
不要修改代码。
记录原因。
需要人工判断时将 Issue 标签转 needs-human 并停止。
不得自行补全、重新定义或扩大 Frozen Spec。

====================
三、领取与分支准备
====================

若来源为 agent-ready：
- 创建独立 feature branch：
  agent/issue-{issue_number}-<short-slug>
- 不得直接修改 main。

若来源为 changes-requested：
- 找到该 Issue 已有关联 PR 和 branch。
- 只处理最新正式 CHANGES_REQUESTED Review 中与 Frozen Spec 直接相关的事项。
- 不创建重复 PR。

====================
四、实现规则
====================

实现必须严格受 Frozen Spec 限制。

禁止：
- 顺手重构范围外代码；
- 增加新功能；
- 改产品行为，除非 Frozen Spec 明确要求；
- 删除或放宽测试断言来获得全绿；
- 将 skipped / 未运行 / 失败报告为通过；
- 修改 Issue 的验收标准；
- 修改父 Frozen Spec；
- 自动解除 infra-blocked 或 needs-human。

发现范围外问题：
- 不在当前 PR 修复；
- 创建或建议 follow-up Issue；
- 当前任务继续按原 Frozen Spec 收敛。

====================
五、测试
====================

运行 Frozen Spec 要求的测试。

必须如实记录：
- 实际运行命令；
- PASS；
- FAIL；
- SKIPPED；
- NOT RUN；
- 环境原因。

不得把低层测试冒充高层验收。

如果失败属于当前实现缺陷：
修复后重跑。

如果属于环境/基础设施且无法在当前任务解决：
不要修改业务代码规避。
记录证据并在 Issue 上转 infra-blocked，然后停止。

====================
六、提交与 PR（强制 GitHub App 凭据边界）
====================

【严格红线】：
Git commit author metadata is NOT authentication evidence.
GitHub identity proof strictly comes from App-authenticated API,
App-authenticated push chain, or PR actor.
Do NOT rely on git author user.name/email for authentication.

GitHub writes:
- NEVER use ordinary gh for writes
- NEVER use ordinary git push
- use app-gh
- use app-git-push

严禁使用普通 git push！
严禁使用普通 gh pr create / gh pr merge！
严禁使用普通 gh 进行任何写入操作（pr create/edit/merge, issue create/edit/comment, api write 等）！
严禁使用 host human 凭据 (liuchangchxy) 进行任何写操作！

Agent 终端环境已配置 FAIL-CLOSED 机械拦截 (mechanically blocked)：
- 普通 git push 会被 git shim 机械阻断；
- 普通 gh 写操作会被 gh shim 机械阻断；
- 只有 app-gh 和 app-git-push 才能写。

所有 Implementer GitHub 写操作必须显式调用受控 wrapper：
1. Git Push：
   必须使用 app-git-push (或 python {APP_GIT_PUSH_EXECUTOR})
   命令格式（--expected-sha 为强制必填项）：
   app-git-push --branch <branch> --expected-sha <40 hex SHA>
   或者：
   python {APP_GIT_PUSH_EXECUTOR} --branch <branch> --expected-sha <40 hex SHA>

2. PR 创建与更新：
   必须使用 app-gh (或 python {APP_GH_EXECUTOR})
   命令格式：
   app-gh pr create --title "..." --body "..."
   或者：
   python {APP_GH_EXECUTOR} pr create --title "..." --body "..."

3. PR 必须关联源 Issue #{issue_number}。
4. PR 描述必须如实填写：
   - Frozen Spec
   - 实际修改范围
   - 是否偏离
   - 实际测试结果
   - skipped / 未运行项
   - 已知问题
   - follow-up Issue

普通只读命令（git status, git diff, git log, gh pr view, gh issue view, 测试运行）直接在本地执行，无需 wrapper。
不得自动 merge。

====================
七、CI 与结束
====================

PR 创建或更新后：
- 不伪造 CI 状态；
- 不因为本地测试通过就宣称 CI 已通过；
- GitHub Actions 结果由 GitHub 记录。
- 本次 Agent 运行到 PR 已创建/更新且本地证据已记录后即可停止。

====================
八、Changes Requested 上限
====================

一次正式 GitHub CHANGES_REQUESTED Review = 1 轮。
最多允许 3 轮。
若第 3 轮修改后仍收到正式 CHANGES_REQUESTED：
在 Issue 上转 needs-human 并停止，不得开始第 4 轮。

====================
九、最终输出
====================

每次执行结束只输出：
STATUS:
ISSUE: #{issue_number}
BRANCH:
PR:
CHANGES:
TESTS:
BLOCKERS:
NEXT_ACTION:
"""
    return prompt.strip()


def ensure_workspace_fail_closed_guard(repo_path):
    """Ensure repo-local git config and hooks fail closed for direct push."""
    repo_dir = Path(repo_path)
    if not (repo_dir / ".git").is_dir():
        return
    git_bin = shutil.which("git") or "git"
    for remote in ("origin", "easyexam"):
        run_cmd([git_bin, "config", f"remote.{remote}.pushURL", "FAIL_CLOSED_DIRECT_PUSH_DISABLED_USE_APP_GIT_PUSH"], cwd=repo_path)
    # Git commit author metadata is NOT authentication evidence.
    # GitHub identity proof solely comes from App-authenticated API / push chain.
    # Do NOT inject bot user.name or user.email into repo-local or global config.
    hook_path = repo_dir / ".git" / "hooks" / "pre-push"
    hook_content = (
        "#!/bin/sh\n"
        'if [ "$EASYEXAM_APP_PUSH_AUTH" != "1" ] && [ "$ALLOW_HOST_PUSH" != "1" ]; then\n'
        '    echo "FAIL-CLOSED: Direct git push is blocked. Use app_git_push executor." >&2\n'
        '    exit 1\n'
        'fi\n'
        'exit 0\n'
    )
    try:
        hook_path.parent.mkdir(parents=True, exist_ok=True)
        hook_path.write_text(hook_content, encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Could not write pre-push hook: {exc}")


def build_implementer_environment(repo):
    """
    Verify external GitHub App credential helper and executors exist.
    Operation-time token architecture: no secrets are injected into agentapi launch environment.
    """
    if not GITHUB_APP_HELPER.is_file():
        raise RuntimeError("GitHub App credential helper was not found")
    if not APP_GH_EXECUTOR.is_file():
        raise RuntimeError("GitHub App gh executor was not found")
    if not APP_GIT_PUSH_EXECUTOR.is_file():
        raise RuntimeError("GitHub App git push executor was not found")

    spec = importlib.util.spec_from_file_location("easyexam_github_app_credentials", GITHUB_APP_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load GitHub App credential helper")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    child_env = os.environ.copy()
    for key in ("GH_TOKEN", "GITHUB_APP_TOKEN", "GITHUB_TOKEN"):
        child_env.pop(key, None)

    metadata = {
        "installation_id": int(os.environ.get("EASYEXAM_INSTALLATION_ID", "167869152")),
        "app_slug": GITHUB_APP_SLUG,
        "expires_at": None,
    }
    return child_env, metadata


def dispatch_agent(
    repo,
    repo_path,
    issue_number,
    issue_title,
    source_label,
    repair_ordinal=0,
    repair_kind=None,
    failure_detail=None,
):
    """
    Launch a new Antigravity implementer conversation via safe argv list.
    Syntax: agentapi new-conversation [--model=...] [--title=...] <prompt>
    """
    prompt = build_implementer_prompt(
        repo,
        repo_path,
        issue_number,
        issue_title,
        source_label,
        repair_ordinal=repair_ordinal,
        repair_kind=repair_kind,
        failure_detail=failure_detail,
    )
    cmd_prefix = get_agentapi_cmd_prefix()
    recovery_spec = get_recovery_spec(issue_number)
    if recovery_spec is not None and source_label == "changes-requested":
        title = f"Repair Implementer: Issue #{issue_number} ({source_label})"
    elif recovery_spec is not None:
        title = f"Recovery Implementer: Issue #{issue_number} ({source_label})"
    elif source_label in ("changes-requested", "ci-repair") or repair_ordinal > 0:
        ord_str = f" #{repair_ordinal}" if repair_ordinal else ""
        title = f"Repair Implementer{ord_str}: Issue #{issue_number} ({source_label})"
    else:
        title = f"Implementer: Issue #{issue_number} ({source_label})"

    cmd_args = cmd_prefix + ["new-conversation", f"--title={title}", prompt]

    result = {
        "app_slug": GITHUB_APP_SLUG,
        "installation_id": None,
        "token_expires_at": None,
        "agentapi_invoked": False,
        "exit_code": None,
        "timeout": False,
        "conversation_id": None,
        "launch_confirmed": False,
        "error_category": None,
    }
    try:
        ensure_workspace_fail_closed_guard(repo_path)
        child_env, credential = build_implementer_environment(repo)
        result["installation_id"] = credential.get("installation_id")
        result["token_expires_at"] = credential.get("expires_at")
        result["app_slug"] = credential.get("app_slug") or GITHUB_APP_SLUG
    except Exception as exc:
        logger.error("Could not prepare isolated Implementer credentials (%s)", type(exc).__name__)
        result["error_category"] = "credential_setup_exception"
        return result

    logger.info(
        f"Invoking agentapi new-conversation for Issue #{issue_number} using binary: {cmd_prefix[0]}..."
    )
    logger.info("Implementer credential boundary verified; launch env has no persistent tokens.")

    result["agentapi_invoked"] = True
    try:
        code, stdout, stderr, timed_out = run_cmd(
            cmd_args, timeout=AGENTAPI_TIMEOUT_SECONDS, env=child_env
        )
    except Exception as exc:
        logger.error("agentapi invocation raised an unexpected exception (%s)", type(exc).__name__)
        result["error_category"] = "agentapi_invocation_exception"
        return result
    result["exit_code"] = code
    result["timeout"] = bool(timed_out)

    if timed_out:
        logger.error("agentapi timed out")
        result["error_category"] = "agentapi_timeout"
        return result

    if code != 0:
        logger.error("agentapi returned a non-zero exit code: %s", code)
        result["error_category"] = "agentapi_nonzero_exit"
        return result

    conversation_id = extract_conversation_id(stdout)
    if not conversation_id:
        logger.error("agentapi returned success without a parseable conversation ID")
        result["error_category"] = "conversation_id_missing"
        return result

    result["conversation_id"] = conversation_id
    result["launch_confirmed"] = True
    logger.info("Agent launch confirmed for Issue #%s, conversation %s", issue_number, conversation_id)
    return result


def process_claimed_dispatch(repo, issue_number, issue_title, source_label, attempt_id, lease_token=None, ledger=None):
    """Launch a claimed issue and leave a durable receipt or fail it closed."""
    ledger = ledger or get_ledger()
    ledger.record_launch_intent(attempt_id)

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "attempt_id": attempt_id,
        "event": "claimed",
        "repo": repo,
        "issue_number": issue_number,
        "source_label": source_label,
        "claim_result": True,
        "app_slug": GITHUB_APP_SLUG,
        "installation_id": None,
        "token_expires_at": None,
        "agentapi_invoked": False,
        "exit_code": None,
        "timeout": False,
        "conversation_id": None,
        "launch_confirmed": False,
        "final_coordination_state": "agent-working",
        "error_category": None,
    }
    try:
        append_dispatch_audit(record)
    except Exception as exc:
        logger.error("Could not persist the claimed dispatch receipt (%s)", type(exc).__name__)
        try:
            blocked = fail_closed_to_infra_blocked(repo, issue_number, "audit_write_failed", attempt_id)
        except Exception as fail_exc:
            logger.error("Fail-closed GitHub update raised an exception (%s)", type(fail_exc).__name__)
            blocked = False
        record["final_coordination_state"] = "infra-blocked" if blocked else "agent-working"
        record["error_category"] = "audit_write_failed"
        ledger.record_outcome(attempt_id, "audit_write_failed", last_error="audit_write_failed")
        if lease_token:
            ledger.release_lease(lease_token)
        else:
            ledger.release_issue_lease(repo, issue_number)
        return record

    try:
        result = dispatch_agent(repo, EASYEXAM_REPO_PATH, issue_number, issue_title, source_label)
        if not isinstance(result, dict):
            raise TypeError("dispatch_result_invalid")
    except Exception as exc:
        logger.error("Unexpected exception while dispatching a claimed issue (%s)", type(exc).__name__)
        result = {"error_category": "unexpected_dispatch_exception"}

    for key in (
        "app_slug", "installation_id", "token_expires_at", "agentapi_invoked",
        "exit_code", "timeout", "conversation_id", "launch_confirmed", "error_category",
    ):
        if key in result:
            record[key] = result[key]

    if record["launch_confirmed"] and record["conversation_id"]:
        record["event"] = "launch_confirmed"
        ledger.record_launch_confirmed(attempt_id, record["conversation_id"])
        try:
            append_dispatch_audit(record)
            return record
        except Exception as exc:
            logger.error("Could not persist the confirmed conversation receipt (%s)", type(exc).__name__)
            record["error_category"] = "audit_write_failed"

    category = record["error_category"] or "dispatch_unconfirmed"
    try:
        blocked = fail_closed_to_infra_blocked(repo, issue_number, category, attempt_id)
    except Exception as exc:
        logger.error("Fail-closed GitHub update raised an exception (%s)", type(exc).__name__)
        blocked = False
    record["event"] = "finalized" if blocked else "fail_closed_pending"
    record["final_coordination_state"] = "infra-blocked" if blocked else "agent-working"
    record["launch_confirmed"] = False
    record["error_category"] = category if blocked else "fail_closed_github_update_failed"
    ledger.record_outcome(attempt_id, "failed_to_launch", last_error=category)
    if lease_token:
        ledger.release_lease(lease_token)
    else:
        ledger.release_issue_lease(repo, issue_number)
    try:
        append_dispatch_audit(record)
    except Exception as exc:
        logger.error("Could not persist the fail-closed dispatch receipt (%s)", type(exc).__name__)
    return record


def reconcile_incomplete_dispatches(repo):
    """Fail closed on claims interrupted between claim and a durable terminal receipt."""
    if not DISPATCH_AUDIT_PATH.is_file():
        return True
    latest_by_attempt = {}
    reconciliation_ok = True
    with open(DISPATCH_AUDIT_PATH, "r", encoding="utf-8", errors="replace") as audit_file:
        for line in audit_file:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                logger.error("Ignoring malformed dispatch audit line during reconciliation")
                reconciliation_ok = False
                continue
            attempt_id = item.get("attempt_id")
            if attempt_id:
                latest_by_attempt[attempt_id] = item

    for attempt_id, item in latest_by_attempt.items():
        if item.get("event") in ("launch_confirmed", "finalized", "claim_failed"):
            continue
        issue_number = item.get("issue_number")
        if not issue_number:
            continue
        details = get_issue_details(repo, issue_number)
        labels = {label.get("name") for label in (details or {}).get("labels", [])}
        if details is None or "agent-working" in labels or "infra-blocked" in labels:
            try:
                blocked = fail_closed_to_infra_blocked(
                    repo, issue_number, "dispatcher_interrupted_after_claim", attempt_id
                )
            except Exception as exc:
                logger.error("Interrupted-dispatch fail-closed raised an exception (%s)", type(exc).__name__)
                blocked = False
            final_state = "infra-blocked" if blocked else "agent-working"
            category = "dispatcher_interrupted_after_claim" if blocked else "fail_closed_github_update_failed"
        else:
            final_state = "unclaimed"
            category = "claim_not_applied"
        item.update({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": "finalized" if final_state != "agent-working" else "fail_closed_pending",
            "launch_confirmed": False,
            "final_coordination_state": final_state,
            "error_category": category,
        })
        try:
            append_dispatch_audit(item)
        except Exception as exc:
            logger.error("Could not persist an interrupted dispatch reconciliation (%s)", type(exc).__name__)
            reconciliation_ok = False
        if item.get("event") == "fail_closed_pending":
            reconciliation_ok = False
    return reconciliation_ok


REQUIRED_CHECKS = [
    "Whitespace & Guard Checks",
    "Backend & Packaging Tests",
    "Frontend Unit & Build Tests",
    "Browser E2E Tests",
    "Mobile Interaction E2E",
]


def get_pull_request_details(repo: str, pr_number: int, pr_dict: dict = None) -> dict | None:
    """Fetch PR details using canonical GitHub REST API or return provided test data."""
    if pr_dict is not None:
        return pr_dict
    gh_bin = shutil.which("gh") or "gh"
    cmd = [gh_bin, "api", f"repos/{repo}/pulls/{pr_number}"]
    code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
    if code != 0 or timed_out or not stdout.strip():
        logger.warning(f"Could not fetch details for PR #{pr_number}")
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning(f"Could not parse details JSON for PR #{pr_number}")
        return None


def get_pr_checks_status(repo: str, pr_number: int, head_sha: str = None, checks_data: list[dict] = None) -> dict:
    """
    Query check runs for the PR or commit head.
    Returns:
    {
        "status": "pending" | "success" | "failure",
        "total_checks": int,
        "completed_count": int,
        "failed_check": dict | None,
        "all_checks": list[dict],
    }
    """
    if checks_data is None:
        gh_bin = shutil.which("gh") or "gh"
        if not head_sha and pr_number:
            pr_dict = get_pull_request_details(repo, pr_number)
            if pr_dict:
                head_sha = ((pr_dict.get("head") or {}).get("sha"))

        if head_sha:
            cmd = [gh_bin, "api", f"repos/{repo}/commits/{head_sha}/check-runs?per_page=100"]
            code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
            if code != 0 or timed_out or not stdout.strip():
                logger.warning(f"Could not fetch check runs for commit {head_sha}")
                return {"status": "pending", "total_checks": 0, "completed_count": 0, "failed_check": None, "all_checks": []}
            try:
                res = json.loads(stdout)
                checks_data = res.get("check_runs", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
            except json.JSONDecodeError:
                return {"status": "pending", "total_checks": 0, "completed_count": 0, "failed_check": None, "all_checks": []}
        else:
            cmd = [gh_bin, "pr", "checks", str(pr_number), "--repo", repo, "--json", "name,state,bucket,description"]
            code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
            if code != 0 or timed_out or not stdout.strip():
                logger.warning(f"Could not fetch checks for PR #{pr_number}")
                return {"status": "pending", "total_checks": 0, "completed_count": 0, "failed_check": None, "all_checks": []}
            try:
                checks_data = json.loads(stdout)
            except json.JSONDecodeError:
                return {"status": "pending", "total_checks": 0, "completed_count": 0, "failed_check": None, "all_checks": []}

    if not isinstance(checks_data, list):
        return {"status": "pending", "total_checks": 0, "completed_count": 0, "failed_check": None, "all_checks": []}

    checks_by_name = {}
    for c in checks_data:
        name = c.get("name")
        if not name:
            continue
        c_head = c.get("head_sha")
        # If head_sha is specified and the check run specifies head_sha, require exact equality
        if head_sha and c_head and not verify_exact_head_sha(c_head, head_sha):
            continue
        existing = checks_by_name.get(name)
        if not existing:
            checks_by_name[name] = c
        else:
            existing_id = existing.get("id") or 0
            new_id = c.get("id") or 0
            if new_id >= existing_id:
                checks_by_name[name] = c

    # Require all five named jobs to belong to head_sha before classifying or routing a repair
    if head_sha:
        for name in REQUIRED_CHECKS:
            c = checks_by_name.get(name)
            if not c:
                return {
                    "status": "pending",
                    "total_checks": len(checks_data),
                    "completed_count": 0,
                    "failed_check": None,
                    "all_checks": checks_data,
                }
            c_head = c.get("head_sha")
            if c_head and not verify_exact_head_sha(c_head, head_sha):
                return {
                    "status": "pending",
                    "total_checks": len(checks_data),
                    "completed_count": 0,
                    "failed_check": None,
                    "all_checks": checks_data,
                }

    # Check for any failures among check runs
    for name in REQUIRED_CHECKS:
        c = checks_by_name.get(name)
        if c:
            state = str(c.get("state") or "").upper()
            bucket = str(c.get("bucket") or "").lower()
            conclusion = str(c.get("conclusion") or "").lower()
            if (
                bucket in ("fail", "error")
                or state in ("FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED")
                or conclusion in ("failure", "timed_out", "action_required")
            ):
                return {
                    "status": "failure",
                    "total_checks": len(checks_data),
                    "completed_count": len([
                        x for x in checks_by_name.values()
                        if (x.get("state") or "").upper() == "SUCCESS"
                        or (x.get("bucket") or "").lower() == "pass"
                        or (x.get("conclusion") or "").lower() == "success"
                    ]),
                    "failed_check": c,
                    "all_checks": checks_data,
                }

    # Check if all 5 required checks are completed and successful
    completed_required = 0
    for name in REQUIRED_CHECKS:
        c = checks_by_name.get(name)
        if c:
            state = str(c.get("state") or "").upper()
            bucket = str(c.get("bucket") or "").lower()
            conclusion = str(c.get("conclusion") or "").lower()
            if bucket == "pass" or state == "SUCCESS" or conclusion == "success":
                completed_required += 1

    if completed_required >= len(REQUIRED_CHECKS):
        return {
            "status": "success",
            "total_checks": len(checks_data),
            "completed_count": completed_required,
            "failed_check": None,
            "all_checks": checks_data,
        }

    return {
        "status": "pending",
        "total_checks": len(checks_data),
        "completed_count": completed_required,
        "failed_check": None,
        "all_checks": checks_data,
    }


def get_latest_approved_review(
    repo: str, pr_number: int, reviews_list: list[dict] = None, target_head_sha: str = None
) -> dict | None:
    """Fetch reviews and return latest APPROVED review if no subsequent CHANGES_REQUESTED review exists.
    If target_head_sha is specified, only reviews anchored to target_head_sha are considered.
    """
    if reviews_list is None:
        gh_bin = shutil.which("gh") or "gh"
        cmd = [gh_bin, "api", f"repos/{repo}/pulls/{pr_number}/reviews", "--paginate"]
        code, stdout, stderr, timed_out = run_cmd(cmd, timeout=GITHUB_TIMEOUT_SECONDS)
        if code != 0 or timed_out or not stdout.strip():
            logger.error(f"Failed to fetch reviews for PR #{pr_number}: {stderr}")
            return None
        try:
            reviews_list = json.loads(stdout)
        except json.JSONDecodeError:
            return None

    if not isinstance(reviews_list, list):
        return None

    valid_reviews = [r for r in reviews_list if r.get("state") in ("APPROVED", "CHANGES_REQUESTED")]
    if target_head_sha:
        valid_reviews = [r for r in valid_reviews if is_review_anchored_to_sha(r, target_head_sha)]
    if not valid_reviews:
        return None
    valid_reviews.sort(key=lambda r: (r.get("submitted_at") or "", r.get("id") or 0))
    latest = valid_reviews[-1]
    if latest.get("state") == "APPROVED":
        return latest
    return None


def complete_terminal_merge(
    repo: str,
    issue_number: int,
    attempt_id: str,
    lease_token: str = None,
    resulting_head_sha: str = None,
    ledger: ExecutionLedger = None,
) -> bool:
    """
    Handle terminal merge completion:
    Record outcome 'merged_success', release ownership lease, and clean up active coordination labels.
    """
    ledger = ledger or get_ledger()
    ledger.record_outcome(attempt_id, "merged_success", resulting_head_sha=resulting_head_sha)
    if lease_token:
        ledger.release_lease(lease_token)
    else:
        ledger.release_issue_lease(repo, issue_number)

    logger.info(
        f"Terminal closure SUCCESS for Issue #{issue_number} (attempt {attempt_id}): PR merged with SHA {resulting_head_sha}"
    )

    details = get_issue_details(repo, issue_number)
    labels = {
        l.get("name") if isinstance(l, dict) else str(l)
        for l in (details or {}).get("labels", [])
    }
    remove_labels = [l for l in ("agent-working", "changes-requested", "agent-ready") if l in labels]
    if remove_labels:
        cmd_edit = ["issue", "edit", str(issue_number), "--repo", repo]
        for rl in remove_labels:
            cmd_edit.extend(["--remove-label", rl])
        execute_coordination_write(cmd_edit, repo=repo)

    return True


def transition_attempt_phase(
    attempt: dict,
    ledger: ExecutionLedger,
    new_phase: str,
    resulting_head_sha: str = None,
    now_ts: float = None,
) -> str:
    """
    Transition an attempt's phase both in the ExecutionLedger and in the in-memory attempt dict.
    Updates in-memory attempt's phase_entered_at, phase, and resulting_head_sha so subsequent
    watchdog checks evaluate the newly persisted clock rather than inheriting the previous phase's clock.
    """
    p_entered = (
        datetime.fromtimestamp(float(now_ts), tz=timezone.utc).isoformat()
        if now_ts is not None
        else datetime.now(timezone.utc).isoformat()
    )
    if ledger:
        ledger.record_phase(
            attempt.get("attempt_id"),
            new_phase,
            resulting_head_sha=resulting_head_sha,
            phase_entered_at=p_entered,
        )
        reloaded = ledger.get_attempt(attempt.get("attempt_id"))
        if reloaded:
            attempt.update(reloaded)
            return p_entered

    attempt["phase"] = new_phase
    attempt["phase_entered_at"] = p_entered
    if resulting_head_sha is not None:
        attempt["resulting_head_sha"] = resulting_head_sha
    return p_entered


def advance_active_lifecycle(
    repo: str,
    attempt: dict,
    ledger: ExecutionLedger = None,
    issue_details: dict = None,
    pr_details: dict = None,
    checks_data: list[dict] = None,
    reviews_list: list[dict] = None,
    now_ts: float = None,
) -> tuple[bool, str]:
    """
    Advance the durable lifecycle of an active attempt based on GitHub and runtime state.
    Covers the full production lifecycle:
    LAUNCH_CONFIRMED -> PR_BOUND -> WAITING_CI -> WAITING_REVIEW -> WAITING_MERGE -> terminal outcome.
    Renews active lease and updates heartbeat when progress is observed.
    Evaluates watchdog timeouts when stalled.
    """
    ledger = ledger or get_ledger()
    issue_number = attempt.get("issue_number")
    attempt_id = attempt.get("attempt_id")
    lease_token = attempt.get("lease_token")
    phase = attempt.get("phase")

    if not issue_number or not attempt_id:
        return False, "invalid_attempt_record"

    # Cancellation fencing check
    if issue_details is None:
        try:
            issue_details = get_issue_details(repo, issue_number)
        except Exception:
            issue_details = None

    if issue_details:
        is_cancelled, cancel_reason = check_cancellation_fencing(issue_details)
        if is_cancelled:
            logger.info(
                f"Active attempt {attempt_id} for Issue #{issue_number} is cancelled: {cancel_reason}"
            )
            ledger.record_outcome(attempt_id, f"cancelled_{cancel_reason}", last_error=cancel_reason)
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)
            return True, f"cancelled_{cancel_reason}"

    # Fleeting early phases before launch confirmation
    if phase in ("CLAIM_INTENT", "CLAIMED", "LAUNCH_INTENT"):
        timed_out, reason, target = evaluate_watchdog_timeout(attempt, now_ts=now_ts)
        if timed_out:
            fail_closed_to_infra_blocked(repo, issue_number, reason, attempt_id)
            ledger.record_outcome(attempt_id, "timeout_infra_blocked", last_error=reason)
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)
            return False, reason
        return True, "awaiting_launch_confirmation"

    # Phase: LAUNCH_CONFIRMED (waiting for PR creation / initial push / repair push)
    if phase == "LAUNCH_CONFIRMED":
        pr_number = attempt.get("pr_number")
        is_repair = attempt.get("attempt_kind") in ("ci_repair", "reviewer_repair") or bool(attempt.get("expected_pr_head_sha"))

        if pr_details is not None:
            pr = pr_details
            status = "adopted" if pr else "none_found"
        else:
            status, adopted_pr = adopt_existing_pr(repo, issue_number)
            if status == "adopted" and adopted_pr and (not pr_number or adopted_pr.get("number") == pr_number):
                pr = adopted_pr
            elif pr_number:
                pr = get_pull_request_details(repo, pr_number)
                status = "adopted" if pr else "none_found"
            else:
                pr = None
                status = "none_found"

        if status == "needs_human_multiple_candidates":
            fail_closed_to_needs_human(repo, issue_number, "multiple_pr_candidates", attempt_id)
            ledger.record_outcome(attempt_id, "needs_human_multiple_candidates")
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)
            return False, "multiple_pr_candidates"
        elif status == "invalid_author":
            fail_closed_to_infra_blocked(repo, issue_number, "orphan_pr_invalid_author", attempt_id)
            ledger.record_outcome(attempt_id, "orphan_pr_invalid_author")
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)
            return False, "invalid_author"

        if pr:
            pr_num = pr.get("number")
            branch = ((pr.get("head") or {}).get("ref")) or attempt.get("branch") or ""
            current_sha = ((pr.get("head") or {}).get("sha")) or ""
            expected_head = attempt.get("expected_pr_head_sha")

            if is_repair and expected_head and current_sha == expected_head:
                # Repair agent still in progress, hasn't pushed new head yet
                conv_id = attempt.get("conversation_id")
                if conv_id:
                    has_progress, latest_act = check_implementer_conversation_progress(
                        conv_id, last_activity_ts=attempt.get("heartbeat_at")
                    )
                    if has_progress and latest_act is not None:
                        act_iso = datetime.fromtimestamp(latest_act, tz=timezone.utc).isoformat()
                        ledger.update_heartbeat(attempt_id, heartbeat_at=act_iso)
                        reloaded = ledger.get_attempt(attempt_id)
                        if reloaded:
                            attempt.update(reloaded)

                timed_out, reason, target = evaluate_watchdog_timeout(attempt, now_ts=now_ts)
                if timed_out:
                    fail_closed_to_infra_blocked(repo, issue_number, reason, attempt_id)
                    ledger.record_outcome(attempt_id, "timeout_infra_blocked", last_error=reason)
                    if lease_token:
                        ledger.release_lease(lease_token)
                    ledger.release_issue_lease(repo, issue_number)
                    return False, reason
                else:
                    if lease_token:
                        ledger.renew_lease(lease_token)
                    ledger.renew_issue_lease(repo, issue_number)
                    return True, "waiting_for_repair_push"

            # PR created or new repair head pushed
            p_time = (
                datetime.fromtimestamp(float(now_ts), tz=timezone.utc).isoformat()
                if now_ts is not None
                else datetime.now(timezone.utc).isoformat()
            )
            ledger.record_pr_bound(attempt_id, pr_num, branch, current_sha, phase_entered_at=p_time)
            reloaded = ledger.get_attempt(attempt_id)
            if reloaded:
                attempt.update(reloaded)
            else:
                attempt["phase"] = "PR_BOUND"
                attempt["phase_entered_at"] = p_time
                attempt["pr_number"] = pr_num
                attempt["branch"] = branch
                attempt["resulting_head_sha"] = current_sha
            if lease_token:
                ledger.renew_lease(lease_token)
            ledger.renew_issue_lease(repo, issue_number)
            logger.info(
                f"Production lifecycle: Issue #{issue_number} transitioned LAUNCH_CONFIRMED -> PR_BOUND (PR #{pr_num}, SHA {current_sha})"
            )

            if is_repair:
                # Transition immediately PR_BOUND -> WAITING_CI for repair pushes
                transition_attempt_phase(attempt, ledger, "WAITING_CI", resulting_head_sha=current_sha, now_ts=now_ts)
                logger.info(
                    f"Production lifecycle: Issue #{issue_number} (PR #{pr_num}) transitioned PR_BOUND -> WAITING_CI after repair push"
                )
                return True, "waiting_ci"
            return True, "pr_bound"
        else:
            # PR not created yet
            conv_id = attempt.get("conversation_id")
            if conv_id:
                has_progress, latest_act = check_implementer_conversation_progress(
                    conv_id, last_activity_ts=attempt.get("heartbeat_at")
                )
                if has_progress and latest_act is not None:
                    act_iso = datetime.fromtimestamp(latest_act, tz=timezone.utc).isoformat()
                    ledger.update_heartbeat(attempt_id, heartbeat_at=act_iso)
                    reloaded = ledger.get_attempt(attempt_id)
                    if reloaded:
                        attempt.update(reloaded)

            timed_out, reason, target = evaluate_watchdog_timeout(attempt, now_ts=now_ts)
            if timed_out:
                fail_closed_to_infra_blocked(repo, issue_number, reason, attempt_id)
                ledger.record_outcome(attempt_id, "timeout_infra_blocked", last_error=reason)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)
                return False, reason
            else:
                if lease_token:
                    ledger.renew_lease(lease_token)
                ledger.renew_issue_lease(repo, issue_number)
                return True, "waiting_for_pr_creation"

    # Phases: PR_BOUND or WAITING_CI
    if phase in ("PR_BOUND", "WAITING_CI"):
        pr_number = attempt.get("pr_number")
        if pr_details is not None:
            pr = pr_details
        else:
            status, adopted_pr = adopt_existing_pr(repo, issue_number)
            if status == "adopted" and adopted_pr and (not pr_number or adopted_pr.get("number") == pr_number):
                pr = adopted_pr
            elif pr_number:
                pr = get_pull_request_details(repo, pr_number)
            else:
                pr = None

        if not pr_number and pr:
            pr_number = pr.get("number")
            attempt["pr_number"] = pr_number

        if not pr_number:
            return True, "missing_pr_number"

        if not pr:
            timed_out, reason, target = evaluate_watchdog_timeout(attempt, now_ts=now_ts)
            if timed_out:
                fail_closed_to_infra_blocked(repo, issue_number, reason, attempt_id)
                ledger.record_outcome(attempt_id, "timeout_infra_blocked", last_error=reason)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)
                return False, reason
            return True, "pr_details_pending"

        # Check if PR is already merged
        if pr.get("merged") or (pr.get("state") == "closed" and pr.get("merged_at")):
            complete_terminal_merge(
                repo, issue_number, attempt_id, lease_token=lease_token,
                resulting_head_sha=((pr.get("head") or {}).get("sha")), ledger=ledger
            )
            return True, "merged"

        if pr.get("state") == "closed":
            fail_closed_to_needs_human(repo, issue_number, "pr_closed_without_merge", attempt_id)
            ledger.record_outcome(attempt_id, "pr_closed_unmerged")
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)
            return False, "pr_closed_unmerged"

        current_head_sha = ((pr.get("head") or {}).get("sha")) or attempt.get("resulting_head_sha") or attempt.get("expected_pr_head_sha")
        branch = ((pr.get("head") or {}).get("ref")) or attempt.get("branch")

        # Evaluate CI checks on current head
        ci_info = get_pr_checks_status(repo, pr_number, head_sha=current_head_sha, checks_data=checks_data)
        ci_status = ci_info.get("status")

        if ci_status == "failure":
            failed_check = ci_info.get("failed_check") or {}
            classification, class_reason = classify_ci_failure(failed_check)
            if classification == "infra_failure":
                fail_closed_to_infra_blocked(repo, issue_number, f"ci_infra_{class_reason}", attempt_id)
                ledger.record_outcome(attempt_id, "infra_failure_blocked", resulting_head_sha=current_head_sha, last_error=class_reason)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)
                return False, "infra_failure_blocked"
            elif classification == "ambiguous":
                fail_closed_to_needs_human(repo, issue_number, f"ci_ambiguous_{class_reason}", attempt_id)
                ledger.record_outcome(attempt_id, "ambiguous_failure_needs_human", resulting_head_sha=current_head_sha, last_error=class_reason)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)
                return False, "ambiguous_failure_needs_human"
            else:
                # Code failure: automated CI repair
                can_repair, ordinal = ledger.can_attempt_repair(repo, pr_number, max_repairs=MAX_AUTOMATED_REPAIRS)
                if not can_repair:
                    fail_closed_to_needs_human(repo, issue_number, "repair_budget_exhausted_max_3", attempt_id)
                    ledger.record_outcome(attempt_id, "repair_budget_exhausted", resulting_head_sha=current_head_sha)
                    if lease_token:
                        ledger.release_lease(lease_token)
                    ledger.release_issue_lease(repo, issue_number)
                    return False, "repair_budget_exhausted"

                repair_key = compute_repair_key(repo, pr_number, current_head_sha)
                if ledger.is_repair_key_processed(repair_key):
                    logger.info(f"Duplicate CI repair ignored for {repair_key}")
                    in_flight = ledger.get_active_repair_attempt(repair_key)
                    if in_flight:
                        in_flight_id = in_flight.get("attempt_id")
                        in_flight_conv = in_flight.get("conversation_id")
                        if in_flight_conv:
                            has_prog, latest_act = check_implementer_conversation_progress(
                                in_flight_conv, last_activity_ts=in_flight.get("heartbeat_at")
                            )
                            if has_prog and latest_act is not None:
                                act_iso = datetime.fromtimestamp(latest_act, tz=timezone.utc).isoformat()
                                ledger.update_heartbeat(in_flight_id, heartbeat_at=act_iso)
                                reloaded = ledger.get_attempt(in_flight_id)
                                if reloaded:
                                    in_flight.update(reloaded)
                        timed_out, reason, target = evaluate_watchdog_timeout(in_flight, now_ts=now_ts)
                        if timed_out:
                            fail_closed_to_infra_blocked(repo, issue_number, reason, in_flight_id)
                            ledger.record_outcome(in_flight_id, "timeout_infra_blocked", last_error=reason)
                            if lease_token:
                                ledger.release_lease(lease_token)
                            ledger.release_issue_lease(repo, issue_number)
                            return False, reason
                    if lease_token:
                        ledger.renew_lease(lease_token)
                    ledger.renew_issue_lease(repo, issue_number)
                    return True, "duplicate_ci_repair_ignored"

                ledger.record_outcome(attempt_id, "repaired_ci_failure", resulting_head_sha=current_head_sha)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)

                rep_ok, rep_reason, rep_meta = dispatch_automated_repair(
                    repo=repo,
                    issue_number=issue_number,
                    pr_number=pr_number,
                    current_pr_head_sha=current_head_sha,
                    expected_repair_baseline_sha=current_head_sha,
                    repair_kind="ci_repair",
                    cause_type="ci_failure",
                    cause_id=failed_check.get("name") or "ci_failure",
                    failure_detail=failed_check,
                    ledger=ledger,
                    branch=branch,
                )
                return rep_ok, rep_reason

        elif ci_status == "pending":
            if attempt.get("phase") != "WAITING_CI":
                transition_attempt_phase(
                    attempt, ledger, "WAITING_CI", resulting_head_sha=current_head_sha, now_ts=now_ts
                )
                logger.info(
                    f"Production lifecycle: Issue #{issue_number} (PR #{pr_number}) transitioned to WAITING_CI"
                )
            timed_out, reason, target = evaluate_watchdog_timeout(attempt, now_ts=now_ts)
            if timed_out:
                fail_closed_to_infra_blocked(repo, issue_number, reason, attempt_id)
                ledger.record_outcome(attempt_id, "timeout_infra_blocked", last_error=reason)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)
                return False, reason
            else:
                if lease_token:
                    ledger.renew_lease(lease_token)
                ledger.renew_issue_lease(repo, issue_number)
                return True, "waiting_ci"

        elif ci_status == "success":
            transition_attempt_phase(
                attempt, ledger, "WAITING_REVIEW", resulting_head_sha=current_head_sha, now_ts=now_ts
            )
            if lease_token:
                ledger.renew_lease(lease_token)
            ledger.renew_issue_lease(repo, issue_number)
            logger.info(
                f"Production lifecycle: Issue #{issue_number} (PR #{pr_number}) CI succeeded, transitioned to WAITING_REVIEW"
            )
            return True, "waiting_review"

    # Phase: WAITING_REVIEW
    if phase == "WAITING_REVIEW":
        pr_number = attempt.get("pr_number")
        if pr_details is not None:
            pr = pr_details
        else:
            status, adopted_pr = adopt_existing_pr(repo, issue_number)
            if status == "adopted" and adopted_pr and (not pr_number or adopted_pr.get("number") == pr_number):
                pr = adopted_pr
            elif pr_number:
                pr = get_pull_request_details(repo, pr_number)
            else:
                pr = None

        live_head_sha = ((pr or {}).get("head") or {}).get("sha") or ""
        ledger_head_sha = attempt.get("resulting_head_sha") or ""
        branch = ((pr or {}).get("head") or {}).get("ref") or attempt.get("branch") or ""

        # Head change detection: read live PR head first; if it differs from the ledger's
        # resulting_head_sha, return to the current-head CI path immediately.
        if live_head_sha and ledger_head_sha and live_head_sha != ledger_head_sha:
            logger.info(
                f"PR #{pr_number} head updated from {ledger_head_sha} to {live_head_sha}; "
                f"returning to current-head CI path"
            )
            transition_attempt_phase(
                attempt, ledger, "WAITING_CI", resulting_head_sha=live_head_sha, now_ts=now_ts
            )
            return advance_active_lifecycle(
                repo=repo,
                attempt=attempt,
                ledger=ledger,
                issue_details=issue_details,
                pr_details=pr,
                checks_data=checks_data,
                reviews_list=reviews_list,
                now_ts=now_ts,
            )

        current_head_sha = live_head_sha or ledger_head_sha

        # Check reviews on PR anchored to exact live current_head_sha
        latest_cr = (
            get_latest_changes_requested_review(repo, pr_number, reviews_list=reviews_list, target_head_sha=current_head_sha)
            if pr_number
            else None
        )
        latest_app = (
            get_latest_approved_review(repo, pr_number, reviews_list=reviews_list, target_head_sha=current_head_sha)
            if pr_number
            else None
        )

        if latest_cr and (not latest_app or (latest_cr.get("submitted_at") or "") > (latest_app.get("submitted_at") or "")):
            # Reviewer requested changes anchored to current head
            can_repair, ordinal = ledger.can_attempt_repair(repo, pr_number, max_repairs=MAX_AUTOMATED_REPAIRS)
            if not can_repair:
                fail_closed_to_needs_human(repo, issue_number, "repair_budget_exhausted_max_3", attempt_id)
                ledger.record_outcome(attempt_id, "repair_budget_exhausted", resulting_head_sha=current_head_sha)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)
                return False, "repair_budget_exhausted"

            repair_key = compute_repair_key(repo, pr_number, current_head_sha)
            if ledger.is_repair_key_processed(repair_key):
                logger.info(f"Duplicate reviewer repair ignored for {repair_key}")
                in_flight = ledger.get_active_repair_attempt(repair_key)
                if in_flight:
                    in_flight_id = in_flight.get("attempt_id")
                    in_flight_conv = in_flight.get("conversation_id")
                    if in_flight_conv:
                        has_prog, latest_act = check_implementer_conversation_progress(
                            in_flight_conv, last_activity_ts=in_flight.get("heartbeat_at")
                        )
                        if has_prog and latest_act is not None:
                            act_iso = datetime.fromtimestamp(latest_act, tz=timezone.utc).isoformat()
                            ledger.update_heartbeat(in_flight_id, heartbeat_at=act_iso)
                            reloaded = ledger.get_attempt(in_flight_id)
                            if reloaded:
                                in_flight.update(reloaded)
                    timed_out, reason, target = evaluate_watchdog_timeout(in_flight, now_ts=now_ts)
                    if timed_out:
                        fail_closed_to_infra_blocked(repo, issue_number, reason, in_flight_id)
                        ledger.record_outcome(in_flight_id, "timeout_infra_blocked", last_error=reason)
                        if lease_token:
                            ledger.release_lease(lease_token)
                        ledger.release_issue_lease(repo, issue_number)
                        return False, reason
                if lease_token:
                    ledger.renew_lease(lease_token)
                ledger.renew_issue_lease(repo, issue_number)
                return True, "duplicate_reviewer_repair_ignored"

            ledger.record_outcome(attempt_id, "repaired_reviewer_changes_requested", resulting_head_sha=current_head_sha)
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)

            rep_ok, rep_reason, rep_meta = dispatch_automated_repair(
                repo=repo,
                issue_number=issue_number,
                pr_number=pr_number,
                current_pr_head_sha=current_head_sha,
                expected_repair_baseline_sha=current_head_sha,
                repair_kind="reviewer_repair",
                cause_type="changes_requested",
                cause_id=str(latest_cr.get("id")),
                failure_detail=latest_cr,
                ledger=ledger,
                branch=branch,
            )
            return rep_ok, rep_reason

        elif latest_app:
            # PR is APPROVED anchored to current head
            if pr and (pr.get("merged") or (pr.get("state") == "closed" and pr.get("merged_at"))):
                complete_terminal_merge(
                    repo, issue_number, attempt_id, lease_token=lease_token,
                    resulting_head_sha=current_head_sha, ledger=ledger
                )
                return True, "merged"

            transition_attempt_phase(
                attempt, ledger, "WAITING_MERGE", resulting_head_sha=current_head_sha, now_ts=now_ts
            )
            if lease_token:
                ledger.renew_lease(lease_token)
            ledger.renew_issue_lease(repo, issue_number)
            logger.info(
                f"Production lifecycle: Issue #{issue_number} (PR #{pr_number}) approved, transitioned to WAITING_MERGE"
            )
            return True, "waiting_merge"

        else:
            # Still waiting for Reviewer anchored to current head
            timed_out, reason, target = evaluate_watchdog_timeout(attempt, now_ts=now_ts)
            if timed_out:
                fail_closed_to_needs_human(repo, issue_number, reason, attempt_id)
                ledger.record_outcome(attempt_id, "timeout_needs_human", last_error=reason)
                if lease_token:
                    ledger.release_lease(lease_token)
                ledger.release_issue_lease(repo, issue_number)
                return False, reason
            else:
                if lease_token:
                    ledger.renew_lease(lease_token)
                ledger.renew_issue_lease(repo, issue_number)
                return True, "waiting_review"

    # Phase: WAITING_MERGE
    if phase == "WAITING_MERGE":
        pr_number = attempt.get("pr_number")
        if pr_details is not None:
            pr = pr_details
        else:
            status, adopted_pr = adopt_existing_pr(repo, issue_number)
            if status == "adopted" and adopted_pr and (not pr_number or adopted_pr.get("number") == pr_number):
                pr = adopted_pr
            elif pr_number:
                pr = get_pull_request_details(repo, pr_number)
            else:
                pr = None

        live_head_sha = ((pr or {}).get("head") or {}).get("sha") or ""
        ledger_head_sha = attempt.get("resulting_head_sha") or ""
        branch = ((pr or {}).get("head") or {}).get("ref") or attempt.get("branch") or ""

        if live_head_sha and ledger_head_sha and live_head_sha != ledger_head_sha:
            logger.info(
                f"PR #{pr_number} head updated while WAITING_MERGE from {ledger_head_sha} to {live_head_sha}; "
                f"returning to WAITING_CI"
            )
            transition_attempt_phase(
                attempt, ledger, "WAITING_CI", resulting_head_sha=live_head_sha, now_ts=now_ts
            )
            return advance_active_lifecycle(
                repo=repo,
                attempt=attempt,
                ledger=ledger,
                issue_details=issue_details,
                pr_details=pr,
                checks_data=checks_data,
                reviews_list=reviews_list,
                now_ts=now_ts,
            )

        current_head_sha = live_head_sha or ledger_head_sha

        if pr and (pr.get("merged") or (pr.get("state") == "closed" and pr.get("merged_at"))):
            complete_terminal_merge(
                repo, issue_number, attempt_id, lease_token=lease_token,
                resulting_head_sha=current_head_sha, ledger=ledger
            )
            return True, "merged"

        if pr and pr.get("state") == "closed":
            fail_closed_to_needs_human(repo, issue_number, "pr_closed_without_merge", attempt_id)
            ledger.record_outcome(attempt_id, "pr_closed_unmerged")
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)
            return False, "pr_closed_unmerged"

        timed_out, reason, target = evaluate_watchdog_timeout(attempt, now_ts=now_ts)
        if timed_out:
            fail_closed_to_infra_blocked(repo, issue_number, reason, attempt_id)
            ledger.record_outcome(attempt_id, "timeout_infra_blocked", last_error=reason)
            if lease_token:
                ledger.release_lease(lease_token)
            ledger.release_issue_lease(repo, issue_number)
            return False, reason
        else:
            if lease_token:
                ledger.renew_lease(lease_token)
            ledger.renew_issue_lease(repo, issue_number)
            return True, "waiting_merge"

    return True, "noop"


def reconcile_closure_v1(repo: str, ledger: ExecutionLedger = None, now_ts: float = None) -> bool:
    """
    Startup & runtime reconciliation matching Frozen Spec Section 16:
    - Missed triggers & incomplete receipts.
    - Active lifecycle progression: LAUNCH_CONFIRMED -> PR_BOUND -> WAITING_CI -> WAITING_REVIEW -> WAITING_MERGE -> merged.
    - Orphan agent-working issues: adopt existing PR or fail-closed.
    - Watchdog timeouts: fail-closed to infra-blocked or needs-human.
    - Cancellation fencing on stale active work.
    """
    ledger = ledger or get_ledger()
    reconciled_ok = True

    # 1. Active attempt lifecycle progression & watchdog evaluation
    try:
        active_attempts = ledger.get_active_attempts(repo)
    except Exception as exc:
        logger.error("Error fetching active attempts during reconciliation (%s)", type(exc).__name__)
        active_attempts = []

    for attempt in active_attempts:
        issue_num = attempt.get("issue_number")
        attempt_id = attempt.get("attempt_id")
        if not issue_num or not attempt_id:
            continue

        # Advance active lifecycle based on GitHub and runtime state
        success, reason = advance_active_lifecycle(repo, attempt, ledger=ledger, now_ts=now_ts)
        if not success:
            reconciled_ok = False

    # 2. Check open issues for orphan agent-working states
    try:
        issues = get_open_issues(repo)
    except Exception as exc:
        logger.error(f"Reconciliation error fetching issues: {exc}")
        return False

    if issues is None:
        return True

    for issue in issues:
        issue_num = issue.get("number")
        if not issue_num:
            continue
        labels = {l.get("name") if isinstance(l, dict) else str(l) for l in issue.get("labels", [])}

        # Check orphan agent-working
        if "agent-working" in labels:
            active_lease = ledger.get_active_lease(repo, issue_num)
            if not active_lease:
                adoption_status, adopted_pr = adopt_existing_pr(repo, issue_num)
                if adoption_status == "adopted" and adopted_pr:
                    pr_num = adopted_pr.get("number")
                    pr_branch = ((adopted_pr.get("head") or {}).get("ref")) or ""
                    pr_sha = ((adopted_pr.get("head") or {}).get("sha")) or ""
                    attempt_id = str(uuid.uuid4())
                    owner_id = f"reconciler-{os.getpid()}"
                    acq_ok, token, _ = ledger.acquire_lease(repo, issue_num, owner_id)
                    ledger.record_claim_intent(
                        repo=repo,
                        issue_number=issue_num,
                        owner_id=owner_id,
                        lease_token=token or "adopted",
                        attempt_id=attempt_id,
                        attempt_kind="pr_adoption",
                        trigger_key=f"reconcile_adopt:{pr_num}",
                        pr_number=pr_num,
                        branch=pr_branch,
                        expected_pr_head_sha=pr_sha,
                    )
                    ledger.record_claimed(attempt_id)
                    ledger.record_launch_intent(attempt_id)
                    ledger.record_launch_confirmed(attempt_id, f"adopted-pr-{pr_num}")
                    ledger.record_pr_bound(attempt_id, pr_num, pr_branch, pr_sha)
                    logger.info(f"Reconciliation: adopted orphan PR #{pr_num} for Issue #{issue_num}")
                elif adoption_status == "needs_human_multiple_candidates":
                    fail_closed_to_needs_human(repo, issue_num, "multiple_pr_candidates_on_reconcile")
                    reconciled_ok = False
                elif adoption_status == "invalid_author":
                    fail_closed_to_infra_blocked(repo, issue_num, "orphan_pr_invalid_author")
                    reconciled_ok = False
                else:
                    fail_closed_to_infra_blocked(repo, issue_num, "orphan_agent_working_detected")
                    reconciled_ok = False

    return reconciled_ok


def poll_cycle(now_ts: float = None):
    """Run one polling iteration."""
    if not reconcile_incomplete_dispatches(EASYEXAM_REPO):
        logger.error("Skipping claim scan while dispatch audit reconciliation is pending")
        return

    try:
        reconcile_closure_v1(EASYEXAM_REPO, now_ts=now_ts)
    except Exception as exc:
        logger.error("Error during Closure v1 reconciliation (%s)", type(exc).__name__)

    issues = get_open_issues(EASYEXAM_REPO)
    if issues is None:
        logger.warning("Could not retrieve issue list from GitHub. Retrying next cycle.")
        return

    # Check if there is already an active agent-working issue
    working_issues = []
    for issue in issues:
        label_names = [l.get("name") for l in issue.get("labels", [])]
        if "agent-working" in label_names:
            working_issues.append(issue.get("number"))

    if working_issues:
        ledger = get_ledger()
        working_issue = working_issues[0]
        active_attempt = ledger.get_active_attempt_for_issue(EASYEXAM_REPO, working_issue)
        current_phase = active_attempt.get("phase") if active_attempt else "unknown"
        logger.info(
            f"Active task already in progress: Issue #{working_issue} is agent-working (phase: {current_phase}). Active monitoring."
        )
        return

    # Filter candidate issues
    changes_requested_candidates = []
    agent_ready_candidates = []

    for issue in issues:
        issue_num = issue.get("number")
        if issue_num is not None:
            in_backoff, remaining = is_in_claim_backoff(issue_num)
            if in_backoff:
                logger.debug(f"Issue #{issue_num} is in claim backoff ({remaining:.1f}s remaining). Skipping.")
                continue

        label_names = set(l.get("name") for l in issue.get("labels", []))

        # Ignore blocked or needs-human issues
        if "infra-blocked" in label_names or "needs-human" in label_names:
            continue

        # Must have frozen-spec
        if "frozen-spec" not in label_names:
            continue

        if "changes-requested" in label_names:
            changes_requested_candidates.append(issue)
        elif "agent-ready" in label_names:
            agent_ready_candidates.append(issue)

    # Priority: changes-requested > agent-ready
    target_issue = None
    source_label = None

    if changes_requested_candidates:
        target_issue = changes_requested_candidates[0]
        source_label = "changes-requested"
    elif agent_ready_candidates:
        target_issue = agent_ready_candidates[0]
        source_label = "agent-ready"

    if not target_issue:
        logger.debug("No eligible tasks found. Sleeping.")
        return

    issue_number = target_issue.get("number")
    issue_title = target_issue.get("title", "")
    logger.info(
        f"Found candidate task: #{issue_number} ({issue_title}) with source label '{source_label}'"
    )

    # DRY RUN mode check
    if EASYEXAM_DRY_RUN:
        mode_str = "Recovery Implementer" if get_recovery_spec(issue_number) else "Implementer"
        logger.info(f"[DRY RUN] Target issue identified: #{issue_number} ({issue_title})")
        logger.info(f"[DRY RUN] Would execute claim transition: -{source_label} +agent-working")
        logger.info(
            f"[DRY RUN] Would execute agentapi new-conversation with title '{mode_str}: Issue #{issue_number} ({source_label})'"
        )
        logger.info("[DRY RUN] Skipping all write operations and Agent launch.")
        return

    # Re-verify issue eligibility right before claiming (Double-check)
    details = get_issue_details(EASYEXAM_REPO, issue_number)
    if not details or details.get("state") != "OPEN":
        logger.warning(f"Issue #{issue_number} is no longer OPEN. Skipping.")
        return

    current_labels = set(l.get("name") for l in details.get("labels", []))
    if (
        "infra-blocked" in current_labels
        or "needs-human" in current_labels
        or "frozen-spec" not in current_labels
        or source_label not in current_labels
    ):
        logger.warning(
            f"Issue #{issue_number} labels changed before claiming: {current_labels}. Skipping."
        )
        return

    ledger = get_ledger()
    owner_id = f"dispatcher-{os.getpid()}"

    if source_label == "changes-requested":
        # Production repair entry point:
        # Resolves linked PR and head SHA, latest rejected review baseline,
        # enforces unified repair budget (<= 3), repair-key idempotency, and exact-SHA fencing.
        status, pr = adopt_existing_pr(EASYEXAM_REPO, issue_number)
        if status == "needs_human_multiple_candidates":
            logger.warning(f"Multiple candidate PRs for Issue #{issue_number}. Failing closed to needs-human.")
            fail_closed_to_needs_human(EASYEXAM_REPO, issue_number, "multiple_pr_candidates")
            return
        elif status == "invalid_author":
            logger.warning(f"PR for Issue #{issue_number} has invalid author. Failing closed to infra-blocked.")
            fail_closed_to_infra_blocked(EASYEXAM_REPO, issue_number, "orphan_pr_invalid_author")
            return
        elif status != "adopted" or not pr:
            logger.warning(f"No valid PR found for changes-requested Issue #{issue_number}. Failing closed to needs-human.")
            fail_closed_to_needs_human(EASYEXAM_REPO, issue_number, "no_associated_pr_for_changes_requested")
            return

        pr_number = pr.get("number")
        current_head_sha = ((pr.get("head") or {}).get("sha")) or ""
        branch = ((pr.get("head") or {}).get("ref")) or ""

        latest_review = get_latest_changes_requested_review(EASYEXAM_REPO, pr_number)
        if latest_review:
            cause_id = str(latest_review.get("id") or "latest")
            expected_baseline_sha = latest_review.get("commit_id")
            if not expected_baseline_sha:
                m = re.search(r"\[easyexam-review:([0-9a-fA-F]{40})\]", latest_review.get("body", ""))
                if m:
                    expected_baseline_sha = m.group(1)
                else:
                    m2 = re.search(r"Reviewed head:\s*([0-9a-fA-F]{40})", latest_review.get("body", ""))
                    if m2:
                        expected_baseline_sha = m2.group(1)
                    else:
                        expected_baseline_sha = current_head_sha
        else:
            cause_id = "review_unknown"
            expected_baseline_sha = current_head_sha

        repair_ok, repair_reason, repair_meta = dispatch_automated_repair(
            repo=EASYEXAM_REPO,
            issue_number=issue_number,
            pr_number=pr_number,
            current_pr_head_sha=current_head_sha,
            expected_repair_baseline_sha=expected_baseline_sha,
            repair_kind="reviewer_repair",
            cause_type="changes_requested",
            cause_id=cause_id,
            ledger=ledger,
            owner_id=owner_id,
            branch=branch,
        )
        logger.info(
            f"Automated repair dispatch result for #{issue_number} (PR #{pr_number}): "
            f"ok={repair_ok}, reason={repair_reason}, meta={repair_meta}"
        )
        return

    # Initial dispatch path (agent-ready):
    # Enforce exclusive lease, SQLite ledger CLAIM_INTENT -> CLAIMED -> LAUNCH_INTENT -> LAUNCH_CONFIRMED.
    acquired, lease_token, lease_reason = ledger.acquire_lease(EASYEXAM_REPO, issue_number, owner_id)
    if not acquired:
        logger.warning(f"Could not acquire execution lease for #{issue_number}: {lease_reason}")
        return

    attempt_id = str(uuid.uuid4())
    trigger_key = f"dispatch:{EASYEXAM_REPO}:{issue_number}:{attempt_id}"
    ledger.record_claim_intent(
        repo=EASYEXAM_REPO,
        issue_number=issue_number,
        owner_id=owner_id,
        lease_token=lease_token,
        attempt_id=attempt_id,
        attempt_kind="initial_dispatch",
        trigger_key=trigger_key,
    )

    claim_record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "attempt_id": attempt_id,
        "event": "claim_intent",
        "repo": EASYEXAM_REPO,
        "issue_number": issue_number,
        "source_label": source_label,
        "claim_result": None,
        "app_slug": GITHUB_APP_SLUG,
        "installation_id": None,
        "token_expires_at": None,
        "agentapi_invoked": False,
        "exit_code": None,
        "timeout": False,
        "conversation_id": None,
        "launch_confirmed": False,
        "final_coordination_state": "not_claimed",
        "error_category": None,
    }
    try:
        append_dispatch_audit(claim_record)
    except Exception:
        logger.exception("Cannot safely claim an issue without a durable dispatch journal")
        ledger.release_lease(lease_token)
        return

    # Claim transition: switch source label to agent-working via strict CAS.
    claimed, claim_reason = cas_transition_coordination_state(
        EASYEXAM_REPO, issue_number, source_label, "agent-working"
    )
    if not claimed:
        logger.error(f"Failed claim transition for #{issue_number} (reason: {claim_reason}). Aborting dispatch.")
        backoff_sec = record_claim_failure(issue_number, claim_reason)
        claim_record.update({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": "claim_failed",
            "claim_result": False,
            "final_coordination_state": "unchanged",
            "error_category": f"claim_transition_failed_{claim_reason}",
            "backoff_seconds": backoff_sec,
        })
        try:
            append_dispatch_audit(claim_record)
        except Exception as exc:
            logger.error("Could not persist failed claim outcome (%s)", type(exc).__name__)
        ledger.record_outcome(attempt_id, "failed_to_claim", last_error=claim_reason)
        ledger.release_lease(lease_token)
        return

    reset_claim_backoff(issue_number)

    ledger.record_claimed(attempt_id)
    claim_record.update({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event": "claimed",
        "claim_result": True,
        "final_coordination_state": "agent-working",
    })
    try:
        append_dispatch_audit(claim_record)
    except Exception as exc:
        logger.error("Claim succeeded but its result could not be journaled (%s)", type(exc).__name__)
        fail_closed_to_infra_blocked(EASYEXAM_REPO, issue_number, "audit_write_failed", attempt_id)
        ledger.record_outcome(attempt_id, "audit_write_failed", last_error="audit_write_failed")
        ledger.release_lease(lease_token)
        return

    process_claimed_dispatch(
        EASYEXAM_REPO, issue_number, issue_title, source_label, attempt_id, lease_token=lease_token, ledger=ledger
    )


def main():
    lock = WindowsSingleInstanceLock()
    if not lock.acquire():
        sys.exit(1)

    try:
        logger.info("Starting EasyExam Dispatcher Sidecar")
        logger.info(f"Dispatcher Version: {DISPATCHER_VERSION}")
        logger.info(f"Repository: {EASYEXAM_REPO}")
        logger.info(f"Local Path: {EASYEXAM_REPO_PATH}")
        logger.info(f"Poll Interval: {EASYEXAM_POLL_SECONDS}s")
        logger.info(f"Dry Run: {EASYEXAM_DRY_RUN} | Run Once: {EASYEXAM_RUN_ONCE}")

        self_check = check_pr_canonical_author_runtime(EASYEXAM_REPO, 15)
        logger.info(
            f"Runtime self-check: PR #15 canonical REST author login={self_check.get('login')}, "
            f"type={self_check.get('type')}, valid={self_check.get('valid')}"
        )

        try:
            reconciliation_ok = reconcile_incomplete_dispatches(EASYEXAM_REPO) and reconcile_closure_v1(EASYEXAM_REPO)
        except Exception as exc:
            logger.error("Could not reconcile incomplete dispatch attempts (%s)", type(exc).__name__)
            reconciliation_ok = False

        while True:
            try:
                if not reconciliation_ok:
                    try:
                        reconciliation_ok = reconcile_incomplete_dispatches(EASYEXAM_REPO) and reconcile_closure_v1(EASYEXAM_REPO)
                    except Exception as exc:
                        logger.error("Dispatch remains paused until audit reconciliation succeeds (%s)", type(exc).__name__)
                if reconciliation_ok:
                    poll_cycle()
                else:
                    logger.error("Dispatch paused: unresolved claim receipt remains")
            except Exception as exc:
                logger.error("Unexpected error in polling cycle (%s)", type(exc).__name__)

            if EASYEXAM_RUN_ONCE:
                logger.info("EASYEXAM_RUN_ONCE enabled. Exiting main loop.")
                break

            time.sleep(EASYEXAM_POLL_SECONDS)
    finally:
        lock.release()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        num = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        source_label = sys.argv[3] if len(sys.argv) > 3 else "agent-ready"
        print(render_dispatch_prompt(num, source_label=source_label))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        check = check_pr_canonical_author_runtime(EASYEXAM_REPO, 15)
        print(json.dumps(check, indent=2))
        sys.exit(0)
    main()
