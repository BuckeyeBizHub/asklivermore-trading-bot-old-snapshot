"""
core.csv_ingest
===============
Watches data/csv_imports/ for new files and parses them into Candidate rows
using core/csv_schema.yaml. Tolerant to header changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from core.config import settings
from core.logging import get_logger
from core.state import Candidate

log = get_logger(__name__)


def _load_schema() -> dict[str, list[str]]:
    with settings.csv_schema_path.open() as f:
        return yaml.safe_load(f)


def _pick(row: dict[str, Any], aliases: list[str]) -> Any | None:
    """Case-insensitive header match."""
    lower = {k.lower(): v for k, v in row.items()}
    for a in aliases:
        if a.lower() in lower:
            v = lower[a.lower()]
            if pd.notna(v):
                return v
    return None


def _parse_dt(v: Any) -> datetime:
    if v is None:
        return datetime.now(tz=timezone.utc)
    try:
        return pd.to_datetime(v, utc=True).to_pydatetime()
    except Exception:
        return datetime.now(tz=timezone.utc)


def parse_csv(path: Path) -> list[Candidate]:
    """Parse one CSV file into Candidate rows."""
    schema = _load_schema()
    df = pd.read_csv(path)
    out: list[Candidate] = []
    for _, raw_row in df.iterrows():
        row = raw_row.to_dict()
        ticker = _pick(row, schema["ticker"])
        if not ticker:
            continue
        try:
            cand = Candidate(
                ticker=str(ticker),
                last_price=float(_pick(row, schema["last_price"]) or 0.0),
                rvol=float(_pick(row, schema["rvol"]) or 1.0),
                rs_rating=float(_pick(row, schema["rs_rating"]) or 50.0),
                source="csv",
                captured_at=_parse_dt(_pick(row, schema["captured_at"])),
                raw={
                    "pattern_hint": _pick(row, schema.get("pattern_hint", [])),
                    "note": _pick(row, schema.get("note", [])),
                    "_file": path.name,
                },
            )
            out.append(cand)
        except Exception as e:
            log.warning("csv.row_skip", file=path.name, error=str(e))
    log.info("csv.parsed", file=path.name, rows=len(out))
    return out


def ingest_directory(directory: Path | None = None) -> list[Candidate]:
    """Parse every CSV in the import dir; move processed files to .processed/."""
    directory = directory or settings.csv_import_dir
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
    processed_dir = directory / ".processed"
    processed_dir.mkdir(exist_ok=True)

    candidates: list[Candidate] = []
    for csv_path in sorted(directory.glob("*.csv")):
        try:
            candidates.extend(parse_csv(csv_path))
            csv_path.rename(processed_dir / csv_path.name)
        except Exception as e:
            log.error("csv.ingest_failed", file=csv_path.name, error=str(e))
    return candidates
