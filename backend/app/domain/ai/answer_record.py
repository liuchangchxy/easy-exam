from dataclasses import dataclass


@dataclass(frozen=True)
class ExplanationVersion:
    id: str
    user_id: str
    question_id: str
    question_version_id: str
    source: str
    content: str
    is_candidate: bool = True
    is_adopted: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id, "user_id": self.user_id, "question_id": self.question_id,
            "question_version_id": self.question_version_id, "source": self.source,
            "content": self.content, "is_candidate": self.is_candidate, "is_adopted": self.is_adopted,
        }
