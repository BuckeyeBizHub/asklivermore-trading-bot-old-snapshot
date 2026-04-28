"""Tests for the AskLivermore CSV ingester."""
from __future__ import annotations

from pathlib import Path

from core.csv_ingest import parse_csv


def test_parse_csv_minimal(tmp_path: Path) -> None:
    csv = tmp_path / "scan.csv"
    csv.write_text(
        "Ticker,Last,RVOL,RS,Pattern,Note,Date\n"
        "AAPL,190.55,2.4,88,Bull Flag,clean,2026-04-28T13:30:00Z\n"
        "nvda,902.10,3.7,95,VCP,tight pivot,2026-04-28T13:31:00Z\n"
    )
    rows = parse_csv(csv)
    assert {r.ticker for r in rows} == {"AAPL", "NVDA"}
    aapl = next(r for r in rows if r.ticker == "AAPL")
    assert aapl.rvol == 2.4
    assert aapl.rs_rating == 88
    assert aapl.source == "csv"
    assert aapl.raw["pattern_hint"] == "Bull Flag"


def test_parse_csv_alternate_headers(tmp_path: Path) -> None:
    csv = tmp_path / "scan2.csv"
    csv.write_text(
        "Symbol,Price,RelVol,RS Rating,Setup,Notes,Timestamp\n"
        "TSLA,250.00,1.9,72,Cup-Handle,watching,2026-04-28T14:00:00Z\n"
    )
    rows = parse_csv(csv)
    assert len(rows) == 1
    assert rows[0].ticker == "TSLA"
    assert rows[0].rs_rating == 72
