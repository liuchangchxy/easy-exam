from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExamBlueprint:
    profile_id: str
    version_number: int
    sections: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"profile_id": self.profile_id, "version_number": self.version_number, "sections": self.sections}
