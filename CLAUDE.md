# Claude Code Project Guidelines

- **First**: Read [AGENTS.md](AGENTS.md) for core behaviors and the Self-Verification Workflow.
- **Next**: Read [TESTING.md](TESTING.md) for gate hierarchies and commands.
- **Verification Gate**:
  - Run `python scripts/verify.py fast` during general development.
  - Run `python scripts/verify.py ui` after UI or interaction modifications.
  - Run `python scripts/verify.py full` once before claiming completion / ready to deliver.
- **Browser Testing**: Use in-repo Playwright suite (`frontend/tests/`). Do not depend on Claude Code's native Chrome extension.
- **Playwright Agents**: Use the repository's official Playwright agent definitions located in `.claude/agents/` (and `.codex/agents/` for Codex).
