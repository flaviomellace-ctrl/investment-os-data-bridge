#!/usr/bin/env python3
"""Render the integrated run as an operator report. Research mode only: it never emits BUY/ADD."""
import json, sys
from pathlib import Path

WHY = {"NOT_IN_DEEP_DIVE_QUEUE": "fuori dalla coda di approfondimento", "IOS_NOT_CALCULABLE": "IOS non calcolabile",
       "MARKET_DATA_NOT_PRESENT": "dato di mercato assente", "BR09_PROVISIONAL": "classificazione marketplace non documentata",
       "CASH_QUALITY_NOT_REVIEWED_EVIDENCE_MISSING": "qualità della cassa non revisionata",
       "CASH_QUALITY_RECONCILE_CASH_QUALITY": "qualità della cassa da riconciliare",
       "COMMITMENTS_NOT_REVIEWED_EVIDENCE_MISSING": "impegni non revisionati", "COMMITMENTS_INVESTIGARE": "impegno materiale non quantificato",
       "COMMITMENT_INVENTORY_NOT_ATTESTED": "inventario degli impegni non attestato come completo",
       "QUALITY_FLAGS_NOT_REVIEWED": "una tantum e ciclicità non revisionate", "UNRESOLVED_ECONOMIC_CASE": "rilievi economici aperti",
       "INDEPENDENT_ECONOMIC_CLEARANCE_MISSING": "clearance economica indipendente assente"}


def render(run: dict) -> str:
    rows = {r["entity_key"]: r for r in run["results"]}
    eligible = [r for r in run["results"] if r["decision"]["allowed_under_hypothetical_live_state"]]
    out = ["# Investment OS V4.2 — rapporto operativo (modalità ricerca)", "",
           "## COSA DEVI FARE", "",
           "NON FARE NULLA sul broker. Sistema NOT LIVE: nessun BUY/ADD è emesso.",
           f"Entità che hanno superato tutti i controlli della pipeline: {len(eligible)}"
           + (" (" + ", ".join(r['entity_key'] for r in eligible) + "): candidabili al Decision Gate a tre analisi, non all'acquisto." if eligible else "."),
           "Per le entità in coda l'azione è INVESTIGARE: completa le voci mancanti elencate sotto.", "",
           f"Candidato: `{run['inputs']['candidate_sha256']}` · righe {run['rows']} · IOS calcolabili {run['ios_gate_counts'].get('CALCULABLE', 0)} · pipeline {run['pipeline_version']}",
           "", "## Coda di approfondimento", "",
           "| # | Entità | Lane | Modulo | BQS | IOS | Conflitti di dato | Cosa manca |", "|---|---|---|---|---|---|---|---|"]
    for q in run["deep_dive_queue"]:
        r = rows[q["entity_key"]]
        why = "; ".join(WHY.get(x, x) for x in r["decision"]["unresolved_reasons"]) or "nulla"
        if r["decision"]["economic_flag_ids"]:
            why += f" ({len(r['decision']['economic_flag_ids'])})"
        out.append(f"| {q['queue_rank']} | {r['entity_key']} | {q['selection_lane']} | {r['module_final']} | {r['bqs']} ({r['bqs_confidence']}) | {r['ios']} | "
                   f"{', '.join(r.get('open_data_conflicts') or []) or 'no'} | {why} |")
    conf = [r for r in run["results"] if r.get("open_data_conflicts")]
    out += ["", "## Conflitti di dato aperti con la fonte primaria", ""]
    out += [f"- {r['entity_key']}: {', '.join(r['open_data_conflicts'])}" for r in conf] or ["- nessuno registrato"]
    out += ["", "## Gate IOS sull'universo", ""] + [f"- {k}: {v}" for k, v in run["ios_gate_counts"].items()]
    out += ["", "BQS PROVISIONAL significa che mancano metriche essenziali: il numero non va letto come preciso."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    run = json.loads(Path(sys.argv[1]).read_text())
    Path(sys.argv[2]).write_text(render(run))
