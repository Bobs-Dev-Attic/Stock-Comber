"""Screening strategies: classic Graham, Buffett, and user-defined custom."""

from .graham import evaluate_graham
from .buffett import evaluate_buffett
from .custom import evaluate_custom

STRATEGIES = {
    "graham": evaluate_graham,
    "buffett": evaluate_buffett,
    "custom": evaluate_custom,
}

__all__ = ["evaluate_graham", "evaluate_buffett", "evaluate_custom", "STRATEGIES"]
