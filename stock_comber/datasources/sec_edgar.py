"""SEC EDGAR data source (free, no API key).

Pulls the ticker->CIK map and the XBRL ``companyfacts`` document for a company,
then reduces the raw us-gaap concepts into tidy annual fundamentals.

Endpoints used (all free, rate-limited to ~10 req/s by the SEC):
  * https://www.sec.gov/files/company_tickers.json
  * https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

The SEC requires a descriptive ``User-Agent`` header containing a contact
email; supply one via ``config.data.user_agent``.
"""

from __future__ import annotations

import time
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..models import AnnualFacts, Company
from .cache import FileCache

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Concept fallbacks, in priority order, per logical field. The unit key differs
# by concept (dollars vs. shares vs. per-share dollars).
_USD = "USD"
_SHARES = "shares"
_EPS = "USD/shares"

CONCEPTS: dict[str, tuple[str, list[str]]] = {
    "revenue": (_USD, [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ]),
    "net_income": (_USD, ["NetIncomeLoss", "ProfitLoss"]),
    "total_assets": (_USD, ["Assets"]),
    "total_liabilities": (_USD, ["Liabilities"]),
    "stockholders_equity": (_USD, [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ]),
    "current_assets": (_USD, ["AssetsCurrent"]),
    "current_liabilities": (_USD, ["LiabilitiesCurrent"]),
    "long_term_debt": (_USD, [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
    ]),
    "eps": (_EPS, ["EarningsPerShareDiluted", "EarningsPerShareBasic"]),
    "shares_outstanding": (_SHARES, [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "CommonStockSharesOutstanding",
    ]),
    "dividends_paid": (_USD, [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
    ]),
    "operating_cash_flow": (_USD, [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ]),
    "capital_expenditures": (_USD, [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ]),
}


def _annual_by_year(concept: dict[str, Any], unit_key: str) -> dict[int, float]:
    """Return {fiscal_year: value} for annual (10-K, full-year) datapoints.

    When a fiscal year has several datapoints (restatements/amendments) the one
    with the most recent ``end`` date wins.
    """
    units = concept.get("units", {})
    entries = units.get(unit_key)
    if not entries and unit_key == _USD:
        # Some filers report shares/dollars under alternate unit spellings.
        for k, v in units.items():
            if k.upper() == _USD:
                entries = v
                break
    if not entries:
        return {}

    best: dict[int, tuple[str, float]] = {}
    for e in entries:
        fy = e.get("fy")
        fp = e.get("fp")
        form = e.get("form", "")
        val = e.get("val")
        end = e.get("end", "")
        if fy is None or val is None:
            continue
        if fp != "FY":
            continue
        if not str(form).startswith("10-K"):
            continue
        prev = best.get(fy)
        if prev is None or end > prev[0]:
            best[fy] = (end, float(val))
    return {fy: v for fy, (_end, v) in best.items()}


def match_tickers(mapping: dict[str, dict], query: str, limit: int = 10) -> list[dict]:
    """Prefix/substring ticker search over a {TICKER: {cik, name}} map.

    Ticker prefix matches rank first, then ticker-substring/name matches.
    """
    q = (query or "").strip().upper()
    if not q:
        return []
    starts, contains = [], []
    for ticker, info in mapping.items():
        name = info.get("name") or ""
        if ticker.startswith(q):
            starts.append((ticker, name))
        elif q in ticker or q in name.upper():
            contains.append((ticker, name))
    starts.sort()
    contains.sort()
    return [{"ticker": t, "name": n} for t, n in (starts + contains)[:limit]]


def extract_annuals(facts_json: dict[str, Any]) -> list[AnnualFacts]:
    """Reduce a raw companyfacts document to a sorted list of AnnualFacts."""
    gaap = facts_json.get("facts", {}).get("us-gaap", {})
    field_years: dict[str, dict[int, float]] = {}
    for field_name, (unit_key, candidates) in CONCEPTS.items():
        merged: dict[int, float] = {}
        for concept_name in candidates:
            concept = gaap.get(concept_name)
            if not concept:
                continue
            by_year = _annual_by_year(concept, unit_key)
            for fy, val in by_year.items():
                # First candidate to supply a year wins (priority order).
                merged.setdefault(fy, val)
        field_years[field_name] = merged

    all_years = sorted({fy for years in field_years.values() for fy in years})
    annuals: list[AnnualFacts] = []
    for fy in all_years:
        annuals.append(
            AnnualFacts(
                fiscal_year=fy,
                revenue=field_years["revenue"].get(fy),
                net_income=field_years["net_income"].get(fy),
                total_assets=field_years["total_assets"].get(fy),
                total_liabilities=field_years["total_liabilities"].get(fy),
                stockholders_equity=field_years["stockholders_equity"].get(fy),
                current_assets=field_years["current_assets"].get(fy),
                current_liabilities=field_years["current_liabilities"].get(fy),
                long_term_debt=field_years["long_term_debt"].get(fy),
                eps=field_years["eps"].get(fy),
                shares_outstanding=field_years["shares_outstanding"].get(fy),
                dividends_paid=field_years["dividends_paid"].get(fy),
                operating_cash_flow=field_years["operating_cash_flow"].get(fy),
                capital_expenditures=field_years["capital_expenditures"].get(fy),
            )
        )
    return annuals


class SecEdgarSource:
    """Fetches ticker->CIK mapping and company fundamentals from SEC EDGAR."""

    def __init__(
        self,
        user_agent: str,
        cache: Optional[FileCache] = None,
        timeout: float = 30.0,
        delay: float = 0.2,
        session: Any = None,
    ) -> None:
        self.user_agent = user_agent
        self.cache = cache
        self.timeout = timeout
        self.delay = delay
        self._ticker_map: Optional[dict[str, dict[str, Any]]] = None
        if session is not None:
            self.session = session
        elif requests is not None:
            self.session = requests.Session()
        else:  # pragma: no cover
            self.session = None

    # -- HTTP helpers ----------------------------------------------------
    def _get_json(self, url: str, namespace: str, key: str) -> Optional[Any]:
        if self.cache is not None:
            cached = self.cache.get(namespace, key)
            if cached is not None:
                return cached
        if self.session is None:  # pragma: no cover
            raise RuntimeError("requests is not available; cannot fetch data")
        resp = self.session.get(
            url,
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip"},
            timeout=self.timeout,
        )
        if self.delay:
            time.sleep(self.delay)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        if self.cache is not None:
            self.cache.set(namespace, key, data)
        return data

    # -- Public API ------------------------------------------------------
    def ticker_map(self) -> dict[str, dict[str, Any]]:
        """Return {TICKER: {"cik": int, "name": str}} for all SEC filers."""
        if self._ticker_map is not None:
            return self._ticker_map
        data = self._get_json(TICKERS_URL, "sec_tickers", "all") or {}
        mapping: dict[str, dict[str, Any]] = {}
        # The document is {"0": {"cik_str":..,"ticker":..,"title":..}, ...}
        rows = data.values() if isinstance(data, dict) else data
        for row in rows:
            ticker = str(row.get("ticker", "")).upper()
            if not ticker:
                continue
            mapping[ticker] = {
                "cik": int(row.get("cik_str")),
                "name": row.get("title"),
            }
        self._ticker_map = mapping
        return mapping

    def resolve(self, ticker: str) -> Optional[dict[str, Any]]:
        return self.ticker_map().get(ticker.upper())

    def list_tickers(self, limit: Optional[int] = None) -> list[str]:
        tickers = sorted(self.ticker_map().keys())
        return tickers[:limit] if limit else tickers

    def search_tickers(self, query: str, limit: int = 10) -> list[dict]:
        return match_tickers(self.ticker_map(), query, limit)

    def fetch_company(self, ticker: str) -> Optional[Company]:
        """Fetch and reduce fundamentals for one ticker (no price)."""
        info = self.resolve(ticker)
        if not info:
            return None
        cik = info["cik"]
        url = FACTS_URL.format(cik=cik)
        facts = self._get_json(url, "sec_facts", str(cik))
        if not facts:
            return Company(ticker=ticker.upper(), cik=str(cik), name=info.get("name"))
        annuals = extract_annuals(facts)
        return Company(
            ticker=ticker.upper(),
            cik=str(cik),
            name=facts.get("entityName") or info.get("name"),
            annuals=annuals,
        )
