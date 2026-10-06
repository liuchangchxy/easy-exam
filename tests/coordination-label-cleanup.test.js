const test = require("node:test");
const assert = require("node:assert/strict");

const cleanupCoordinationLabels = require("../.github/scripts/cleanup-coordination-labels");

test("successful completion removes only active coordination labels", async () => {
  const removed = [];
  const result = await cleanupCoordinationLabels(
    { labels: ["agent-working", "changes-requested", "frozen-spec", "bug"].map((name) => ({ name })) },
    async (name) => removed.push(name),
  );

  assert.deepEqual(removed, ["agent-working", "changes-requested"]);
  assert.deepEqual(result, {
    preservedTerminalState: false,
    removed: ["agent-working", "changes-requested"],
  });
});

test("closing in either terminal blocked state preserves all labels", async () => {
  for (const terminalLabel of ["infra-blocked", "needs-human"]) {
    const removed = [];
    const result = await cleanupCoordinationLabels(
      { labels: [terminalLabel, "agent-working"].map((name) => ({ name })) },
      async (name) => removed.push(name),
    );

    assert.deepEqual(removed, []);
    assert.deepEqual(result, { preservedTerminalState: true, removed: [] });
  }
});
