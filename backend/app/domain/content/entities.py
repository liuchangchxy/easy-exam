from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QuestionVersion:
    id: str
    question_id: str
    version_number: int
    type: str
    stem: str
    answer: str = ""
    options: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "question_id": self.question_id, "version_number": self.version_number,
            "type": self.type, "stem": self.stem, "answer": self.answer,
            "options": self.options, "explanation": self.explanation, "tags": self.tags,
        }
