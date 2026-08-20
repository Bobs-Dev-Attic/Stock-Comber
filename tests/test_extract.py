from stock_comber.datasources.sec_edgar import extract_annuals


def test_extract_annuals_shapes(mini_companyfacts):
    annuals = extract_annuals(mini_companyfacts)
    assert [a.fiscal_year for a in annuals] == [2022, 2023]
    latest = annuals[-1]
    assert latest.revenue == 1200
    assert latest.net_income == 260
    assert latest.stockholders_equity == 580
    assert latest.eps == 2.6
    assert latest.shares_outstanding == 100
    assert latest.operating_cash_flow == 300
    assert latest.capital_expenditures == 50


def test_extract_prefers_latest_end_on_restatement():
    facts = {
        "facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
            {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2023-12-31", "val": 100},
            {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2024-12-31", "val": 150},
        ]}}}}
    }
    annuals = extract_annuals(facts)
    assert annuals[-1].net_income == 150


def test_extract_ignores_quarterly():
    facts = {
        "facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
            {"fy": 2023, "fp": "Q1", "form": "10-Q", "end": "2023-03-31", "val": 25},
            {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2023-12-31", "val": 100},
        ]}}}}
    }
    annuals = extract_annuals(facts)
    assert len(annuals) == 1
    assert annuals[0].net_income == 100
