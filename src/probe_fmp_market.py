#!/usr/bin/env python3
import os
import requests

KEY = os.getenv("FMP_API_KEY", "").strip()
if not KEY:
    raise SystemExit("FMP_API_KEY non configurata")

session = requests.Session()
session.headers.update({"User-Agent": "InvestmentOSDataBridge/1.0"})


def show(name, url, params):
    try:
        r = session.get(url, params=params, timeout=30)
        print(f"{name}: HTTP {r.status_code}")

        if r.status_code != 200:
            print(
                "  endpoint non disponibile con il piano corrente "
                "oppure richiesta non supportata"
            )
            return

        try:
            data = r.json()
        except Exception:
            data = None

        if isinstance(data, list):
            print(f"  righe: {len(data)}")

            if data:
                row = data[0]
                print(
                    "  price presente:",
                    "price" in row and row.get("price") not in (None, 0, ""),
                )
                print(
                    "  marketCap presente:",
                    (
                        "marketCap" in row
                        and row.get("marketCap") not in (None, 0, "")
                    )
                    or (
                        "mktCap" in row
                        and row.get("mktCap") not in (None, 0, "")
                    ),
                )
                print(
                    "  timestamp presente:",
                    "timestamp" in row
                    and row.get("timestamp") not in (None, ""),
                )
        else:
            print("  risposta non-lista; nessun dato sensibile stampato")

    except Exception:
        print(
            f"{name}: errore di connessione/richiesta "
            "(chiave non stampata)"
        )


show(
    "legacy_batch_quote",
    "https://financialmodelingprep.com/api/v3/quote/AAPL,MSFT",
    {"apikey": KEY},
)

show(
    "stable_profile_single",
    "https://financialmodelingprep.com/stable/profile",
    {"symbol": "AAPL", "apikey": KEY},
)

show(
    "stable_profile_bulk_part0",
    "https://financialmodelingprep.com/stable/profile-bulk",
    {"part": 0, "apikey": KEY},
)

show(
    "stable_quote_single",
    "https://financialmodelingprep.com/stable/quote",
    {"symbol": "AAPL", "apikey": KEY},
)

show(
    "stable_quote_multi",
    "https://financialmodelingprep.com/stable/quote",
    {"symbol": "AAPL,MSFT", "apikey": KEY},
)
