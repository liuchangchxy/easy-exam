const ACTIVE_LABELS = ["agent-ready", "agent-working", "changes-requested"];
const TERMINAL_LABELS = ["infra-blocked", "needs-human"];

async function cleanupCoordinationLabels(issue, removeLabel) {
  const labels = new Set(issue.labels.map(({ name }) => name));
  const preservedTerminalState = TERMINAL_LABELS.some((name) => labels.has(name));

  const removed = [];
  for (const name of ACTIVE_LABELS) {
    if (labels.has(name)) {
      await removeLabel(name);
      removed.push(name);
    }
  }
  return { preservedTerminalState, removed };
}

module.exports = cleanupCoordinationLabels;
