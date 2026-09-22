"""Mistake and review service implementing 6-level taxonomy and 2-consecutive-correct elimination."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from backend.models import MistakeCause, FSRSState
from backend.repositories import MistakeRepository
from backend.services.fsrs import FSRS5

# 6-level mistake cause taxonomy
TAXONOMY_CAUSES = {
    "READING_MISS",       # 审题粗心/漏看条件
    "CONCEPT_GAP",        # 概念模糊/知识盲区
    "METHOD_GAP",         # 解法不熟/题型思路受阻
    "OPTION_TRAP",        # 逻辑陷阱/选项干扰
    "CALCULATION_ERROR",  # 计算失误/推导演算
    "CARELESSNESS",       # 其他手滑/疏忽
}


def _parse_datetime(val: Any) -> Optional[datetime]:
    """Parse string or datetime to datetime object."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        val = val.strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ):
            try:
                cleaned = val.replace("Z", "").split("+")[0]
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None
    return None


def _to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetime to naive UTC datetime for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class MistakeService:
    """Manages mistake records, 6-level causes, and 2-consecutive-correct elimination."""

    def __init__(
        self,
        mistake_repo: Optional[MistakeRepository] = None,
        fsrs: Optional[FSRS5] = None,
    ):
        self.mistake_repo = mistake_repo
        self.fsrs = fsrs or FSRS5()

    def evaluate_answer(
        self,
        record: Dict[str, Any],
        is_correct: bool,
        cause: Optional[Union[str, MistakeCause]] = None,
    ) -> Dict[str, Any]:
        """Evaluate an answer and update consecutive correct count and cleared state.

        Rule: 2 consecutive correct answers eliminate the mistake (is_cleared = True).
        A wrong answer resets consecutive correct to 0, increments mistake count,
        and reactivates the mistake (is_cleared = False).
        """
        updated = dict(record)
        if is_correct:
            consecutive = updated.get("consecutive_correct", 0) + 1
            updated["consecutive_correct"] = consecutive
            if consecutive >= 2:
                updated["is_cleared"] = True
        else:
            updated["consecutive_correct"] = 0
            updated["is_cleared"] = False
            updated["mistake_count"] = (updated.get("mistake_count") or 0) + 1
            if cause is not None:
                cause_str = cause.value if hasattr(cause, "value") else str(cause)
                updated["mistake_cause"] = cause_str
        return updated

    def record_question_result(
        self,
        question_id: str,
        bank_id: str,
        is_correct: bool,
        rating: Optional[int] = None,
        cause: Optional[Union[str, MistakeCause]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record the answer result for a question, applying elimination rules and FSRS schedule.

        - If the question was never answered wrongly and is answered correctly now,
          it is not recorded as an active mistake (is_cleared = True).
        - If answered wrongly, records mistake with cause, updates FSRS (default Again),
          and calculates next due review time.
        - If an active mistake is answered correctly twice consecutively, it is eliminated.
        """
        if self.mistake_repo is None:
            raise ValueError("MistakeRepository is required to record question results.")

        existing = self.mistake_repo.get_mistake(question_id)
        cause_str = (
            cause.value if hasattr(cause, "value")
            else (str(cause) if cause is not None else None)
        )
        now_dt = now or datetime.now(timezone.utc)

        # First encounter and correct -> not an active mistake
        if existing is None and is_correct:
            return {
                "id": None,
                "question_id": question_id,
                "bank_id": bank_id,
                "mistake_count": 0,
                "consecutive_correct": 1,
                "is_cleared": True,
                "mistake_cause": None,
                "fsrs_state": FSRSState.REVIEW.value if hasattr(FSRSState, "REVIEW") else 2,
                "fsrs_stability": 0.0,
                "fsrs_difficulty": 5.0,
                "fsrs_due": None,
                "last_review_at": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            }

        # Retrieve previous state or defaults
        current_s = existing.get("fsrs_stability", 0.0) if existing else 0.0
        current_d = existing.get("fsrs_difficulty", 5.0) if existing else 5.0
        last_review_at = existing.get("last_review_at") if existing else None

        elapsed_days = 0.0
        if last_review_at:
            last_dt = _parse_datetime(last_review_at)
            if last_dt:
                diff_sec = (_to_utc_naive(now_dt) - _to_utc_naive(last_dt)).total_seconds()
                elapsed_days = max(0.0, diff_sec / 86400.0)

        # Rating: 1=Again if wrong, 3=Good if correct unless explicitly passed
        if rating is None:
            rating = 3 if is_correct else 1

        fsrs_res = self.fsrs.schedule(
            rating=rating,
            stability=current_s,
            difficulty=current_d,
            elapsed_days=elapsed_days,
            now=now_dt,
        )

        # Upsert mistake record in database
        self.mistake_repo.upsert_mistake(
            question_id=question_id,
            bank_id=bank_id,
            is_correct=is_correct,
            mistake_cause=cause_str,
        )

        due_str = fsrs_res.due.strftime("%Y-%m-%d %H:%M:%S")
        self.mistake_repo.update_fsrs(
            question_id=question_id,
            fsrs_state=fsrs_res.state,
            fsrs_stability=fsrs_res.stability,
            fsrs_difficulty=fsrs_res.difficulty,
            fsrs_due=due_str,
        )

        updated = self.mistake_repo.get_mistake(question_id)
        if updated:
            res_dict = dict(updated)
            res_dict["is_cleared"] = bool(res_dict.get("is_cleared", 0))
            return res_dict

        return {
            "question_id": question_id,
            "bank_id": bank_id,
            "is_cleared": is_correct,
            "consecutive_correct": 1 if is_correct else 0,
            "mistake_count": 0 if is_correct else 1,
            "mistake_cause": cause_str,
            "fsrs_stability": fsrs_res.stability,
            "fsrs_difficulty": fsrs_res.difficulty,
            "fsrs_due": due_str,
        }

    def get_due_reviews(
        self,
        bank_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return mistakes due for review (fsrs_due <= as_of and is_cleared = False)."""
        if self.mistake_repo is None:
            return []

        as_of_dt = _to_utc_naive(as_of or datetime.now(timezone.utc))
        records = self.mistake_repo.get_mistakes(bank_id=bank_id, only_uncleared=True)

        due_list: List[Dict[str, Any]] = []
        for rec in records:
            if rec.get("is_cleared"):
                continue
            due_val = rec.get("fsrs_due")
            if not due_val:
                continue
            due_dt = _to_utc_naive(_parse_datetime(due_val))
            if due_dt and due_dt <= as_of_dt:
                item = dict(rec)
                item["is_cleared"] = bool(item.get("is_cleared", 0))
                due_list.append(item)
        return due_list

    def get_active_mistakes_by_cause(
        self,
        bank_id: Optional[str] = None,
        cause: Optional[Union[str, MistakeCause]] = None,
    ) -> List[Dict[str, Any]]:
        """Return active uncleared mistakes filtered by the 6-level taxonomy."""
        if self.mistake_repo is None:
            return []

        records = self.mistake_repo.get_mistakes(bank_id=bank_id, only_uncleared=True)
        results: List[Dict[str, Any]] = []

        target_cause = None
        if cause is not None:
            target_cause = cause.value if hasattr(cause, "value") else str(cause)

        for rec in records:
            if rec.get("is_cleared"):
                continue
            rec_cause = rec.get("mistake_cause")
            if target_cause is not None:
                if rec_cause == target_cause:
                    item = dict(rec)
                    item["is_cleared"] = bool(item.get("is_cleared", 0))
                    results.append(item)
            else:
                if rec_cause in TAXONOMY_CAUSES or rec_cause is not None:
                    item = dict(rec)
                    item["is_cleared"] = bool(item.get("is_cleared", 0))
                    results.append(item)

        return results
