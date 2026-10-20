from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExamBlueprint:
    profile_id: str
    version_number: int
    sections: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"profile_id": self.profile_id, "version_number": self.version_number, "sections": self.sections}


def select_questions_by_blueprint(
    candidate_questions: list[dict],
    blueprint: dict,
    total_questions: int = 0,
) -> list[dict]:
    """Selects questions from candidate_questions based on blueprint sections and filters.

    Sections can define:
    - type: question type (SINGLE, MULTI, JUDGE, ESSAY)
    - count: number of questions to pick for this section
    - tags: list of tags or tag string to match
    - chapter_id: chapter identifier
    - difficulty: target difficulty (1-5)

    Gracefully degrades if not enough matching questions exist in a section.
    """
    sections = blueprint.get("sections")
    if not sections:
        return candidate_questions[:total_questions] if total_questions > 0 else candidate_questions

    selected: list[dict] = []
    selected_ids = set()

    for sec in sections:
        sec_type = sec.get("type")
        sec_tags = sec.get("tags")
        if isinstance(sec_tags, str):
            sec_tags = [sec_tags]
        sec_chapter = sec.get("chapter_id")
        sec_difficulty = sec.get("difficulty")
        sec_count = int(sec.get("count") or 0)
        if sec_count <= 0:
            continue

        matches = []
        for q in candidate_questions:
            if q["id"] in selected_ids:
                continue
            if sec_type and q.get("type") != sec_type:
                continue
            if sec_chapter and q.get("chapter_id") != sec_chapter:
                continue
            if sec_tags:
                q_tags = q.get("tags") or []
                if not any(t in q_tags for t in sec_tags):
                    continue
            if sec_difficulty is not None and q.get("difficulty") != sec_difficulty:
                continue
            matches.append(q)

        picked = matches[:sec_count]
        for p in picked:
            selected.append(p)
            selected_ids.add(p["id"])

    # If target total questions hasn't been reached (either from total_questions or sum of section counts),
    # gracefully degrade by drawing remaining questions from candidates.
    target_total = total_questions if total_questions > 0 else sum(int(s.get("count") or 0) for s in sections)
    if target_total > len(selected):
        for q in candidate_questions:
            if q["id"] not in selected_ids:
                selected.append(q)
                selected_ids.add(q["id"])
                if len(selected) >= target_total:
                    break

    return selected
