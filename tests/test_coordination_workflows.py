import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
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


if __name__ == "__main__":
    unittest.main()
