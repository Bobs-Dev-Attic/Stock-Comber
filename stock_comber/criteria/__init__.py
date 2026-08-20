"""Screening strategies: classic Graham & Buffett, four more investor lenses,
and user-defined custom criteria."""

from .graham import evaluate_graham
from .buffett import evaluate_buffett
from .custom import evaluate_custom
from .piotroski import evaluate_piotroski
from .greenblatt import evaluate_greenblatt
from .lynch import evaluate_lynch
from .netnet import evaluate_netnet

STRATEGIES = {
    "graham": evaluate_graham,
    "buffett": evaluate_buffett,
    "custom": evaluate_custom,
    "piotroski": evaluate_piotroski,
    "greenblatt": evaluate_greenblatt,
    "lynch": evaluate_lynch,
    "netnet": evaluate_netnet,
}

__all__ = [
    "evaluate_graham", "evaluate_buffett", "evaluate_custom",
    "evaluate_piotroski", "evaluate_greenblatt", "evaluate_lynch",
    "evaluate_netnet", "STRATEGIES",
]
