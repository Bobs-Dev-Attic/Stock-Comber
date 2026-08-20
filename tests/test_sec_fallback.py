"""The ticker->CIK map can point at an entity with no XBRL facts (a newer
registrant sharing the ticker, e.g. XOM). fetch_company must then fall back to
the CIK that actually files 10-Ks for that ticker."""

from stock_comber.datasources.sec_edgar import SecEdgarSource

# A companyfacts doc with one usable annual year.
FACTS_WITH_DATA = {
    "entityName": "Exxon Mobil Corporation",
    "facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2023-12-31", "val": 344000000000},
        ]}},
        "NetIncomeLoss": {"units": {"USD": [
            {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2023-12-31", "val": 36000000000},
        ]}},
    }},
}
# The mapped (wrong) entity: no us-gaap facts at all.
FACTS_EMPTY = {"entityName": "XOM SHELL CO", "facts": {"us-gaap": {}}}

ATOM = "<xml><company-info><CIK>0000034088</CIK></company-info></xml>"


class FakeResp:
    def __init__(self, status=200, data=None, text=""):
        self.status_code = status
        self._data = data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if "companyfacts/CIK0002115436" in url:
            return FakeResp(data=FACTS_EMPTY)
        if "companyfacts/CIK0000034088" in url:
            return FakeResp(data=FACTS_WITH_DATA)
        if "browse-edgar" in url:
            return FakeResp(text=ATOM)
        return FakeResp(status=404)


def _src():
    src = SecEdgarSource("test@example.com", cache=None, delay=0, session=FakeSession())
    src._ticker_map = {"XOM": {"cik": 2115436, "name": "XOM SHELL CO"}}
    return src


def test_fetch_company_falls_back_to_10k_filer_cik():
    src = _src()
    company = src.fetch_company("XOM")
    assert company is not None
    assert company.cik == "34088"                      # used the real filer CIK
    assert company.name == "Exxon Mobil Corporation"   # from the good facts
    assert [a.fiscal_year for a in company.annuals] == [2023]
    assert company.latest.revenue == 344000000000


def test_filer_cik_parses_atom():
    src = _src()
    assert src.filer_cik("XOM") == 34088


def test_no_fallback_when_primary_has_data():
    src = SecEdgarSource("test@example.com", cache=None, delay=0, session=FakeSession())
    src._ticker_map = {"XOM": {"cik": 34088, "name": "Exxon Mobil Corporation"}}
    company = src.fetch_company("XOM")
    assert company.cik == "34088"
    # browse-edgar must NOT be consulted when the mapped CIK already has data.
    assert not any("browse-edgar" in u for u in src.session.calls)
