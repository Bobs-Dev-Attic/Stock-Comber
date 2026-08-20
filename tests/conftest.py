"""Shared test fixtures — synthetic companies and a mini companyfacts doc."""

import pytest

from stock_comber.config import load_config
from stock_comber.models import AnnualFacts, Company, Quote


def _year(fy, ni, rev, eq, ca, cl, ltd, eps, shares, ocf, capex, div=0.0):
    return AnnualFacts(
        fiscal_year=fy, net_income=ni, revenue=rev, stockholders_equity=eq,
        total_assets=eq + (cl + ltd), total_liabilities=cl + ltd,
        current_assets=ca, current_liabilities=cl, long_term_debt=ltd,
        eps=eps, shares_outstanding=shares, operating_cash_flow=ocf,
        capital_expenditures=capex, dividends_paid=div,
    )


@pytest.fixture
def strong_company():
    """A profitable, low-debt, steadily growing company (should pass both)."""
    annuals = []
    base_ni = 5_000_000_000
    for i, fy in enumerate(range(2019, 2024)):
        ni = base_ni * (1 + 0.15 * i)
        annuals.append(_year(
            fy, ni=ni, rev=ni * 4, eq=ni * 3, ca=ni * 2, cl=ni * 0.8,
            ltd=ni * 0.3, eps=5.0 + i, shares=ni / (5.0 + i),
            ocf=ni * 1.2, capex=ni * 0.2, div=ni * 0.2,
        ))
    return Company(
        ticker="STRONG", cik="1", name="Strong Co",
        annuals=annuals, quote=Quote(ticker="STRONG", price=40.0, as_of="2024-01-01"),
    )


@pytest.fixture
def weak_company():
    """An expensive, indebted, shrinking company (should fail both)."""
    annuals = []
    for i, fy in enumerate(range(2019, 2024)):
        ni = 100_000_000 * (1 - 0.1 * i)  # shrinking
        annuals.append(_year(
            fy, ni=ni, rev=ni * 20, eq=ni * 0.5, ca=ni * 0.5, cl=ni * 1.5,
            ltd=ni * 5, eps=0.5, shares=ni / 0.5,
            ocf=ni * 0.1, capex=ni * 0.5, div=0.0,
        ))
    return Company(
        ticker="WEAK", cik="2", name="Weak Co",
        annuals=annuals, quote=Quote(ticker="WEAK", price=500.0, as_of="2024-01-01"),
    )


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def mini_companyfacts():
    """A trimmed SEC companyfacts document covering two fiscal years."""
    def usd(pairs):
        return {"units": {"USD": [
            {"fy": fy, "fp": "FY", "form": "10-K", "end": f"{fy}-12-31", "val": val}
            for fy, val in pairs
        ]}}

    def per_share(pairs):
        return {"units": {"USD/shares": [
            {"fy": fy, "fp": "FY", "form": "10-K", "end": f"{fy}-12-31", "val": val}
            for fy, val in pairs
        ]}}

    def shares(pairs):
        return {"units": {"shares": [
            {"fy": fy, "fp": "FY", "form": "10-K", "end": f"{fy}-12-31", "val": val}
            for fy, val in pairs
        ]}}

    return {
        "cik": 320193,
        "entityName": "Example Inc.",
        "facts": {
            "us-gaap": {
                "Revenues": usd([(2022, 1000), (2023, 1200)]),
                "NetIncomeLoss": usd([(2022, 200), (2023, 260)]),
                "Assets": usd([(2022, 900), (2023, 1000)]),
                "Liabilities": usd([(2022, 400), (2023, 420)]),
                "StockholdersEquity": usd([(2022, 500), (2023, 580)]),
                "AssetsCurrent": usd([(2022, 300), (2023, 340)]),
                "LiabilitiesCurrent": usd([(2022, 120), (2023, 130)]),
                "LongTermDebt": usd([(2022, 100), (2023, 90)]),
                "EarningsPerShareDiluted": per_share([(2022, 2.0), (2023, 2.6)]),
                "WeightedAverageNumberOfDilutedSharesOutstanding": shares(
                    [(2022, 100), (2023, 100)]),
                "NetCashProvidedByUsedInOperatingActivities": usd(
                    [(2022, 240), (2023, 300)]),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd(
                    [(2022, 40), (2023, 50)]),
            }
        },
    }
