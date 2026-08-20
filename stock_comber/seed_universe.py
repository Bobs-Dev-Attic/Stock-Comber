"""A curated seed universe of diversified small/mid-cap and international names.

This is the starting pool for the nightly "hidden gems" screen. It is diversified
across sectors and geographies and is intended to be expanded over time by the
Finnhub-backed universe catalog (see ``universe.py``). Sectors/regions here are
hints; live Finnhub profiles refine market cap, sector and country. Users can add
their own tickers via settings (``universe.extra_tickers``).

Not investment advice — an illustrative candidate list, not recommendations.
"""

# Each entry: (ticker, sector-hint, region-hint)
SEED_UNIVERSE = [
    # Technology / Software (US small-mid)
    ("ZI", "Technology", "US"), ("PATH", "Technology", "US"),
    ("FROG", "Technology", "US"), ("APPF", "Technology", "US"),
    ("BL", "Technology", "US"), ("PCTY", "Technology", "US"),
    ("NOVT", "Technology", "US"), ("ALRM", "Technology", "US"),
    # Semiconductors
    ("AMKR", "Semiconductors", "US"), ("SLAB", "Semiconductors", "US"),
    ("POWI", "Semiconductors", "US"), ("FORM", "Semiconductors", "US"),
    ("COHU", "Semiconductors", "US"),
    # Healthcare / Med-tech
    ("LNTH", "Healthcare", "US"), ("HALO", "Healthcare", "US"),
    ("MEDP", "Healthcare", "US"), ("OMCL", "Healthcare", "US"),
    ("IRTC", "Healthcare", "US"), ("TNDM", "Healthcare", "US"),
    # Consumer discretionary
    ("CROX", "Consumer", "US"), ("YETI", "Consumer", "US"),
    ("BOOT", "Consumer", "US"), ("CAKE", "Consumer", "US"),
    ("WING", "Consumer", "US"), ("FIGS", "Consumer", "US"),
    # Industrials
    ("AAON", "Industrials", "US"), ("POWL", "Industrials", "US"),
    ("MLI", "Industrials", "US"), ("UFPI", "Industrials", "US"),
    ("ATKR", "Industrials", "US"), ("CSWI", "Industrials", "US"),
    ("GGG", "Industrials", "US"),
    # Financials
    ("PIPR", "Financials", "US"), ("EVR", "Financials", "US"),
    ("HLI", "Financials", "US"), ("FHI", "Financials", "US"),
    ("COOP", "Financials", "US"),
    # Materials / Energy
    ("CMC", "Materials", "US"), ("SUM", "Materials", "US"),
    ("CRC", "Energy", "US"), ("MGY", "Energy", "US"),
    ("AMR", "Energy", "US"),
    # International ADRs — Latin America
    ("STNE", "Financials", "Brazil"), ("PAGS", "Financials", "Brazil"),
    ("DLO", "Financials", "Uruguay"), ("GLOB", "Technology", "Argentina"),
    ("ARCO", "Consumer", "Argentina"), ("VIST", "Energy", "Argentina"),
    # International ADRs — Asia / India
    ("WIT", "Technology", "India"), ("YMM", "Technology", "China"),
    ("TME", "Communication", "China"), ("GDS", "Technology", "China"),
    ("ATAT", "Consumer", "China"), ("TCOM", "Consumer", "China"),
    ("HTHT", "Consumer", "China"),
    # International ADRs — Israel
    ("WIX", "Technology", "Israel"), ("MNDY", "Technology", "Israel"),
    ("GLBE", "Technology", "Israel"), ("CYBR", "Technology", "Israel"),
    ("NICE", "Technology", "Israel"), ("NNDM", "Industrials", "Israel"),
    # International ADRs — Europe / other
    ("ASX", "Semiconductors", "Taiwan"), ("UMC", "Semiconductors", "Taiwan"),
    ("GRVY", "Communication", "South Korea"), ("SE", "Consumer", "Singapore"),
    ("QFIN", "Financials", "China"), ("XYZ", "Technology", "US"),
]


def seed_rows() -> list[dict]:
    """Return the seed universe as upsertable catalog rows."""
    return [
        {"ticker": t, "sector": sector, "country": region, "source": "seed"}
        for (t, sector, region) in SEED_UNIVERSE
    ]


def seed_tickers() -> list[str]:
    return [t for (t, _s, _r) in SEED_UNIVERSE]
