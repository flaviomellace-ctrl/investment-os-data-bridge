#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "current"

SOURCE = DATA_DIR / "sp500_fundamentals.csv"
ROWS_PER_CHUNK = 55


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit("sp500_fundamentals.csv non trovato")

    df = pd.read_csv(SOURCE, low_memory=False)

    # Elimina eventuali chunk prodotti da run precedenti.
    for old in DATA_DIR.glob("sp500_fundamentals_part_*.csv"):
        old.unlink()

    total_rows = len(df)
    total_parts = max(1, math.ceil(total_rows / ROWS_PER_CHUNK))

    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    base = (
        f"https://raw.githubusercontent.com/{repo}/main/data/current"
        if repo
        else ""
    )

    parts = []

    for i in range(total_parts):
        start = i * ROWS_PER_CHUNK
        end = min(start + ROWS_PER_CHUNK, total_rows)

        part = df.iloc[start:end].copy()

        filename = f"sp500_fundamentals_part_{i + 1:02d}.csv"
        path = DATA_DIR / filename
        part.to_csv(path, index=False)

        info = {
            "part": i + 1,
            "filename": filename,
            "row_start_1_based": start + 1,
            "row_end_1_based": end,
            "rows": len(part),
            "bytes": path.stat().st_size,
        }

        if base:
            info["url"] = f"{base}/{filename}"

        parts.append(info)

    index = {
        "source": "sp500_fundamentals.csv",
        "total_rows": total_rows,
        "rows_per_chunk": ROWS_PER_CHUNK,
        "total_parts": total_parts,
        "parts": parts,
        "rules": [
            "Read every part before full-universe ranking.",
            "MISSING is not zero.",
            "Chunks are transport files only and do not change methodology.",
            "Finalists must still be reconciled with latest primary filings.",
        ],
    }

    (DATA_DIR / "fundamentals_chunks.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Investment OS — Fundamentals chunks for Claude",
        "",
        f"- Total rows: **{total_rows}**",
        f"- Total parts: **{total_parts}**",
        "- Read **all parts** before producing the full-universe BQS ranking.",
        "",
    ]

    for p in parts:
        if "url" in p:
            md.append(
                f"- Part {p['part']:02d}: {p['url']} "
                f"— rows {p['row_start_1_based']}-{p['row_end_1_based']} "
                f"— {p['bytes']} bytes"
            )
        else:
            md.append(
                f"- Part {p['part']:02d}: {p['filename']} "
                f"— rows {p['row_start_1_based']}-{p['row_end_1_based']} "
                f"— {p['bytes']} bytes"
            )

    md.extend(
        [
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
        f"OK — {total_rows} righe divise in {total_parts} parti "
        f"da massimo {ROWS_PER_CHUNK} righe."
    )

    for p in parts:
        print(
            f"{p['filename']}: {p['rows']} righe, "
            f"{p['bytes']} bytes"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
