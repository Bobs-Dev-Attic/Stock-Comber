"""Screening strategies: classic Graham and Buffett value criteria."""

from .graham import evaluate_graham
from .buffett import evaluate_buffett

STRATEGIES = {
    "graham": evaluate_graham,
    "buffett": evaluate_buffett,
}

__all__ = ["evaluate_graham", "evaluate_buffett", "STRATEGIES"]
