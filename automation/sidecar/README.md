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
  - `automation/sidecar/test_dispatcher.py`: Test suite
  - `automation/sidecar/README.md`: Architecture and usage documentation
- **External to Git (`~/.gemini/`)**:
  - `sidecar.json`: Antigravity sidecar definition
  - `dispatch_audit.jsonl`: Local audit trail
  - `execution_ledger.db`: Runtime SQLite ledger
  - `~/.gemini/credentials/github-app/`: GitHub App private keys and credential helpers

No private keys, tokens, runtime DBs, or audit data may enter Git.

## Running Tests

Run the sidecar test suite directly:
```bash
python automation/sidecar/test_dispatcher.py
```

Or via project test discovery:
```bash
python -m unittest tests/test_sidecar_suite.py
```
