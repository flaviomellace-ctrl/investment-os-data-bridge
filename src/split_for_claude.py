#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
from io import StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "current"

SOURCE = DATA_DIR / "sp500_fundamentals.csv"

# Claude had previously truncated a ~68 KB fetch.
# Keep transport files well below that observed threshold.
TARGET_MAX_BYTES = 48_000
HARD_MAX_BYTES = 58_000


def csv_bytes(df: pd.DataFrame) -> bytes:
    text = df.to_csv(index=False)
    return text.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_ranges(df: pd.DataFrame) -> list[tuple[int, int, bytes]]:
    if len(df) == 0:
        return [(0, 0, csv_bytes(df))]

    ranges: list[tuple[int, int, bytes]] = []
    start = 0

    while start < len(df):
        low = start + 1
        high = len(df)
        best_end = low
        best_data = csv_bytes(df.iloc[start:low])

        # Binary search the largest row range near TARGET_MAX_BYTES.
        while low <= high:
            mid = (low + high) // 2
            data = csv_bytes(df.iloc[start:mid])
            size = len(data)

            if size <= TARGET_MAX_BYTES:
                best_end = mid
                best_data = data
                low = mid + 1
            else:
                high = mid - 1

        # Guarantee at least one row per chunk.
        if best_end <= start:
            best_end = start + 1
            best_data = csv_bytes(df.iloc[start:best_end])

        # Safety check. A single very wide row may exceed the hard threshold:
        # retain it rather than corrupt/split one CSV record.
        if len(best_data) > HARD_MAX_BYTES and best_end - start > 1:
            while best_end - start > 1 and len(best_data) > HARD_MAX_BYTES:
                best_end -= 1
                best_data = csv_bytes(df.iloc[start:best_end])

        ranges.append((start, best_end, best_data))
        start = best_end

    return ranges


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit("sp500_fundamentals.csv non trovato")

    df = pd.read_csv(SOURCE, low_memory=False)

    for old in DATA_DIR.glob("sp500_fundamentals_part_*.csv"):
        old.unlink()

    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    base = (
        f"https://raw.githubusercontent.com/{repo}/main/data/current"
        if repo
        else ""
    )

    ranges = build_ranges(df)
    parts = []

    for i, (start, end, data) in enumerate(ranges, start=1):
        filename = f"sp500_fundamentals_part_{i:02d}.csv"
        path = DATA_DIR / filename
        path.write_bytes(data)

        info = {
            "part": i,
            "filename": filename,
            "row_start_1_based": start + 1 if len(df) else 0,
            "row_end_1_based": end,
            "rows": end - start,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }

        if base:
            info["url"] = f"{base}/{filename}"

        parts.append(info)

    total_rows_from_parts = sum(p["rows"] for p in parts)
    contiguous = True
    expected_start = 1
    for p in parts:
        if p["row_start_1_based"] != expected_start:
            contiguous = False
            break
        expected_start = p["row_end_1_based"] + 1

    index = {
        "source": "sp500_fundamentals.csv",
        "source_sha256": sha256_bytes(SOURCE.read_bytes()),
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "target_max_bytes": TARGET_MAX_BYTES,
        "hard_max_bytes": HARD_MAX_BYTES,
        "total_parts": len(parts),
        "transport_validation": {
            "rows_from_parts": total_rows_from_parts,
            "rows_match_source": total_rows_from_parts == len(df),
            "ranges_contiguous": contiguous and (expected_start - 1 == len(df)),
            "all_parts_under_hard_max": all(p["bytes"] <= HARD_MAX_BYTES for p in parts),
        },
        "parts": parts,
        "rules": [
            "Read every part before full-universe ranking.",
            "Verify source_sha256 and transport_validation before ranking.",
            "MISSING is not zero.",
            "Chunks are transport files only and do not change methodology.",
            "Finalists must still be reconciled with latest primary filings.",
        ],
    }

    if not index["transport_validation"]["rows_match_source"]:
        raise SystemExit("Errore: il totale righe dei chunk non coincide con la sorgente")
    if not index["transport_validation"]["ranges_contiguous"]:
        raise SystemExit("Errore: gli intervalli dei chunk non sono contigui")
    if not index["transport_validation"]["all_parts_under_hard_max"]:
        raise SystemExit(
            "Errore: almeno un chunk supera HARD_MAX_BYTES; ridurre TARGET_MAX_BYTES"
        )

    (DATA_DIR / "fundamentals_chunks.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Investment OS — Fundamentals chunks for Claude",
        "",
        f"- Total rows: **{len(df)}**",
        f"- Total columns: **{len(df.columns)}**",
        f"- Total parts: **{len(parts)}**",
        f"- Target max bytes per part: **{TARGET_MAX_BYTES}**",
        f"- Source SHA-256: `{index['source_sha256']}`",
        "- Read **all parts** before producing any full-universe ranking.",
        "",
    ]

    for p in parts:
        loc = p.get("url", p["filename"])
        md.append(
            f"- Part {p['part']:02d}: {loc} "
            f"— rows {p['row_start_1_based']}-{p['row_end_1_based']} "
            f"— {p['bytes']} bytes "
            f"— sha256 `{p['sha256']}`"
        )

    md.extend(
        [
            "",
            "## Transport validation",
            "",
            f"- Rows from parts: **{total_rows_from_parts}**",
            f"- Rows match source: **{index['transport_validation']['rows_match_source']}**",
            f"- Ranges contiguous: **{index['transport_validation']['ranges_contiguous']}**",
            f"- All parts <= {HARD_MAX_BYTES} bytes: **{index['transport_validation']['all_parts_under_hard_max']}**",
            "",
            "## Regole",
            "",
            "- Non costruire ranking da un sottoinsieme dei chunk.",
            "- MISSING non è zero.",
            "- Applicare Sector Fairness Rule.",
            "- I chunk servono solo al trasporto dei dati.",
            "- Per i finalisti verificare gli ultimi filing SEC/Investor Relations.",
            "",
        ]
    )

    (DATA_DIR / "fundamentals_chunks.md").write_text(
        "\n".join(md),
        encoding="utf-8",
    )

    print(
        f"OK — {len(df)} righe / {len(df.columns)} colonne "
        f"divise in {len(parts)} parti."
    )
    for p in parts:
        print(
            f"{p['filename']}: rows={p['rows']} bytes={p['bytes']} "
            f"sha256={p['sha256'][:12]}..."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
