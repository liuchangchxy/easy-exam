class BankService:
    def __init__(self, banks, questions):
        self.banks = banks
        self.questions = questions

    def create_bank(self, user_id: str, payload: dict) -> dict:
        return self.banks.create(user_id, payload["name"], payload.get("description", ""), payload.get("category", "默认分类"))

    def create_question(self, user_id: str, bank_id: str, payload: dict) -> dict:
        return self.questions.create_versioned_question(user_id, bank_id, payload)

    def copy_question(self, user_id: str, source_question_id: str, target_bank_id: str) -> dict:
        return self.questions.copy_to_bank(user_id, source_question_id, target_bank_id)

    def batch_questions(self, user_id: str, bank_id: str, payload: dict) -> dict:
        return self.questions.batch_mutate_questions(
            user_id,
            bank_id,
            payload.get("question_ids") or [],
            payload.get("operation") or "",
            chapter_id=payload.get("chapter_id"),
            tags=payload.get("tags") or [],
            target_bank_id=payload.get("target_bank_id"),
        )
