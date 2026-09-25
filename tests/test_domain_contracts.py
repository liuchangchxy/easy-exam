import unittest

from backend.app.domain.auth.entities import User
from backend.app.domain.content.entities import QuestionVersion
from backend.app.domain.ai.answer_record import ExplanationVersion
from backend.app.domain.learning.scoring import score_answer


class TestDomainContracts(unittest.TestCase):
    def test_domain_entities_have_stable_serializable_contracts(self):
        user = User(id="u1", username="alice")
        version = QuestionVersion(id="v1", question_id="q1", version_number=1, type="SINGLE", stem="题", answer="A")
        explanation = ExplanationVersion(id="e1", user_id="u1", question_id="q1", question_version_id="v1", source="AI", content="解释")
        self.assertEqual(user.to_dict()["username"], "alice")
        self.assertEqual(version.to_dict()["version_number"], 1)
        self.assertEqual(explanation.to_dict()["source"], "AI")

    def test_subjective_answers_are_saved_without_objective_judgment(self):
        result = score_answer("ESSAY", "我的主观作答", "参考答案")
        self.assertEqual(result["score_ratio"], 0.0)
        self.assertEqual(result["correctness"], "UNANSWERED")
        self.assertEqual(result["mastery_status"], "UNSEEN")
        self.assertFalse(result["is_objective"])
