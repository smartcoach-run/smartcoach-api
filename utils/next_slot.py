from datetime import datetime, timedelta, date
from typing import List, Dict

def compute_next_slot(current_date: date, training_days: list[int]) -> dict:
    """
    Calcule la date du prochain slot à partir du slot courant.
    current_date est DÉJÀ un datetime.date
    """
    assert training_days, "training_days must not be empty"
    assert all(1 <= d <= 7 for d in training_days), "training_days must be ISO (1–7)"

    training_days = sorted(set(training_days))
    if not training_days:
        raise ValueError("training_days vide")
    if not all(isinstance(d, int) and 1 <= d <= 7 for d in training_days):
        raise ValueError("training_days must be ISO (1–7)")

    for delta in range(1, 8):
        candidate = current_date + timedelta(days=delta)
        if candidate.isoweekday() in training_days:
            return {
                "date": candidate.isoformat(),
                "rule": "NEXT_TRAINING_DAY"
            }

    raise RuntimeError(
        f"No next slot found after {current_date}"
    )
