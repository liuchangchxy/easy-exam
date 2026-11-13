import unittest
from pathlib import Path


class TestFrontendArchitecture(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / "frontend" / "src"

    def test_active_frontend_is_split_into_views_and_api_modules(self):
        for relative in (
            "views/LoginView.vue",
            "views/HomeView.vue",
            "views/PracticeViewV1.vue",
            "api/client.js",
            "stores/authStore.js",
        ):
            self.assertTrue((self.root / relative).is_file(), relative)

        app_source = (self.root / "App.vue").read_text(encoding="utf-8")
        router_source = (self.root / "router/index.js").read_text(encoding="utf-8")
        self.assertIn("LoginView", app_source)
        self.assertIn("router-view", app_source)
        self.assertIn("HomeView", router_source)
        self.assertIn("PracticeViewV1", router_source)
        self.assertNotIn("fetch('/api/", app_source)

    def test_learning_mistakes_and_import_flows_have_separate_boundaries(self):
        for relative in (
            "views/ReviewView.vue",
            "views/ImportView.vue",
            "api/learning.js",
            "api/imports.js",
            "stores/learningStore.js",
        ):
            self.assertTrue((self.root / relative).is_file(), relative)
        review_source = (self.root / "views/ReviewView.vue").read_text(encoding="utf-8")
        router_source = (self.root / "router/index.js").read_text(encoding="utf-8")
        import_source = (self.root / "views/ImportView.vue").read_text(encoding="utf-8")
        self.assertIn("listDueMistakes", review_source)
        self.assertIn("listMistakes", review_source)
        self.assertIn("ImportView", router_source)
        self.assertIn("ReviewView", router_source)
        self.assertIn("previewFileImport", import_source)

    def test_mock_exam_has_a_dedicated_entrypoint_and_exam_view(self):
        home_source = (self.root / "views/HomeView.vue").read_text(encoding="utf-8")
        router_source = (self.root / "router/index.js").read_text(encoding="utf-8")
        self.assertTrue((self.root / "features/exam/ExamView.vue").is_file())
        self.assertTrue((self.root / "api/exams.js").is_file())
        # P6: the home page no longer emits a bare start event; every entrance
        # goes through the shared start decision so an active session surfaces
        # the 继续/结束并新建 panel instead of silently opening a second one.
        self.assertIn("useStartStudy", home_source)
        self.assertIn("startStudy(", home_source)
        self.assertIn("ExamCenterView", router_source)
        self.assertIn("ExamView", router_source)
        self.assertIn("exams", router_source)
        self.assertIn("practice/:sessionId", router_source)
        self.assertIn("exam/:sessionId", router_source)

        exam_source = (self.root / "features/exam/ExamView.vue").read_text(encoding="utf-8")
        for contract in ('data-testid="exam-timer"', 'data-testid="exam-answer-sheet"',
                         'data-testid="exam-flag-toggle"', 'data-testid="exam-submit-confirm"'):
            self.assertIn(contract, exam_source)

    def test_mistakes_and_kills_have_dedicated_api_and_controls(self):
        self.assertTrue((self.root / "api/kills.js").is_file(), "api/kills.js missing")
        kills_source = (self.root / "api/kills.js").read_text(encoding="utf-8")
        self.assertIn("listKills", kills_source)
        self.assertIn("killQuestion", kills_source)
        self.assertIn("unkillQuestion", kills_source)

        review_source = (self.root / "views/ReviewView.vue").read_text(encoding="utf-8")
        self.assertIn("listKills", review_source)
        self.assertIn("unkillQuestion", review_source)
        self.assertIn("FSRS", review_source)

        practice_source = (self.root / "views/PracticeViewV1.vue").read_text(encoding="utf-8")
        self.assertIn("ep.banks.mark_weak", practice_source)
        self.assertIn("ep.practice.kill", practice_source)

    def test_home_view_supports_bank_creation_and_kills_entry(self):
        home_source = (self.root / "views/HomeView.vue").read_text(encoding="utf-8")
        review_source = (self.root / "views/ReviewView.vue").read_text(encoding="utf-8")
        self.assertIn("ep.today.create_bank", home_source)
        self.assertIn("createBank", home_source)
        self.assertIn("listKills", review_source)
        self.assertIn("killQuestion", review_source)


if __name__ == "__main__":
    unittest.main()
