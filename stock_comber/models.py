"""Core data models shared across the screener."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class AnnualFacts:
    """A single fiscal year of extracted fundamentals for one company."""

    fiscal_year: int
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    stockholders_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    long_term_debt: Optional[float] = None
    eps: Optional[float] = None
    shares_outstanding: Optional[float] = None
    dividends_paid: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capital_expenditures: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuarterFacts:
    """A single fiscal quarter (10-Q) of extracted fundamentals for one company.

    Flow items (revenue, net income, EPS, operating cash flow) are the quarter's
    own 3-month figures; balance-sheet items are the point-in-time snapshot as of
    ``period_end``. Used for a fresher-than-annual read, not for the annual-based
    strategy scoring.
    """

    period_end: str                       # ISO date, e.g. "2024-09-30"
    fiscal_year: Optional[int] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    stockholders_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    shares_outstanding: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Quote:
    """Latest market price for a security."""

    ticker: str
    price: Optional[float] = None
    as_of: Optional[str] = None
    source: Optional[str] = None
    volume: Optional[float] = None  # latest regular-market share volume, if known


@dataclass
class Company:
    """A company plus everything we know about it."""

    ticker: str
    cik: Optional[str] = None
    name: Optional[str] = None
    annuals: list[AnnualFacts] = field(default_factory=list)
    quarters: list["QuarterFacts"] = field(default_factory=list)
    ttm: Optional[dict] = None     # trailing-twelve-month roll-forward figures
    quote: Optional[Quote] = None
    extra: Optional[dict] = None  # supplementary data (e.g. Finnhub metrics)

    @property
    def latest(self) -> Optional[AnnualFacts]:
        return self.annuals[-1] if self.annuals else None

    @property
    def latest_quarter(self) -> Optional["QuarterFacts"]:
        return self.quarters[-1] if self.quarters else None


@dataclass
class CriterionResult:
    """The outcome of evaluating one named criterion against a company."""

    name: str
    passed: bool
    actual: Optional[float] = None
    threshold: Optional[float] = None
    detail: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenResult:
    """The full outcome of screening one company."""

    ticker: str
    name: Optional[str]
    strategy: str
    passed: bool
    score: float
    max_score: float
    cik: Optional[str] = None
    metrics: dict[str, Optional[float]] = field(default_factory=dict)
    criteria: list[CriterionResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def score_pct(self) -> float:
        return 100.0 * self.score / self.max_score if self.max_score else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["score_pct"] = round(self.score_pct, 1)
        return d
