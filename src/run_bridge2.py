#!/usr/bin/env python3
"""BRIDGE-2 in produzione (adottato da Flavio il 22/11/2026, testato in R12-ter).

Esegue bridge.py o enrich_br01_br02.py con la stessa integrazione verificata nel replay R12-ter:
sinonimi XBRL (in bridge.py) + riempimento da SEC companyfacts solo per le stesse filing (accession number)
già selezionate dalla logica invariata. Strettamente additivo: un dato presente nei Financial Statement
Data Sets non viene mai sostituito.
Uso: python src/run_bridge2.py bridge [argomenti di bridge.py] | python src/run_bridge2.py enrich_br01_br02
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bridge  # noqa: E402
import companyfacts_fill  # noqa: E402

_load = bridge.load_submissions_from_zips


def load_submissions_from_zips(*a, **k):
    sub = _load(*a, **k)
    companyfacts_fill.remember_submissions(sub)
    return sub


bridge.load_submissions_from_zips = load_submissions_from_zips
_scan = bridge.scan_relevant_nums


def scan_relevant_nums(zip_infos, adsh_set):
    return companyfacts_fill.augment(_scan(zip_infos, adsh_set), set(adsh_set), bridge.ALL_RELEVANT_TAGS)


bridge.scan_relevant_nums = scan_relevant_nums

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "bridge"
    sys.argv = [target] + sys.argv[2:]
    if target == "bridge":
        rc = bridge.main()
    elif target == "enrich_br01_br02":
        import enrich_br01_br02
        _scan2 = enrich_br01_br02.scan_nums

        def scan_nums(zip_infos, adsh_set, *a, **k):
            return companyfacts_fill.augment(_scan2(zip_infos, adsh_set, *a, **k), set(adsh_set),
                                             enrich_br01_br02.RELEVANT_TAGS)

        enrich_br01_br02.scan_nums = scan_nums
        rc = enrich_br01_br02.main()
    else:
        raise SystemExit(f"target sconosciuto: {target}")
    print("BRIDGE-2 companyfacts:", companyfacts_fill.STATS)
    sys.exit(rc)
