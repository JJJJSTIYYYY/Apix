import time
import copy
import math
from typing import Optional, TypedDict, Dict, List
import pandas as pd

from core.commons.logger import logger


# ----------------------------------------------------------------------
# Data schema
# ----------------------------------------------------------------------
class LongtermMemoryMessage(TypedDict):
    memory_type: str            # preference | fact | rule | event | transient
    confidence: float           # 0.0 ~ 1.0
    worth: float                # 0.0 ~ 1.0
    timestamp: float            # Unix timestamp * 1_000_000 (microseconds), create_timestamp
    used_count: int             # Unsigned int
    last_modify_at: float       # Unix timestamp * 1_000_000 (microseconds), update_timestamp (usually current)
    score: Optional[float]      # Training label (0.0 ~ 1.0)


# ----------------------------------------------------------------------
# Long-term memory model
# ----------------------------------------------------------------------
class LongtermMemory:
    """
    Long-term memory scoring module (Ebbinghaus-inspired).

    Core change:
    - Replace exponential decay with:
        f(x) = normalization(n / ||x||)

    where:
        x = [age_since_create, age_since_modify]
    """

    MEMORY_TYPES = ["preference", "fact", "rule", "event", "transient"]
    TIME_SCALE = 1_000_000.0   # microseconds -> seconds

    # ------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------
    def __init__(self) -> None:
        self.params: Dict = {
            # -------------------------------------------------
            # Feature weights
            # -------------------------------------------------
            "w_worth": 3.0,
            "w_used": 1.2,
            "w_time": 1.5,

            # -------------------------------------------------
            # Time scaling (used for normalization, not decay)
            # -------------------------------------------------
            "tau_time": 30 * 24 * 3600,     # 30 days
            "tau_modify": 5 * 24 * 3600,    # 5 days

            # -------------------------------------------------
            # Type bias
            # -------------------------------------------------
            "type_gain": {
                "rule": 1.10,
                "preference": 1.05,
                "fact": 1.00,
                "event": 0.95,
                "transient": 0.50,
            },

            # -------------------------------------------------
            # Bias
            # -------------------------------------------------
            "bias": -1.0,
        }

    # ------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------
    def calc_score(
        self,
        memory: LongtermMemoryMessage,
        *,
        now: float | None = None,
    ) -> float:
        """
        Calculate memory score using Ebbinghaus-like decay.

        Steps:
        1. Build time vector x
        2. Compute ||x||
        3. Apply decay: n / (1 + ||x||)
        4. Linear combination + sigmoid normalization
        """
        if now is None:
            now = time.time()

        p = self.params

        # --------------------------------------------------
        # Unpack fields
        # --------------------------------------------------
        confidence = float(memory["confidence"])
        worth = float(memory["worth"])
        used_count = int(memory["used_count"])
        memory_type = memory["memory_type"]

        created_at = memory["timestamp"] / self.TIME_SCALE
        last_modify_at = memory["last_modify_at"] / self.TIME_SCALE

        # --------------------------------------------------
        # Early exit
        # --------------------------------------------------
        if confidence <= 0.0:
            return 0.0

        # --------------------------------------------------
        # Confidence gate (log-scaled)
        # --------------------------------------------------
        conf_gate = confidence

        # --------------------------------------------------
        # Type gain
        # --------------------------------------------------
        type_gain = p["type_gain"].get(memory_type, 1.0)

        # --------------------------------------------------
        # Time vector (Ebbinghaus core)
        # --------------------------------------------------
        age_since_create = max(0.0, now - created_at)
        age_since_modify = max(0.0, now - last_modify_at)

        # Normalize time (dimensionless)
        t_create = age_since_create / p["tau_time"]
        t_modify = age_since_modify / p["tau_modify"]

        # --------------------------------------------------
        # Usage reinforcement (important!)
        # More usage → slower forgetting
        # --------------------------------------------------
        used_boost = math.log1p(used_count)

        # Avoid division by zero
        reinforce = 1.0 + used_boost

        # Apply reinforcement on modify time
        t_modify_adjusted = t_modify / reinforce

        # --------------------------------------------------
        # Vector norm ||x||
        # --------------------------------------------------
        x_norm = math.sqrt(t_create ** 2 + t_modify_adjusted ** 2)

        # --------------------------------------------------
        # Ebbinghaus decay: n / (1 + ||x||)
        # --------------------------------------------------
        n = 1.0
        ebbinghaus_decay = n / (1.0 + x_norm)

        # --------------------------------------------------
        # Feature composition
        # --------------------------------------------------
        raw_score = type_gain * (
            p["w_worth"] * worth +
            p["w_used"] * used_boost +
            p["w_time"] * ebbinghaus_decay +
            p["bias"]
        )

        logger.info(
            f"[Ebbinghaus] raw={raw_score:.4f}, "
            f"x_norm={x_norm:.4f}, decay={ebbinghaus_decay:.4f}, "
            f"used={used_count}, worth={worth}"
        )

        # --------------------------------------------------
        # Sigmoid normalization
        # --------------------------------------------------
        normalized = 1.0 / (1.0 + math.exp(-raw_score))

        # --------------------------------------------------
        # Final score
        # --------------------------------------------------
        final_score = conf_gate * normalized

        return final_score


memory_model = LongtermMemory()