#!/usr/bin/env python3
"""
Il Margine - inserisce i dati del mattino nella pagina, senza ricopiarli a mano.

Uso:  python src/margine_embed.py pagina.html [cartella_dati]

Sostituisce nella pagina:
- il blocco  var DATA=`...`;   con data/current/margine_DATA.txt
- il blocco  var RET=`...`;    con data/current/margine_RET.txt
- il blocco  /*EXT-START*/ ... /*EXT-END*/  con data/current/margine_EXT.js (universo esteso
  dell'osservatorio); se la pagina non ha ancora il blocco, lo aggiunge prima dello script principale.
Le righe dei file entrano senza modifiche. Se un file manca, quel blocco resta com'era.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    page = Path(sys.argv[1])
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "current"
    h = page.read_text(encoding="utf-8")
    for var, fname in (("DATA", "margine_DATA.txt"), ("RET", "margine_RET.txt")):
        f = src / fname
        if not f.exists():
            print(f"{fname} assente: blocco {var} invariato")
            continue
        body = f.read_text(encoding="utf-8").strip("\n")
        assert "`" not in body
        h, n = re.subn(r"var %s=`[^`]*`;" % var, lambda _m: f"var {var}=`{body}`;", h, count=1)
        assert n == 1, f"blocco var {var} non trovato"
        print(f"{var}: {body.count(chr(10)) + 1} righe")
    f = src / "margine_EXT.js"
    if f.exists():
        ext = f.read_text(encoding="utf-8").strip()
        assert ext.startswith("/*EXT-START*/") and ext.endswith("/*EXT-END*/")
        if "/*EXT-START*/" in h:
            h, n = re.subn(r"/\*EXT-START\*/.*?/\*EXT-END\*/", lambda _m: ext, h, count=1, flags=re.S)
        else:
            h, n = h.replace("<script>\n(function(){", "<script>" + ext + "</script>\n<script>\n(function(){", 1), 1
        print("EXT: inserito" if n == 1 else "EXT: posizione non trovata")
    else:
        print("margine_EXT.js assente: blocco EXT invariato")
    page.write_text(h, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
