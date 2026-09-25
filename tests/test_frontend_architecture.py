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
        self.assertIn("LoginView", app_source)
        self.assertIn("HomeView", app_source)
        self.assertIn("PracticeViewV1", app_source)
        self.assertNotIn("fetch('/api/", app_source)

    def test_learning_mistakes_and_import_flows_have_separate_boundaries(self):
        for relative in (
            "views/LearningView.vue",
            "views/MistakesView.vue",
            "views/ImportView.vue",
            "api/learning.js",
            "api/imports.js",
            "stores/learningStore.js",
        ):
            self.assertTrue((self.root / relative).is_file(), relative)
        app_source = (self.root / "App.vue").read_text(encoding="utf-8")
        self.assertIn("LearningView", app_source)
        self.assertIn("MistakesView", app_source)
        self.assertIn("ImportView", app_source)

    def test_mock_exam_has_a_dedicated_entrypoint_and_exam_view(self):
        home_source = (self.root / "views/HomeView.vue").read_text(encoding="utf-8")
        app_source = (self.root / "App.vue").read_text(encoding="utf-8")
        self.assertTrue((self.root / "features/exam/ExamView.vue").is_file())
        self.assertTrue((self.root / "api/exams.js").is_file())
        self.assertIn("emit('mock-exam'", home_source)
        self.assertIn("ExamView", app_source)
        self.assertIn('@mock-exam="startExam"', app_source)

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

        mistakes_source = (self.root / "views/MistakesView.vue").read_text(encoding="utf-8")
        self.assertIn("斩杀", mistakes_source)
        self.assertIn("FSRS", mistakes_source)

        practice_source = (self.root / "views/PracticeViewV1.vue").read_text(encoding="utf-8")
        self.assertIn("薄弱", practice_source)
        self.assertIn("斩杀", practice_source)

    def test_home_view_supports_bank_creation_and_kills_entry(self):
        home_source = (self.root / "views/HomeView.vue").read_text(encoding="utf-8")
        self.assertIn("创建题库", home_source)
        self.assertIn("createBank", home_source)
        self.assertIn("斩杀", home_source)



if __name__ == "__main__":
    unittest.main()
