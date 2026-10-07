# EasyExam Automation Sidecar

`automation/sidecar/` is the canonical, version-controlled production source for the EasyExam Automation Dispatcher sidecar.

## Overview

The Dispatcher sidecar bridges GitHub coordination labels (`agent-ready`, `agent-working`, `changes-requested`, `infra-blocked`, `needs-human`) with Antigravity 2.0 autonomous Implementer agents (`chang-implementer[bot]`).

GitHub remains the shared truth for:
- Issue specs and coordination labels
- Pull Requests, Head SHAs, and Required Checks
- Native Code Reviews and GitHub Auto-merge

The local Sidecar runtime manages:
- Exclusive task ownership and leases
- Durable SQLite execution ledger
- Unified repair budget (`MAX_AUTOMATED_REPAIRS = 3`) and idempotency
- Exact-SHA fencing
- Automated crash recovery and watchdog deadlines

## Security and Runtime Boundary

- **In Git (Canonical Source)**:
  - `automation/sidecar/dispatcher.py`: Production sidecar implementation
  - `automation/sidecar/test_dispatcher.py`: Deterministic test suite
  - `automation/sidecar/README.md`: Architecture and usage documentation
- **External to Git (`~/.gemini/`)**:
  - `sidecar.json`: Antigravity sidecar definition
  - `dispatch_audit.jsonl`: Local audit trail
  - `execution_ledger.db`: Runtime SQLite ledger
  - `~/.gemini/credentials/github-app/`: GitHub App private keys and credential helpers

No private keys, tokens, runtime DBs, or audit data may enter Git.

## Execution Ledger Schema

The durable SQLite ledger persists execution attempts and active leases:

```sql
CREATE TABLE execution_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    owner_id TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    phase TEXT NOT NULL,
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
);

CREATE TABLE active_leases (
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    owner_id TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    PRIMARY KEY (repo, issue_number)
);
```

## Key Policies

1. **Exclusive Ownership & Leases**:
   At any moment, at most one legal owner holds the lease for an Issue. If two workers race, exactly one wins. Leases do not automatically transfer to second workers upon expiry.
2. **Unified Repair Budget**:
   `MAX_AUTOMATED_REPAIRS = 3`. CI failure repairs and Reviewer REQUEST_CHANGES repairs share a combined budget of 3 attempts. Attempt #4 transitions to `needs-human`.
3. **Repair Idempotency**:
   Unique key `repair:<repo>:pr:<pr_number>:head:<head_sha>`. Duplicate events for the same head SHA are ignored.
4. **Exact-SHA Fencing**:
   Before initiating a repair, the actual PR head SHA must strictly equal the expected repair baseline SHA.
5. **Existing PR Adoption**:
   If local dispatch receipt is lost but a canonical bot PR exists on GitHub, it is adopted without creating duplicate PRs. Multiple candidate PRs trigger `needs-human`.
6. **Watchdog Deadlines**:
   Unconfirmed launches (>120s), stalled implementers (>1800s), stalled CI (>1800s), and stalled reviews (>1800s) fail closed to `infra-blocked` or `needs-human`.

## Running Tests

Run the sidecar test suite directly:
```bash
python automation/sidecar/test_dispatcher.py
```

Or via project test discovery:
```bash
python -m unittest tests/test_sidecar_suite.py
```
