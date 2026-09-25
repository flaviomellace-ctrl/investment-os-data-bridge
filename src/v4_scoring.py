"""
INVESTMENT OS V4.1 - motore di scoring di riferimento.
Price-independent BQS + IOS disaccoppiato. Nessun parametro e' stato scelto osservando
l'effetto su una societa' specifica: ogni ancora ha una motivazione economica generale
registrata in PARAM_REGISTER.
V3 non e' toccato: questo modulo e' nuovo e separato.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

MISSING = None
NA = "NOT_APPLICABLE"          # metrica non pertinente al modello di business
CONFLICTING = "CONFLICTING"

# ---------------------------------------------------------------- parametri
# (lo, hi) = ancore della funzione lineare 0..1 ; rationale = motivazione economica generale
PARAM_REGISTER: Dict[str, Dict[str, Any]] = {
 "op_margin_general":      dict(lo=0.05, hi=0.35, mid=0.2, why="soglia fra impresa che copre a stento il costo del capitale e impresa con potere di prezzo"),
 "op_margin_marketplace":  dict(lo=0.05, hi=0.30, mid=0.18, why="usata solo come metrica secondaria: il conto economico di un marketplace registra la sola quota monetizzata"),
 "ebitda_on_volume":       dict(lo=0.005, hi=0.06, mid=0.03, why="profitto per unita' di valore intermediato: misura l'economia reale della rete, indipendente dalla presentazione contabile"),
 "fcf_on_volume":          dict(lo=0.003, hi=0.05, mid=0.025, why="cassa per unita' di volume; separa il marketplace che guadagna dal marketplace che sussidia"),
 "take_rate":              dict(lo=0.05, hi=0.30, mid=0.18, why="quota di valore trattenuta; una presa troppo alta invita la disintermediazione, troppo bassa non sostiene il reinvestimento"),
 "fcf_margin":             dict(lo=0.02, hi=0.25, mid=0.14, why="conversione dei ricavi in cassa disponibile al proprietario"),
 "cash_conversion":        dict(lo=0.50, hi=1.20, mid=0.95, why="rapporto cassa/utile: sotto 1 segnala utili non incassati"),
 "roic":                   dict(lo=0.08, hi=0.30, mid=0.18, why="ritorno sul capitale investito contro un costo del capitale reale intorno all'8-10%"),
 "roe_financial":          dict(lo=0.06, hi=0.18, mid=0.13, why="per banche e assicurazioni il ROE sostenibile e' il vero indicatore di economics"),
 "combined_ratio":         dict(lo=1.05, hi=0.90, mid=0.95, why="sotto 100 l'assicuratore guadagna sulla sottoscrizione, non solo sugli investimenti"),
 "ffo_margin":             dict(lo=0.20, hi=0.60, mid=0.45, why="per i REIT il FFO sostituisce l'utile contabile deformato dagli ammortamenti"),
 "regulated_margin":       dict(lo=0.08, hi=0.30, mid=0.2, why="margine operativo su ricavi regolati"),
 "margin_stability":       dict(lo=0.35, hi=0.02, mid=0.1, why="deviazione standard del margine su 3 anni: la persistenza e' evidenza di moat, non il livello di un anno"),
 "revenue_cagr3":          dict(lo=0.00, hi=0.18, mid=0.1, why="crescita pluriennale dei ricavi, immune agli effetti base di un singolo esercizio"),
 "opinc_cagr3":            dict(lo=0.00, hi=0.20, mid=0.11, why="crescita dell'utile operativo: esclude poste finanziarie e fiscali straordinarie"),
 "fcf_cagr3":              dict(lo=0.00, hi=0.20, mid=0.11, why="crescita della cassa, la sola che paga il proprietario"),
 "fcf_per_share_cagr3":    dict(lo=0.00, hi=0.18, mid=0.1, why="crescita per azione: neutralizza la crescita comprata con diluizione"),
 "reinvestment_rate":      dict(lo=0.02, hi=0.20, mid=0.11, why="capex+R&D su ricavi: misura se esiste ancora terreno su cui reinvestire"),
 "two_sided_growth":       dict(lo=0.00, hi=0.15, mid=0.08, why="crescita simultanea dei due lati della rete: una rete che cresce da un lato solo si sbilancia"),
 "retention":              dict(lo=0.70, hi=1.05, mid=0.95, why="ritenzione netta per coorte: sopra 1 il cliente esistente compra di piu' ogni anno"),
 "frequency_growth":       dict(lo=-0.02, hi=0.10, mid=0.04, why="frequenza d'uso crescente: prova che il valore per il cliente aumenta con la scala"),
 "unit_cost_decline":      dict(lo=0.00, hi=0.08, mid=0.04, why="calo del costo unitario con il volume: scale economics, cuore della filosofia Nomad"),
 "share_change":           dict(lo=0.02, hi=-0.03, mid=-0.005, why="variazione azioni diluite: la riduzione e' capital allocation, l'aumento e' un costo per il proprietario"),
 "buyback_accretion":      dict(lo=0.0, hi=2.0, mid=1.2, why="riacquisti su SBC: sotto 1 il buyback compensa solo la diluizione, non restituisce capitale"),
 "sbc_to_revenue":         dict(lo=0.12, hi=0.01, mid=0.04, why="SBC su ricavi: e' un costo reale, pagato in proprieta' invece che in cassa"),
 "net_debt_to_ocf":        dict(lo=4.0, hi=0.0, mid=1.5, why="anni di cassa operativa necessari a estinguere il debito netto"),
 "net_debt_to_ocf_util":   dict(lo=7.0, hi=2.0, mid=4.0, why="le utility regolate sostengono strutturalmente piu' leva a fronte di ricavi prevedibili"),
 "net_debt_to_ocf_reit":   dict(lo=8.0, hi=3.0, mid=5.0, why="i REIT finanziano attivi reali a lunga durata"),
 "equity_to_assets_bank":  dict(lo=0.05, hi=0.12, mid=0.09, why="capitale su attivo: per una banca la solidita' non si misura con debito/patrimonio"),
 "interest_coverage":      dict(lo=2.0, hi=12.0, mid=8.0, why="EBIT su oneri finanziari: capacita' di servire il debito in anni deboli"),
 "accrual_quality":        dict(lo=0.7, hi=1.4, mid=1.05, why="OCF/utile netto: divergenze persistenti segnalano utili di qualita' bassa"),
 "roe_sustainable_bank":   dict(lo=0.06, hi=0.18, mid=0.13, why="ROE sostenibile: per una banca il valore economico nasce dal ritorno sul capitale proprio, non da un flusso di cassa operativo che riflette movimenti di raccolta e impieghi"),
 "affo_payout":            dict(lo=1.00, hi=0.60, mid=0.75, why="AFFO payout di un REIT: sotto il 100% il dividendo e' coperto dalla cassa ricorrente e resta capacita' di reinvestimento"),
 "base_effect_gap":        dict(lo=0.25, hi=0.25, mid=0.25, why="divergenza fra crescita utile netto e utile operativo oltre 25 punti in un anno: quasi sempre non operativa (fiscale, minoranze, poste una tantum). Soglia di ALLERTA, non di punteggio: attiva una verifica, non penalizza"),
 "prior_year_jump":        dict(lo=2.5, hi=2.5, mid=2.5, why="utile dell'anno precedente piu' che raddoppiato: base di confronto sospetta per la crescita YoY"),
}

GOOD_ANCHOR = 0.75   # il livello "impresa di buona qualita'" vale 0.75 della scala

def lin(x, key):
    """Mappa spezzata calibrata sulle BANDE della Costituzione (par. 8), non su una societa'.
    Tre ancore per metrica: lo = soglia sotto la quale la qualita' e' insufficiente (0.0),
    mid = livello di un'impresa di BUONA qualita' (0.75), hi = livello ECCEZIONALE (1.0).
    Una mappa lineare lo->hi collocherebbe implicitamente l'impresa buona a meta' scala e
    renderebbe le bande 70-79 / 80-89 / >=90 irraggiungibili: la spezzata rende il punteggio
    leggibile con il significato che la Costituzione gli attribuisce."""
    p = PARAM_REGISTER[key]; lo, hi = p["lo"], p["hi"]; mid = p.get("mid")
    if x is None or x == NA or x == CONFLICTING: return None
    if mid is None or hi == lo or mid == lo or mid == hi:
        return max(0.0, min(1.0, (x - lo) / (hi - lo))) if hi != lo else 0.0
    t1 = (x - lo) / (mid - lo)
    if t1 <= 1.0:
        return max(0.0, t1) * GOOD_ANCHOR
    t2 = (x - mid) / (hi - mid)
    return min(1.0, GOOD_ANCHOR + max(0.0, t2) * (1.0 - GOOD_ANCHOR))

# ---------------------------------------------------------------- moduli settoriali
MODULES = ["MARKETPLACE_NETWORK","SOFTWARE","SEMICONDUCTOR","INDUSTRIAL","BANK",
           "INSURANCE","REIT","UTILITY","RESOURCES","ASSETMGR_EXCH","GENERAL"]

def economics_spec(mod):
    if mod == "MARKETPLACE_NETWORK":
        # margine su ricavi netti ESCLUSO dal punteggio: dipende dalla presentazione contabile
        # (lordo vs netto) e non dall'economia della rete. Resta nel dossier come diagnostica.
        return [("ebitda_on_volume","ebitda_on_volume",10),("fcf_on_volume","fcf_on_volume",8),
                ("take_rate","take_rate",4),("cash_conversion","cash_conversion",3)]
    if mod in ("BANK","ASSETMGR_EXCH"):
        return [("roe","roe_financial",14),("net_margin","fcf_margin",6),("accrual_quality","accrual_quality",5)]
    if mod == "INSURANCE":
        return [("combined_ratio","combined_ratio",12),("roe","roe_financial",9),("net_margin","fcf_margin",4)]
    if mod == "REIT":
        return [("ffo_margin","ffo_margin",13),("occupancy","retention",6),("net_debt_to_ocf","net_debt_to_ocf_reit",6)]
    if mod == "UTILITY":
        return [("op_margin","regulated_margin",13),("roic","roic",7),("accrual_quality","accrual_quality",5)]
    return [("op_margin","op_margin_general",9),("fcf_margin","fcf_margin",8),
            ("roic","roic",5),("cash_conversion","cash_conversion",3)]

def moat_spec(mod):
    base = [("margin_stability","margin_stability",8),("roic","roic",7)]
    if mod == "MARKETPLACE_NETWORK":
        return base + [("two_sided_growth","two_sided_growth",4),("retention","retention",3),
                       ("unit_cost_decline","unit_cost_decline",2),("frequency_growth","frequency_growth",1)]
    if mod in ("BANK","INSURANCE","ASSETMGR_EXCH"):
        return [("roe","roe_financial",12),("margin_stability","margin_stability",8),("retention","retention",5)]
    return base + [("retention","retention",5),("unit_cost_decline","unit_cost_decline",5)]

def runway_spec(mod):
    return [("revenue_cagr3","revenue_cagr3",7),("opinc_cagr3","opinc_cagr3",5),
            ("fcf_cagr3","fcf_cagr3",4),("reinvestment_rate","reinvestment_rate",4)]

def mgmt_spec(mod):
    return [("share_change","share_change",5),("buyback_accretion","buyback_accretion",4),
            ("sbc_to_revenue","sbc_to_revenue",3),("fcf_per_share_cagr3","fcf_per_share_cagr3",3)]

def balance_spec(mod):
    if mod == "BANK": return [("equity_to_assets","equity_to_assets_bank",7),("accrual_quality","accrual_quality",3)]
    if mod == "UTILITY": return [("net_debt_to_ocf","net_debt_to_ocf_util",7),("interest_coverage","interest_coverage",3)]
    if mod == "REIT": return [("net_debt_to_ocf","net_debt_to_ocf_reit",7),("interest_coverage","interest_coverage",3)]
    return [("net_debt_to_ocf","net_debt_to_ocf",7),("interest_coverage","interest_coverage",3)]

def governance_spec(mod):
    return [("accrual_quality","accrual_quality",3)]   # + copertura dati, gestita a parte

COMPONENTS = [("economics",25,economics_spec),("moat",25,moat_spec),("runway",20,runway_spec),
              ("mgmt",15,mgmt_spec),("balance",10,balance_spec),("governance",5,governance_spec)]

# ---------------------------------------------------------------- growth normalization
def normalize_growth(c: dict) -> dict:
    """Declassa la variazione YoY dell'utile netto e segnala gli effetti base.
    Non inventa dati: se le serie pluriennali mancano, restano MISSING."""
    flags = []
    ni_yoy, oi_yoy = c.get("ni_yoy"), c.get("opinc_yoy")
    if ni_yoy is not None and oi_yoy is not None and abs(ni_yoy - oi_yoy) > PARAM_REGISTER['base_effect_gap']['lo']:
        flags.append("BASE_EFFECT_SUSPECTED")
    hist = c.get("net_income_series")           # [t-3, t-2, t-1, t]
    if hist and len(hist) >= 3 and all(h not in (None, 0) for h in hist[:-1]):
        prev, prev2 = hist[-2], hist[-3]
        if prev2 and prev / prev2 > PARAM_REGISTER['prior_year_jump']['lo']:
            flags.append("PRIOR_YEAR_ONE_OFF_SUSPECTED")
    c = dict(c); c["growth_flags"] = flags
    if flags:
        c["ni_yoy_used_in_score"] = False       # escluso dal punteggio, resta nel dossier
    return c

# ---------------------------------------------------------------- BQS
def bqs(c: dict):
    c = normalize_growth(c)
    mod = c.get("module","GENERAL")
    detail, tot_w, avail_w = {}, 0.0, 0.0
    metric_w_tot, metric_w_avail, prov = 0.0, 0.0, []
    for name, weight, spec_fn in COMPONENTS:
        specs = spec_fn(mod)
        pairs = []
        for key, param, w in specs:
            v = c.get(key, MISSING)
            na = (v == NA)
            s_ = None if v in (MISSING, NA, CONFLICTING) else lin(v, param)
            pairs.append((s_, w, na))
        got = [(s_, w) for s_, w, na in pairs if s_ is not None]
        tw = sum(w for _, w, _ in pairs); aw = sum(w for _, w in got)
        # le metriche NOT_APPLICABLE non contano come copertura mancante: non sono pertinenti
        applicable_w = sum(w for _, w, na in pairs if not na)
        metric_w_tot += applicable_w; metric_w_avail += aw
        tot_w += weight
        if aw == 0:
            # BUGFIX V4.1: una componente COMPLETAMENTE priva di dati non puo' limitarsi a
            # sparire dal punteggio. Escluderla in silenzio ridistribuisce il suo peso sulle
            # altre e lascia intatta la confidence: il sistema dichiarerebbe di sapere piu' di
            # quanto sa. Non sapere NULLA di una componente e' peggio, non meglio, che saperne
            # meta'. Distinzione necessaria (par. 5): se nessuna metrica e' APPLICABILE
            # (applicable_w == 0) la componente non e' pertinente al modello di business e
            # NOT_APPLICABLE non e' un'assenza di dati: in quel caso nessun PROVISIONAL.
            if applicable_w > 0:
                prov.append(name)
            detail[name] = None; continue
        val = sum(s_ * w for s_, w in got) / aw * weight
        if applicable_w > 0 and aw / applicable_w < 0.60:
            prov.append(name)          # componente PROVISIONAL: troppe metriche mancanti
        if name == "governance":
            cov = c.get("data_coverage_pct", 0) or 0
            val = min(weight, val * 0.6 + (3.0 if cov >= 99 else 2.0 if cov >= 83 else 1.0 if cov >= 66 else 0.0))
        detail[name] = round(val, 2); avail_w += weight
    if avail_w == 0: return None, 0.0, detail, c.get("growth_flags", [])
    score = sum(v for k, v in detail.items() if v is not None and not k.startswith("_")) / avail_w * tot_w
    coverage = avail_w / tot_w * 100
    metric_cov = (metric_w_avail / metric_w_tot * 100) if metric_w_tot else 0.0
    detail["_metric_coverage_pct"] = round(metric_cov, 1)
    detail["_provisional_components"] = prov
    return round(score, 1), round(coverage, 1), detail, c.get("growth_flags", [])

def bqs_confidence(bqs_cov, data_cov, status, metric_cov=100.0, provisional=()):
    """La ridistribuzione dei pesi puo' ALZARE un punteggio quando manca una metrica debole:
    per questo la copertura a livello di metrica entra nella confidence e, sotto il 70%,
    il punteggio e' PROVISIONAL (par. 30)."""
    if provisional or metric_cov < 70: return "PROVISIONAL"
    if bqs_cov >= 90 and metric_cov >= 90 and data_cov >= 99 and status == "PRESENT": return "HIGH"
    if bqs_cov >= 80 and metric_cov >= 80 and data_cov >= 83: return "MEDIUM"
    return "LOW"

# ---------------------------------------------------------------- IOS
IOS_GATE = dict(min_bqs=60.0, min_data_coverage=70.0)

def discount_rate(mod, net_debt_to_ocf, bqs_score):
    r = 0.095
    if mod in ("SEMICONDUCTOR","RESOURCES","MARKETPLACE_NETWORK"): r += 0.010
    if mod in ("BANK","INSURANCE"): r += 0.010
    if net_debt_to_ocf is not None and net_debt_to_ocf not in (NA,) and net_debt_to_ocf > 3.0: r += 0.010
    if bqs_score is not None and bqs_score < 70: r += 0.005
    return round(r, 4)

def two_stage_dcf(cf, g1, years, gt, r):
    v, f = 0.0, cf
    for _ in range(years):
        f *= (1 + g1); v += f / (1 + r) ** (_ + 1)
    return v + (f * (1 + gt) / (r - gt)) / (1 + r) ** years

# ---- instradamento dell'IOS per modello economico (V4.1) --------------------
# owner_earnings = OCF - capex - SBC descrive un'impresa che produce cassa operativa
# liberamente reinvestibile. Non descrive una banca (l'OCF riflette raccolta e impieghi),
# un assicuratore (riflette riserve e sinistri) o un REIT (il capex mescola manutenzione
# e sviluppo). Applicarlo a questi modelli non e' prudenza: e' misura sbagliata.
IOS_VARIANTS = {
    "BANK": "IOS_BANK", "ASSETMGR_EXCH": "IOS_BANK",
    "INSURANCE": "IOS_INSURANCE",
    "REIT": "IOS_REIT",
}
def ios_variant(mod): return IOS_VARIANTS.get(mod, "IOS_GENERAL")

def _equity_value(c, r, roe_key="roe"):
    """Gordon sul capitale proprio: V = BV * (ROE - g) / (r - g).
    Base per banche e assicurazioni: il valore nasce dal ritorno sul capitale, non dall'OCF.
    La SBC NON viene sottratta: l'utile netto GAAP la ha gia' spesata (par. 12, no doppio conteggio)."""
    bv, roe = c.get("book_value"), c.get(roe_key)
    if bv in (None, 0, NA, CONFLICTING) or roe in (None, NA, CONFLICTING): return None, None, None
    payout = c.get("payout_ratio")
    g = roe * (1 - payout) if payout is not None else c.get("sustainable_growth")
    if g is None: return None, None, None
    g = max(0.0, min(g, 0.08))                    # crescita sostenibile limitata: ROE*ritenzione
    if r - g < 0.02: g = r - 0.02
    earnings = bv * roe
    return bv * (roe - g) / (r - g), earnings, g

def ios(c: dict, bqs_score, bqs_cov):
    """Calcolato per OGNI societa' con BQS>=60 e data coverage>=70. Il prezzo entra solo qui.
    L'ancoraggio economico dipende dal modello: vedi IOS_VARIANTS."""
    if bqs_score is None or bqs_score < IOS_GATE["min_bqs"]: return None, {"gate": "BQS<60"}
    if (c.get("data_coverage_pct") or 0) < IOS_GATE["min_data_coverage"]: return None, {"gate": "coverage<70"}
    mod = c.get("module", "GENERAL"); variant = ios_variant(mod)
    mc = c.get("market_cap")
    if mc in (None, 0): return None, {"gate": "market cap MISSING", "variant": variant}
    r = discount_rate(mod, c.get("net_debt_to_ocf"), bqs_score)

    if variant in ("IOS_BANK", "IOS_INSURANCE"):
        base, earnings, g = _equity_value(c, r)
        if base is None:
            return None, {"gate": "book value / ROE / crescita sostenibile MISSING", "variant": variant}
        if variant == "IOS_INSURANCE":
            cr = c.get("combined_ratio")
            if cr in (None, NA, CONFLICTING):
                return None, {"gate": "combined ratio MISSING: sottoscrizione non valutabile",
                              "variant": variant}
        bear = base * 0.75 if g > 0 else base * 0.80
        bull = base * 1.30
        owner, dil = earnings, c.get("share_change") or 0.0
        exp_ret = owner / mc + min(g, 0.10) - max(0.0, dil)
        detail_extra = dict(variant=variant, basis="utile normalizzato su capitale proprio",
                            sustainable_growth=round(g, 4))
    elif variant == "IOS_REIT":
        affo = c.get("affo")                       # FFO - capex di manutenzione ricorrente
        if affo in (None, NA, CONFLICTING):
            return None, {"gate": "AFFO MISSING: FFO e capex di manutenzione non separati",
                          "variant": variant}
        g = c.get("revenue_cagr3")
        g = 0.0 if g in (None, NA, CONFLICTING) else max(0.0, min(g, 0.06))
        base = two_stage_dcf(affo, g, 5, 0.020, r)
        bear = two_stage_dcf(affo, max(0.0, g - 0.03), 5, 0.010, r + 0.01)
        bull = two_stage_dcf(affo, g + 0.02, 5, 0.025, r - 0.005)
        owner, dil = affo, c.get("share_change") or 0.0
        exp_ret = owner / mc + min(g, 0.06) - max(0.0, dil)
        detail_extra = dict(variant=variant, basis="AFFO", growth_used=round(g, 4))
    else:
        ocf, capex, sbc = c.get("ocf"), c.get("capex"), c.get("sbc")
        if ocf is None: return None, {"gate": "cassa operativa MISSING", "variant": variant}
        fcf = ocf - (capex or 0.0)
        owner = fcf - (sbc or 0.0)                # owner earnings prudenziali (par. 12)
        g = c.get("revenue_cagr3")
        g = 0.0 if g in (None, NA, CONFLICTING) else max(0.0, min(g, 0.15))
        dil = c.get("share_change") or 0.0
        base = two_stage_dcf(owner, min(g, 0.12), 5, 0.025, r)
        bear = two_stage_dcf(owner, max(0.0, min(g, 0.12) - 0.04), 5, 0.015, r + 0.01)
        bull = two_stage_dcf(owner, min(g, 0.12) + 0.03, 5, 0.030, r - 0.005)
        exp_ret = owner / mc + min(g, 0.10) - max(0.0, dil)
        detail_extra = dict(variant=variant, basis="owner earnings = OCF - capex - SBC",
                            fcf=fcf, growth_used=round(g, 4))

    # ---- corpo comune: gli stessi cinque pesi costituzionali per ogni variante
    oy = owner / mc
    mos = base / mc - 1
    up, down = bull / mc - 1, 1 - bear / mc
    def sc(x, lo, hi, p): return max(0.0, min(1.0, (x - lo) / (hi - lo))) * p
    hurdle = c.get("hurdle", 0.12)
    s = (sc(exp_ret, 0.04, 0.16, 30) + sc(mos, -0.30, 0.60, 25) + sc(up - max(down, 0), 0.0, 1.5, 20)
         + bqs_score / 100 * 15 + sc(exp_ret - hurdle, -0.06, 0.06, 10))
    return round(s, 1), dict(owner_earnings=owner, owner_yield=round(oy, 4), r=r,
                             exp_ret=round(exp_ret, 4), mos=round(mos, 3),
                             bear=round(bear / mc - 1, 3), bull=round(up, 3), **detail_extra)

# ---------------------------------------------------------------- optionality (nessun punto)
def optionality_flag(c: dict):
    reasons = []
    if c.get("embedded_option_desc"): reasons.append(c["embedded_option_desc"])
    if not reasons: return dict(flag=False, points=0, requires_qualitative_review=False)
    return dict(flag=True, points=0, requires_qualitative_review=True, reasons=reasons,
                note="L'optionality non attribuisce punti a BQS o IOS: obbliga alla verifica qualitativa in deep dive.")

# ---------------------------------------------------------------- transport integrity
def validate_row(raw: str, schema: List[str], sep="|"):
    parts = raw.split(sep)
    if len(parts) == len(schema): return dict(ok=True, row=dict(zip(schema, parts)), status="PRESENT")
    return dict(ok=False, row=None, status="SCHEMA_MISMATCH",
                detail=f"attesi {len(schema)} campi, trovati {len(parts)}")

def ingest_row(raw, schema, refetch=None, max_retries=2):
    """Rilegge la riga difettosa prima di marcarla. MISSING/CONFLICTING solo dopo il recupero fallito."""
    res = validate_row(raw, schema); attempts = 0
    while not res["ok"] and refetch and attempts < max_retries:
        attempts += 1
        raw2 = refetch(attempts)
        if raw2 is None: break
        res = validate_row(raw2, schema)
    if res["ok"]:
        return dict(status="PRESENT", row=res["row"], repaired=attempts > 0, attempts=attempts)
    return dict(status="CONFLICTING", row=None, repaired=False, attempts=attempts,
                reason=res.get("detail"), note="fuori dal ranking, dentro l'universo, mai azzerata")

# ---------------------------------------------------------------- gate finale
def can_emit_buy(system_live: bool, decision_gate_done: bool, unresolved_red_flag: bool,
                 unresolved_data_conflict: bool):
    if not system_live: return False, "sistema NOT LIVE: IPS non confermato (par. 15)"
    if not decision_gate_done: return False, "Decision Gate a tre analisi non completato (par. 13)"
    if unresolved_red_flag: return False, "red flag irrisolta (par. 13)"
    if unresolved_data_conflict: return False, "conflitto dati materiale non risolto: INVESTIGARE (par. 13)"
    return True, "condizioni soddisfatte"
