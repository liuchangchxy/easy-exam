import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
CLEANUP_PATH = ROOT / ".github" / "workflows" / "coordination-label-cleanup.yml"
REQUIRED_CI_JOBS = {
    "quality-and-guards",
    "backend-suite",
    "frontend-unit-and-build",
    "browser-e2e",
    "mobile-interaction-e2e",
}


def read_workflow(path):
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


class CoordinationWorkflowTests(unittest.TestCase):
    def test_ci_keeps_the_five_required_jobs_and_pr_triggers_only(self):
        workflow = read_workflow(CI_PATH)

        self.assertEqual(set(workflow["jobs"]), REQUIRED_CI_JOBS)
        self.assertEqual(
            set(workflow["on"]["pull_request"]["types"]),
            {"opened", "synchronize", "reopened"},
        )
        self.assertEqual(set(workflow["on"]["pull_request"]["branches"]), {"main", "master"})

    def test_closed_issue_cleanup_is_scoped_and_preserves_blocked_states(self):
        workflow = read_workflow(CLEANUP_PATH)

        self.assertEqual(set(workflow["on"]), {"issues"})
        self.assertEqual(workflow["on"]["issues"]["types"], ["closed"])
        self.assertEqual(workflow["permissions"], {"contents": "read", "issues": "write"})
        steps = workflow["jobs"]["cleanup-active-coordination-labels"]["steps"]
        self.assertEqual(steps[0]["uses"], "actions/checkout@v4")
        self.assertEqual(steps[1]["uses"], "actions/github-script@v7")
        self.assertIn("github.rest.issues.get", steps[1]["with"]["script"])
        self.assertIn(
            "${process.env.GITHUB_WORKSPACE}/.github/scripts/cleanup-coordination-labels",
            steps[1]["with"]["script"],
        )


if __name__ == "__main__":
    unittest.main()
