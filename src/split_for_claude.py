#!/usr/bin/env python3
"""
Investment OS Data Bridge — byte-preserving CSV splitter for Claude transport.

Default behaviour remains production-compatible:
    python src/split_for_claude.py

Optional staging use:
    python src/split_for_claude.py \
        --source data/staging/br04/<run_id>/candidate/sp500_fundamentals.csv \
        --output-dir data/staging/br04/<run_id>/candidate

Critical property:
- CSV records are copied as raw UTF-8 bytes.
- No pandas read/write round-trip is used.
- Reassembling header + all chunk data records reproduces the source byte-for-byte.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "current"
DEFAULT_SOURCE = DEFAULT_DATA_DIR / "sp500_fundamentals.csv"

# Claude had previously truncated a ~68 KB fetch.
TARGET_MAX_BYTES = 48_000
HARD_MAX_BYTES = 58_000

SPLITTER_SCHEMA = "investment_os_byte_preserving_splitter_v1.0"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_records_raw(data: bytes) -> list[bytes]:
    """
    Split CSV into exact raw records, preserving every byte.

    A newline terminates a record only outside quoted fields. Escaped quotes
    ("") inside quoted fields are handled without toggling quote state.
    """
    if not data:
        return []

    records: list[bytes] = []
    start = 0
    i = 0
    in_quotes = False

    while i < len(data):
        b = data[i]

        if b == 0x22:  # "
            if in_quotes and i + 1 < len(data) and data[i + 1] == 0x22:
                i += 2
                continue
            in_quotes = not in_quotes
            i += 1
            continue

        if b == 0x0A and not in_quotes:  # \n
            records.append(data[start : i + 1])
            start = i + 1

        i += 1

    if in_quotes:
        raise ValueError("CSV non valido: campo quotato non chiuso")

    if start < len(data):
        records.append(data[start:])

    return records


def header_column_count(header_record: bytes) -> int:
    text = header_record.decode("utf-8-sig")
    text = text.rstrip("\r\n")
    row = next(csv.reader([text]))
    return len(row)


def derive_url_base(output_dir: Path) -> str:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo:
        return ""

    try:
        rel = output_dir.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return ""

    rel_posix = rel.as_posix()
    return f"https://raw.githubusercontent.com/{repo}/main/{rel_posix}"


def build_ranges(
    header: bytes,
    data_records: list[bytes],
) -> list[tuple[int, int, bytes]]:
    """
    Greedily pack exact raw CSV records under TARGET_MAX_BYTES.
    start/end are zero-based Python slice coordinates over data_records.
    """
    if not data_records:
        if len(header) > HARD_MAX_BYTES:
            raise ValueError("Header CSV supera HARD_MAX_BYTES")
        return [(0, 0, header)]

    if len(header) >= HARD_MAX_BYTES:
        raise ValueError("Header CSV troppo grande per il trasporto")

    ranges: list[tuple[int, int, bytes]] = []
    start = 0

    while start < len(data_records):
        end = start
        size = len(header)

        while end < len(data_records):
            candidate_size = size + len(data_records[end])

            if end == start:
                if candidate_size > HARD_MAX_BYTES:
                    raise ValueError(
                        "Una singola riga CSV più header supera HARD_MAX_BYTES"
                    )
                size = candidate_size
                end += 1
                if size >= TARGET_MAX_BYTES:
                    break
                continue

            if candidate_size > TARGET_MAX_BYTES:
                break

            size = candidate_size
            end += 1

        chunk = header + b"".join(data_records[start:end])
        if len(chunk) > HARD_MAX_BYTES:
            raise ValueError("Chunk supera HARD_MAX_BYTES")

        ranges.append((start, end, chunk))
        start = end

    return ranges


def reassemble_parts(
    *,
    output_dir: Path,
    parts: list[dict],
    header: bytes,
) -> bytes:
    """
    Reassemble chunks without parsing/reserializing CSV.
    The header is retained once; subsequent repeated headers are removed
    byte-for-byte.
    """
    if not parts:
        return b""

    out = bytearray()

    for idx, part in enumerate(parts):
        path = output_dir / part["filename"]
        data = path.read_bytes()

        if not data.startswith(header):
            raise ValueError(
                f"{part['filename']} non inizia con l'header sorgente"
            )

        if idx == 0:
            out.extend(data)
        else:
            out.extend(data[len(header):])

    return bytes(out)


def split_file(
    *,
    source: Path,
    output_dir: Path,
    url_base: str | None = None,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(f"{source} non trovato")

    output_dir.mkdir(parents=True, exist_ok=True)

    raw = source.read_bytes()
    records = csv_records_raw(raw)
    if not records:
        raise ValueError("CSV sorgente vuoto")

    header = records[0]
    data_records = records[1:]

    total_rows = len(data_records)
    total_columns = header_column_count(header)

    for old in output_dir.glob("sp500_fundamentals_part_*.csv"):
        old.unlink()

    if url_base is None:
        url_base = derive_url_base(output_dir)
    url_base = (url_base or "").rstrip("/")

    ranges = build_ranges(header, data_records)
    parts: list[dict] = []

    for i, (start, end, chunk) in enumerate(ranges, start=1):
        filename = f"sp500_fundamentals_part_{i:02d}.csv"
        path = output_dir / filename
        path.write_bytes(chunk)

        info = {
            "part": i,
            "filename": filename,
            "row_start_1_based": start + 1 if total_rows else 0,
            "row_end_1_based": end,
            "rows": end - start,
            "bytes": len(chunk),
            "sha256": sha256_bytes(chunk),
        }

        if url_base:
            info["url"] = f"{url_base}/{filename}"

        parts.append(info)

    total_rows_from_parts = sum(p["rows"] for p in parts)

    contiguous = True
    expected_start = 1
    for p in parts:
        if p["row_start_1_based"] != expected_start:
            contiguous = False
            break
        expected_start = p["row_end_1_based"] + 1

    source_sha = sha256_bytes(raw)
    reassembled = reassemble_parts(
        output_dir=output_dir,
        parts=parts,
        header=header,
    )
    reassembled_sha = sha256_bytes(reassembled)

    validation = {
        "rows_from_parts": total_rows_from_parts,
        "rows_match_source": total_rows_from_parts == total_rows,
        "ranges_contiguous": contiguous
        and (expected_start - 1 == total_rows),
        "all_parts_under_hard_max": all(
            p["bytes"] <= HARD_MAX_BYTES for p in parts
        ),
        "reassembled_byte_identical": reassembled == raw,
        "reassembled_sha256": reassembled_sha,
    }

    index = {
        "schema": SPLITTER_SCHEMA,
        "source": source.name,
        "source_sha256": source_sha,
        "total_rows": total_rows,
        "total_columns": total_columns,
        "target_max_bytes": TARGET_MAX_BYTES,
        "hard_max_bytes": HARD_MAX_BYTES,
        "total_parts": len(parts),
        "byte_preserving": True,
        "transport_validation": validation,
        "parts": parts,
        "rules": [
            "Read every part before full-universe ranking.",
            "Verify source_sha256 and transport_validation before ranking.",
            "MISSING is not zero.",
            "Chunks are transport files only and do not change methodology.",
            "Chunk construction copies raw CSV records; no numeric reserialization.",
            "Finalists must still be reconciled with latest primary filings.",
        ],
    }

    blockers = [
        key
        for key in (
            "rows_match_source",
            "ranges_contiguous",
            "all_parts_under_hard_max",
            "reassembled_byte_identical",
        )
        if not validation[key]
    ]
    if reassembled_sha != source_sha:
        blockers.append("reassembled_sha256_mismatch")

    if blockers:
        raise ValueError(
            "Errore integrità trasporto: " + ", ".join(blockers)
        )

    (output_dir / "fundamentals_chunks.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Investment OS — Fundamentals chunks for Claude",
        "",
        f"- Splitter schema: **{SPLITTER_SCHEMA}**",
        f"- Byte preserving: **True**",
        f"- Total rows: **{total_rows}**",
        f"- Total columns: **{total_columns}**",
        f"- Total parts: **{len(parts)}**",
        f"- Target max bytes per part: **{TARGET_MAX_BYTES}**",
        f"- Source SHA-256: `{source_sha}`",
        f"- Reassembled SHA-256: `{reassembled_sha}`",
        "- Reassembled byte-identical to source: **True**",
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
            f"- Rows match source: **{validation['rows_match_source']}**",
            f"- Ranges contiguous: **{validation['ranges_contiguous']}**",
            f"- All parts <= {HARD_MAX_BYTES} bytes: **{validation['all_parts_under_hard_max']}**",
            f"- Reassembled byte-identical: **{validation['reassembled_byte_identical']}**",
            "",
            "## Regole",
            "",
            "- Non costruire ranking da un sottoinsieme dei chunk.",
            "- MISSING non è zero.",
            "- Applicare Sector Fairness Rule.",
            "- I chunk servono solo al trasporto dei dati.",
            "- Le righe CSV sono copiate byte per byte, senza riletture numeriche.",
            "- Per i finalisti verificare gli ultimi filing SEC/Investor Relations.",
            "",
        ]
    )

    (output_dir / "fundamentals_chunks.md").write_text(
        "\n".join(md),
        encoding="utf-8",
    )

    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="CSV sorgente",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directory di output dei chunk",
    )
    parser.add_argument(
        "--url-base",
        default=None,
        help="Base URL raw opzionale; se omessa viene derivata dal repository",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_absolute():
        source = ROOT / source

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    index = split_file(
        source=source,
        output_dir=output_dir,
        url_base=args.url_base,
    )

    print(
        f"OK — {index['total_rows']} righe / "
        f"{index['total_columns']} colonne divise in "
        f"{index['total_parts']} parti."
    )
    print(
        "Byte-identical reassembly: "
        f"{index['transport_validation']['reassembled_byte_identical']}"
    )

    for p in index["parts"]:
        print(
            f"{p['filename']}: rows={p['rows']} bytes={p['bytes']} "
            f"sha256={p['sha256'][:12]}..."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
