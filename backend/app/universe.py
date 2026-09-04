"""The tradable universe: ~40 real NSE names plus the NIFTY 50 index.

`beta` and `ann_vol` are plausible, not fitted — the simulator uses them to
generate a series whose *structure* (index factor + sector factor + residual) is
what the signal engine is designed to decompose. The point of the numbers is
that RELIANCE and a smallcap-ish name behave differently enough that the
z-framing in DESIGN.md §3 has something to do.
"""

from __future__ import annotations

from dataclasses import dataclass

INDEX_SYMBOL = "NIFTY"


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    name: str
    sector: str
    base_price: float
    beta: float
    ann_vol: float          # annualised idiosyncratic vol
    base_volume: float      # shares/session, for the participation z-score

    @property
    def yahoo_ticker(self) -> str:
        return f"{self.symbol}.NS"


UNIVERSE: tuple[SymbolSpec, ...] = (
    # --- IT ----------------------------------------------------------------
    SymbolSpec("TCS", "Tata Consultancy Services", "IT", 3180.0, 0.72, 0.19, 2.4e6),
    SymbolSpec("INFY", "Infosys", "IT", 1616.0, 0.81, 0.22, 7.1e6),
    SymbolSpec("HCLTECH", "HCL Technologies", "IT", 1495.0, 0.85, 0.24, 3.0e6),
    SymbolSpec("WIPRO", "Wipro", "IT", 268.0, 0.79, 0.26, 9.8e6),
    SymbolSpec("TECHM", "Tech Mahindra", "IT", 1622.0, 0.93, 0.27, 2.6e6),
    SymbolSpec("LTIM", "LTIMindtree", "IT", 5480.0, 0.88, 0.28, 6.5e5),
    # --- Banks & financials ------------------------------------------------
    SymbolSpec("HDFCBANK", "HDFC Bank", "BANK", 1931.0, 0.95, 0.17, 1.1e7),
    SymbolSpec("ICICIBANK", "ICICI Bank", "BANK", 1352.0, 1.02, 0.19, 1.3e7),
    SymbolSpec("SBIN", "State Bank of India", "BANK", 842.0, 1.18, 0.24, 1.6e7),
    SymbolSpec("KOTAKBANK", "Kotak Mahindra Bank", "BANK", 1798.0, 0.91, 0.20, 4.2e6),
    SymbolSpec("AXISBANK", "Axis Bank", "BANK", 1164.0, 1.09, 0.22, 8.9e6),
    SymbolSpec("BAJFINANCE", "Bajaj Finance", "BANK", 7320.0, 1.24, 0.28, 1.4e6),
    SymbolSpec("BAJAJFINSV", "Bajaj Finserv", "BANK", 1930.0, 1.15, 0.26, 2.1e6),
    SymbolSpec("INDUSINDBK", "IndusInd Bank", "BANK", 982.0, 1.21, 0.31, 5.4e6),
    # --- Auto --------------------------------------------------------------
    SymbolSpec("TATAMOTORS", "Tata Motors", "AUTO", 759.5, 1.21, 0.31, 1.9e7),
    SymbolSpec("MARUTI", "Maruti Suzuki", "AUTO", 12840.0, 0.88, 0.22, 6.0e5),
    SymbolSpec("M&M", "Mahindra & Mahindra", "AUTO", 3120.0, 1.06, 0.25, 3.3e6),
    SymbolSpec("EICHERMOT", "Eicher Motors", "AUTO", 5410.0, 0.94, 0.24, 8.0e5),
    SymbolSpec("HEROMOTOCO", "Hero MotoCorp", "AUTO", 4380.0, 0.90, 0.26, 1.2e6),
    SymbolSpec("BAJAJ-AUTO", "Bajaj Auto", "AUTO", 8960.0, 0.87, 0.25, 7.0e5),
    # --- Pharma ------------------------------------------------------------
    SymbolSpec("SUNPHARMA", "Sun Pharmaceutical", "PHARMA", 1729.0, 0.62, 0.21, 3.1e6),
    SymbolSpec("DRREDDY", "Dr Reddy's Laboratories", "PHARMA", 1268.0, 0.58, 0.23, 2.2e6),
    SymbolSpec("CIPLA", "Cipla", "PHARMA", 1542.0, 0.61, 0.22, 2.8e6),
    SymbolSpec("DIVISLAB", "Divi's Laboratories", "PHARMA", 6120.0, 0.69, 0.26, 8.5e5),
    SymbolSpec("APOLLOHOSP", "Apollo Hospitals", "PHARMA", 7240.0, 0.83, 0.25, 7.2e5),
    # --- FMCG & consumer ---------------------------------------------------
    SymbolSpec("HINDUNILVR", "Hindustan Unilever", "FMCG", 2418.0, 0.51, 0.16, 2.0e6),
    SymbolSpec("ITC", "ITC", "FMCG", 421.0, 0.63, 0.17, 1.8e7),
    SymbolSpec("NESTLEIND", "Nestle India", "FMCG", 2270.0, 0.46, 0.15, 9.0e5),
    SymbolSpec("BRITANNIA", "Britannia Industries", "FMCG", 5680.0, 0.55, 0.19, 5.5e5),
    SymbolSpec("TITAN", "Titan Company", "CONSUMER", 3610.0, 0.97, 0.24, 1.7e6),
    SymbolSpec("DMART", "Avenue Supermarts", "CONSUMER", 4180.0, 0.79, 0.25, 6.8e5),
    SymbolSpec("ETERNAL", "Eternal", "CONSUMER", 259.1, 1.31, 0.42, 4.6e7),
    # --- Metals & energy ---------------------------------------------------
    SymbolSpec("RELIANCE", "Reliance Industries", "ENERGY", 1478.0, 1.04, 0.20, 1.2e7),
    SymbolSpec("ONGC", "Oil & Natural Gas Corporation", "ENERGY", 258.0, 1.11, 0.27, 1.4e7),
    SymbolSpec("COALINDIA", "Coal India", "ENERGY", 402.0, 1.02, 0.26, 1.1e7),
    SymbolSpec("TATASTEEL", "Tata Steel", "METAL", 168.0, 1.32, 0.33, 4.1e7),
    SymbolSpec("JSWSTEEL", "JSW Steel", "METAL", 1042.0, 1.26, 0.30, 4.3e6),
    SymbolSpec("HINDALCO", "Hindalco Industries", "METAL", 682.0, 1.29, 0.32, 8.7e6),
    # --- Infra & utilities -------------------------------------------------
    SymbolSpec("LT", "Larsen & Toubro", "INFRA", 3640.0, 1.07, 0.21, 2.4e6),
    SymbolSpec("NTPC", "NTPC", "INFRA", 342.0, 0.83, 0.19, 1.5e7),
    SymbolSpec("POWERGRID", "Power Grid Corporation", "INFRA", 296.0, 0.74, 0.18, 1.3e7),
    SymbolSpec("ULTRACEMCO", "UltraTech Cement", "INFRA", 11820.0, 0.96, 0.22, 4.5e5),
    SymbolSpec("ADANIPORTS", "Adani Ports & SEZ", "INFRA", 1394.0, 1.28, 0.34, 5.2e6),
    SymbolSpec("BHARTIARTL", "Bharti Airtel", "INFRA", 1886.0, 0.86, 0.20, 6.4e6),
)

BY_SYMBOL: dict[str, SymbolSpec] = {s.symbol: s for s in UNIVERSE}
SYMBOLS: tuple[str, ...] = tuple(s.symbol for s in UNIVERSE)

SECTORS: dict[str, list[str]] = {}
for _spec in UNIVERSE:
    SECTORS.setdefault(_spec.sector, []).append(_spec.symbol)

# Pairs whose correlation the engine tracks explicitly. A correlation break is
# only interesting against a baseline that is genuinely tight, so these are the
# well-known co-movers rather than every pair in the universe (which would be
# 903 pairs of mostly noise).
TRACKED_PAIRS: tuple[tuple[str, str], ...] = (
    ("TCS", "INFY"),
    ("INFY", "WIPRO"),
    ("HCLTECH", "TECHM"),
    ("HDFCBANK", "ICICIBANK"),
    ("SBIN", "AXISBANK"),
    ("TATASTEEL", "JSWSTEEL"),
    ("SUNPHARMA", "CIPLA"),
    ("DRREDDY", "CIPLA"),
    ("MARUTI", "M&M"),
    ("HEROMOTOCO", "BAJAJ-AUTO"),
    ("ONGC", "COALINDIA"),
    ("NTPC", "POWERGRID"),
)


def spec(symbol: str) -> SymbolSpec:
    return BY_SYMBOL[symbol]


def name_of(symbol: str) -> str:
    s = BY_SYMBOL.get(symbol)
    return s.name if s else symbol


def sector_peers(symbol: str) -> list[str]:
    s = BY_SYMBOL.get(symbol)
    if not s:
        return []
    return [p for p in SECTORS.get(s.sector, []) if p != symbol]
