"""Pure Python implementation of FSRS-5 (Free Spaced Repetition Scheduler).

Upgraded with 21 trainable parameters for personalized forgetting curves,
difficulty damping, and intra-day review stability management.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import List, Optional

# FSRS-5 default parameters (21 parameters)
DEFAULT_W = [
    0.4, 0.6, 2.4, 5.8,         # w0-w3: initial stability for each rating (1=Again, 2=Hard, 3=Good, 4=Easy)
    4.93, 0.94, 0.86, 0.01,     # w4-w7: difficulty parameters (init + update + mean reversion)
    1.49, 0.14, 0.94,           # w8-w10: stability parameters
    2.18, 0.05, 0.34, 1.26,     # w11-w14: lapse/retrievability parameters
    0.29, 2.61,                 # w15-w16: hard penalty / easy bonus
    0.0, 0.0, 0.0,              # w17-w19: same-day review parameters
    1.0,                        # w20: forgetting curve decay (1.0 = standard)
]


@dataclass
class FSRSResult:
    """Result of scheduling a card with FSRS."""
    stability: float
    difficulty: float
    scheduled_days: int
    due: datetime
    state: int = 0  # 0=New, 1=Learning, 2=Review, 3=Relearning


class FSRS5:
    """FSRS-5 scheduling engine for spaced repetition."""

    def __init__(
        self,
        w: Optional[List[float]] = None,
        request_retention: float = 0.9,
    ):
        self.w = list(w) if w is not None else list(DEFAULT_W)
        self.request_retention = request_retention

    def init_stability(self, rating: int) -> float:
        """Calculate initial stability for the first review (rating 1..4)."""
        idx = max(0, min(rating - 1, 3))
        return max(self.w[idx], 0.1)

    def init_difficulty(self, rating: int) -> float:
        """Calculate initial difficulty (rating 1..4).

        Formula: D0 = w4 - exp(w5 * (G - 1)) + 1
        Bounded to [1.0, 10.0].
        """
        d = self.w[4] - math.exp(self.w[5] * (rating - 1)) + 1.0
        return min(max(d, 1.0), 10.0)

    def next_difficulty(self, d: float, rating: int) -> float:
        """Calculate updated difficulty after a review.

        Linear damping: D' = D + delta * (10 - D) / 9
        Mean reversion toward D0(4).
        """
        delta_d = -self.w[6] * (rating - 3)
        d_new = d + delta_d * (10.0 - d) / 9.0
        # Mean reversion toward easiest initial difficulty (rating 4)
        d_new = self.w[7] * self.init_difficulty(4) + (1.0 - self.w[7]) * d_new
        return min(max(d_new, 1.0), 10.0)

    def retrievability(self, elapsed_days: float, stability: float) -> float:
        """Calculate probability of recall at elapsed_days.

        Formula: R(t) = (1 + factor * t / S)^(-decay)
        where factor = 9 * decay, decay = w[20].
        """
        if stability <= 0.0:
            return 0.0
        decay = self.w[20] if len(self.w) > 20 else 1.0
        factor = 9.0 * decay
        return pow(1.0 + elapsed_days / (factor * stability), -decay)

    def same_day_stability(self, s: float, rating: int) -> float:
        """Calculate stability for intra-day reviews (<1 day elapsed) to avoid inflation."""
        if len(self.w) <= 19 or (self.w[17] == 0.0 and self.w[18] == 0.0 and self.w[19] == 0.0):
            return s
        new_s = s * math.exp(self.w[17] * (rating - 3 + self.w[18])) * pow(s, -self.w[19])
        return max(new_s, 0.1)

    def next_stability(
        self,
        d: float,
        s: float,
        r: float,
        rating: Optional[int] = None,
    ) -> float:
        """Calculate next stability after a review.

        Supports both (d, s, r, rating) and (d, s, rating) signatures.
        """
        if rating is None:
            if isinstance(r, (int, float)) and r in (1, 2, 3, 4, 1.0, 2.0, 3.0, 4.0):
                rating = int(r)
                r = self.request_retention
            else:
                rating = 3

        if rating == 1:
            # Lapse / Again
            lapse_s = (
                self.w[11]
                * pow(d, -self.w[12])
                * (pow(s + 1.0, self.w[13]) - 1.0)
                * math.exp((1.0 - r) * self.w[14])
            )
            return max(lapse_s, 0.1)

        # Successful recall (Hard, Good, Easy)
        hard_penalty = self.w[15] if rating == 2 else 1.0
        easy_bonus = self.w[16] if rating == 4 else 1.0

        new_s = s * (
            1.0
            + math.exp(self.w[8])
            * (11.0 - d)
            * pow(s, -self.w[9])
            * (math.exp((1.0 - r) * self.w[10]) - 1.0)
            * hard_penalty
            * easy_bonus
        )
        return max(new_s, 0.1)

    def next_interval(
        self,
        stability: float,
        request_retention: Optional[float] = None,
    ) -> int:
        """Compute scheduled interval in days to reach requested retention."""
        if stability <= 0.0:
            return 1
        rr = request_retention if request_retention is not None else self.request_retention
        decay = self.w[20] if len(self.w) > 20 else 1.0
        factor = 9.0 * decay
        # Invert R(t) = (1 + t / (factor * S))^(-decay) = rr -> t = factor * S * (rr^(-1/decay) - 1)
        raw_interval = factor * stability * (pow(rr, -1.0 / decay) - 1.0)
        return max(1, round(raw_interval))

    def schedule(
        self,
        rating: int,
        stability: float = 0.0,
        difficulty: float = 5.0,
        elapsed_days: float = 0.0,
        now: Optional[datetime] = None,
    ) -> FSRSResult:
        """Schedule a review and compute next stability, difficulty, interval, and due time."""
        now = now or datetime.now(timezone.utc)

        if stability <= 0.0:
            # Initial review on new question/card
            new_d = self.init_difficulty(rating)
            new_s = self.init_stability(rating)
            if rating == 1:
                scheduled_days = 1
                state = 1  # Learning
            else:
                scheduled_days = self.next_interval(new_s)
                state = 2 if rating >= 3 else 1  # Review or Learning
        else:
            # Subsequent review
            new_d = self.next_difficulty(difficulty, rating)
            r = self.retrievability(elapsed_days, stability)
            if elapsed_days < 1.0:
                new_s = self.same_day_stability(stability, rating)
            else:
                new_s = self.next_stability(difficulty, stability, r, rating)

            if rating == 1:
                scheduled_days = 1
                state = 3  # Relearning
            else:
                scheduled_days = self.next_interval(new_s)
                state = 2  # Review

        due = now + timedelta(days=scheduled_days)
        return FSRSResult(
            stability=new_s,
            difficulty=new_d,
            scheduled_days=scheduled_days,
            due=due,
            state=state,
        )
