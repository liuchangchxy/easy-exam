"""Domain data models and enums for fn-exam."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QuestionType(str, Enum):
    """Question types supported by the exam engine."""
    SINGLE = "SINGLE"
    MULTI = "MULTI"
    JUDGE = "JUDGE"
    ESSAY = "ESSAY"


class SessionMode(str, Enum):
    """Session modes for practicing and examination."""
    PRACTICE = "PRACTICE"
    EXAM = "EXAM"
    ELIMINATION = "ELIMINATION"
    FSRS = "FSRS"


class MistakeCause(str, Enum):
    """6-level mistake cause taxonomy for targeted training."""
    READING_MISS = "READING_MISS"      # 审题粗心/漏看条件
    CONCEPT_GAP = "CONCEPT_GAP"        # 概念模糊/知识盲区
    LOGIC_TRAP = "LOGIC_TRAP"          # 逻辑陷阱/选项干扰
    CALCULATION = "CALCULATION"        # 计算失误/推导演算
    MEMORY_BLANK = "MEMORY_BLANK"      # 记忆遗忘/要点遗漏
    GUESS_LUCK = "GUESS_LUCK"          # 蒙题猜测/侥幸做对


class FSRSState(int, Enum):
    """FSRS card state."""
    NEW = 0
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


@dataclass
class Bank:
    """Question bank entity."""
    id: str
    name: str
    description: str = ""
    category: str = "默认分类"
    question_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "question_count": self.question_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Question:
    """Question entity with options and tags."""
    id: str
    bank_id: str
    type: str
    stem: str
    options: List[Dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    difficulty: int = 3
    tags: List[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "bank_id": self.bank_id,
            "type": self.type,
            "stem": self.stem,
            "options": self.options,
            "answer": self.answer,
            "explanation": self.explanation,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "created_at": self.created_at,
        }


@dataclass
class Session:
    """Examination / practice session entity."""
    id: str
    bank_id: str
    mode: str
    total_questions: int
    current_index: int = 0
    answers_json: str = "{}"
    flags_json: str = "[]"
    time_spent: int = 0
    time_limit: int = 0
    is_completed: bool = False
    score: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "bank_id": self.bank_id,
            "mode": self.mode,
            "total_questions": self.total_questions,
            "current_index": self.current_index,
            "answers_json": self.answers_json,
            "flags_json": self.flags_json,
            "time_spent": self.time_spent,
            "time_limit": self.time_limit,
            "is_completed": self.is_completed,
            "score": self.score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class MistakeRecord:
    """Mistake and FSRS memory record entity."""
    id: str
    question_id: str
    bank_id: str
    mistake_count: int = 1
    consecutive_correct: int = 0
    is_cleared: bool = False
    mistake_cause: Optional[str] = None
    fsrs_state: int = 0
    fsrs_stability: float = 0.0
    fsrs_difficulty: float = 5.0
    fsrs_due: Optional[str] = None
    last_review_at: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question_id": self.question_id,
            "bank_id": self.bank_id,
            "mistake_count": self.mistake_count,
            "consecutive_correct": self.consecutive_correct,
            "is_cleared": self.is_cleared,
            "mistake_cause": self.mistake_cause,
            "fsrs_state": self.fsrs_state,
            "fsrs_stability": self.fsrs_stability,
            "fsrs_difficulty": self.fsrs_difficulty,
            "fsrs_due": self.fsrs_due,
            "last_review_at": self.last_review_at,
            "created_at": self.created_at,
        }
