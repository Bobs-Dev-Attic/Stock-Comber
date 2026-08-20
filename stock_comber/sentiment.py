"""A tiny, dependency-free headline sentiment scorer.

Not a machine-learning model — a transparent finance-oriented lexicon that counts
positive vs. negative cue words across headlines and maps the net tone to a
letter grade. Good enough for an at-a-glance "how is the news skewing" signal;
it is a heuristic, not investment advice.
"""

from __future__ import annotations

import re
from typing import Iterable

POSITIVE = {
    "beat", "beats", "surge", "surged", "growth", "grow", "profit", "profits",
    "record", "upgrade", "upgraded", "outperform", "strong", "gains", "gain",
    "rally", "rallies", "bullish", "raises", "raised", "exceeds", "exceed",
    "jump", "jumps", "soar", "soars", "tops", "wins", "win", "approval",
    "approved", "expansion", "expands", "dividend", "buyback", "breakthrough",
    "positive", "boost", "boosted", "rebound", "rebounds", "optimistic",
    "accelerate", "accelerates", "momentum", "outlook", "guidance", "beat-and-raise",
}
NEGATIVE = {
    "miss", "misses", "missed", "plunge", "plunged", "loss", "losses", "downgrade",
    "downgraded", "underperform", "weak", "weakness", "decline", "declines",
    "falls", "fall", "drop", "drops", "cut", "cuts", "lawsuit", "probe",
    "investigation", "bearish", "warns", "warning", "slump", "slumps",
    "bankruptcy", "fraud", "recall", "layoffs", "delay", "delayed", "sink",
    "sinks", "tumble", "tumbles", "negative", "concern", "concerns", "risk",
    "risks", "default", "halt", "halts", "slowdown", "disappoint", "disappoints",
    "shortfall", "sued", "penalty", "resign", "resigns", "scandal",
}

_WORD = re.compile(r"[a-z][a-z'-]*")


def _grade(score: float) -> str:
    if score >= 0.4:
        return "A"
    if score >= 0.15:
        return "B"
    if score > -0.15:
        return "C"
    if score > -0.4:
        return "D"
    return "F"


def compute_sentiment(texts: Iterable[str]) -> dict:
    """Return {score, grade, positive, negative, article_count} for headlines.

    ``score`` is (pos - neg) / (pos + neg) in [-1, 1]; ``grade`` is A–F. With no
    cue words found, the tone is neutral (score 0.0, grade "C").
    """
    texts = [t for t in (texts or []) if t]
    pos = neg = 0
    for text in texts:
        for w in _WORD.findall(text.lower()):
            if w in POSITIVE:
                pos += 1
            elif w in NEGATIVE:
                neg += 1
    total = pos + neg
    score = (pos - neg) / total if total else 0.0
    return {
        "score": round(score, 3),
        "grade": _grade(score),
        "positive": pos,
        "negative": neg,
        "article_count": len(texts),
    }
