const ACTIVE_LABELS = ["agent-ready", "agent-working", "changes-requested"];
const TERMINAL_LABELS = ["infra-blocked", "needs-human"];

async function cleanupCoordinationLabels(issue, removeLabel) {
  const labels = new Set(issue.labels.map(({ name }) => name));
  if (TERMINAL_LABELS.some((name) => labels.has(name))) {
    return { preservedTerminalState: true, removed: [] };
  }

  const removed = [];
  for (const name of ACTIVE_LABELS) {
    if (labels.has(name)) {
      await removeLabel(name);
      removed.push(name);
    }
  }
  return { preservedTerminalState: false, removed };
}

module.exports = cleanupCoordinationLabels;
