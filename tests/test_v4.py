"""Regression test V4. Archetipi SINTETICI: nessun ticker reale, nessuna calibrazione su societa'."""
import copy, sys
from v4_scoring import (bqs, ios, lin, optionality_flag, ingest_row, can_emit_buy,
                        PARAM_REGISTER, NA, IOS_GATE, ios_variant, economics_spec)

FAIL=[]
def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond: FAIL.append(name)

BASE = dict(module="GENERAL", op_margin=0.22, fcf_margin=0.18, roic=0.19, cash_conversion=1.05,
            margin_stability=0.05, retention=0.95, unit_cost_decline=0.02,
            revenue_cagr3=0.11, opinc_cagr3=0.12, fcf_cagr3=0.10, reinvestment_rate=0.09,
            share_change=-0.01, buyback_accretion=1.6, sbc_to_revenue=0.04, fcf_per_share_cagr3=0.11,
            net_debt_to_ocf=1.2, interest_coverage=9.0, accrual_quality=1.1,
            data_coverage_pct=100.0, market_cap=100e9, ocf=9e9, capex=1e9, sbc=0.6e9)

# T1 - il prezzo non tocca il BQS
a=copy.deepcopy(BASE); b=copy.deepcopy(BASE); b["market_cap"]=BASE["market_cap"]*3
check("T1 BQS price-independent", bqs(a)[0]==bqs(b)[0], f"{bqs(a)[0]} == {bqs(b)[0]}")

# T2 - MISSING non e' zero
m=copy.deepcopy(BASE); m["roic"]=None
z=copy.deepcopy(BASE); z["roic"]=0.0
s_miss,cov_miss,d_miss,_=bqs(m); s_zero,_,_,_=bqs(z); s_full,cov_full,d_full,_=bqs(a)
check("T2 MISSING != 0", s_miss>s_zero, f"missing {s_miss} vs zero {s_zero} (pieno {s_full})")
check("T2b la ridistribuzione e' tracciata dalla copertura metrica",
      d_miss["_metric_coverage_pct"]<d_full["_metric_coverage_pct"],
      f"metric coverage {d_miss['_metric_coverage_pct']}% vs {d_full['_metric_coverage_pct']}%")
from v4_scoring import bqs_confidence
heavy=copy.deepcopy(BASE)
for k in ["roic","cash_conversion","fcf_margin"]: heavy[k]=None
sh,ch,dh,_=bqs(heavy)
check("T2c molte metriche mancanti -> PROVISIONAL",
      bqs_confidence(ch,100.0,"PRESENT",dh["_metric_coverage_pct"],dh["_provisional_components"])=="PROVISIONAL",
      f"metric coverage {dh['_metric_coverage_pct']}%, componenti provisional {dh['_provisional_components']}")

# T3 - NOT_APPLICABLE per modulo
bank=dict(BASE, module="BANK", roe=0.14, net_margin=0.28, equity_to_assets=0.09,
          net_debt_to_ocf=NA, op_margin=NA, fcf_margin=NA)
sb,cb,db,_=bqs(bank)
check("T3 banca valutata senza metriche non pertinenti", sb is not None and db["economics"] is not None,
      f"BQS {sb}, economics {db['economics']}, coverage {cb}%")
util=dict(BASE, module="UTILITY", op_margin=0.24, fcf_margin=NA, roic=0.07, net_debt_to_ocf=5.0)
su,_,du,_=bqs(util)
check("T3b utility: FCF NOT_APPLICABLE senza penalita' arbitraria", su is not None and du["balance"] is not None, f"BQS {su}")

# T4 - invarianza alla presentazione contabile (marketplace)
# stessa economia: 100 di volume, 4 di profitto operativo, 3,5 di cassa, take economico 20%
gross=dict(BASE, module="MARKETPLACE_NETWORK", ebitda_on_volume=0.04, fcf_on_volume=0.035,
           take_rate=0.20, op_margin=0.04, fcf_margin=0.035, two_sided_growth=0.09,
           retention=1.02, frequency_growth=0.04, unit_cost_decline=0.03)
net=dict(gross, op_margin=0.20, fcf_margin=0.175)   # sola presentazione cambiata
_,_,dg,_=bqs(gross); _,_,dn,_=bqs(net)
diff_v4=abs(dg["economics"]-dn["economics"])
def v3_style_econ(c):   # replica della lente V3: solo margini su ricavi
    pairs=[(lin(c["op_margin"],"op_margin_general"),10),(lin(c["fcf_margin"],"fcf_margin"),8),
           (lin(c["roic"],"roic"),7)]
    return sum(s*w for s,w in pairs)/25*25
diff_v3=abs(v3_style_econ(gross)-v3_style_econ(net))
check("T4 invarianza presentazione lordo/netto (V4)", diff_v4<=0.01, f"delta economics V4 = {diff_v4:.2f} punti")
check("T4b la stessa coppia sotto la lente V3 divergeva", diff_v3>5.0, f"delta economics V3 = {diff_v3:.2f} punti")

# T5 - effetto base sull'utile
oneoff=dict(BASE, ni_yoy=0.02, opinc_yoy=0.30, net_income_series=[1.0,1.9,9.9,10.1])
_,_,_,flags=bqs(oneoff)
check("T5 effetto base rilevato", "BASE_EFFECT_SUSPECTED" in flags and "PRIOR_YEAR_ONE_OFF_SUSPECTED" in flags, str(flags))
clean=dict(BASE, ni_yoy=0.12, opinc_yoy=0.13, net_income_series=[7.0,8.0,9.0,10.1])
_,_,_,f2=bqs(clean)
check("T5b nessun falso positivo su crescita regolare", f2==[], str(f2))
check("T5c la crescita non dipende dallo YoY dell'utile netto",
      bqs(oneoff)[2]["runway"]==bqs(clean)[2]["runway"], "runway identico: guidato dai CAGR")

# T6 - IOS disaccoppiato dal rango BQS
mid=dict(BASE, op_margin=0.15, fcf_margin=0.13, roic=0.14, margin_stability=0.09,
         revenue_cagr3=0.09, opinc_cagr3=0.09, fcf_cagr3=0.08, retention=0.92,
         unit_cost_decline=0.01, buyback_accretion=1.1, market_cap=40e9)
sm,cm,_,_=bqs(mid); im,det=ios(mid,sm,cm)
check("T6 IOS calcolato per BQS>=60 fuori dalla Top 30", 60<=sm<80 and im is not None,
      f"BQS {sm} -> IOS {im}")
low=dict(mid, op_margin=0.02, fcf_margin=0.01, roic=0.03, margin_stability=0.30,
         revenue_cagr3=0.0, opinc_cagr3=0.0, fcf_cagr3=0.0, share_change=0.05,
         buyback_accretion=0.2, sbc_to_revenue=0.11, net_debt_to_ocf=3.9, interest_coverage=2.1,
         accrual_quality=0.75, fcf_per_share_cagr3=0.0, reinvestment_rate=0.02, retention=0.72,
         unit_cost_decline=0.0)
sl,cl,_,_=bqs(low); il,gate=ios(low,sl,cl)
check("T6b sotto BQS 60 nessun IOS", sl<60 and il is None, f"BQS {sl}, gate {gate.get('gate')}")

# T7 - integrita' del trasporto
schema=["ticker","a","b","c"]
tries={"n":0}
def refetch(attempt):
    tries["n"]=attempt
    return "XX|1|2|3" if attempt>=1 else None
r_ok=ingest_row("XX|1|2", schema, refetch=refetch)
check("T7 riga difettosa riparata prima di marcarla", r_ok["status"]=="PRESENT" and r_ok["repaired"], str(r_ok["status"]))
r_bad=ingest_row("YY|1|2", schema, refetch=lambda a: None)
check("T7b riparazione fallita -> CONFLICTING, non zero", r_bad["status"]=="CONFLICTING" and r_bad["row"] is None)

# T8 - buyback accrescitivo vs compensazione della diluizione
acc=dict(BASE, buyback_accretion=2.0, share_change=-0.04, sbc_to_revenue=0.02)
off=dict(BASE, buyback_accretion=0.4, share_change=0.01, sbc_to_revenue=0.09)
check("T8 buyback accrescitivo premiato sopra la semplice compensazione",
      bqs(acc)[2]["mgmt"]>bqs(off)[2]["mgmt"]+2, f"{bqs(acc)[2]['mgmt']} vs {bqs(off)[2]['mgmt']}")

# T9 - determinismo
check("T9 determinismo", bqs(copy.deepcopy(BASE))==bqs(copy.deepcopy(BASE)))

# T10 - nessun BUY con sistema NOT LIVE o gate incompleto
check("T10 nessun BUY se NOT LIVE", can_emit_buy(False,True,False,False)[0] is False)
check("T10b nessun BUY senza Decision Gate", can_emit_buy(True,False,False,False)[0] is False)
check("T10c nessun BUY con red flag irrisolta", can_emit_buy(True,True,True,False)[0] is False)
check("T10d nessun BUY con conflitto dati", can_emit_buy(True,True,False,True)[0] is False)
check("T10e con tutte le condizioni il gate apre", can_emit_buy(True,True,False,False)[0] is True)

# T11 - optionality non attribuisce punti
op_no=dict(BASE); op_yes=dict(BASE, embedded_option_desc="opzione strategica materiale")
check("T11 optionality non muove il BQS", bqs(op_no)[0]==bqs(op_yes)[0])
f=optionality_flag(op_yes)
check("T11b optionality obbliga la verifica qualitativa", f["flag"] and f["points"]==0 and f["requires_qualitative_review"])

# T12 - ogni parametro ha una motivazione economica
check("T12 tutti i parametri motivati", all(p.get("why") for p in PARAM_REGISTER.values()),
      f"{len(PARAM_REGISTER)} parametri")

# T13 - calibrazione sulle BANDE della Costituzione, non su una societa'
# Archetipi definiti solo da livelli economici; nessun ticker reale coinvolto.
_ECC=dict(BASE, op_margin=0.38, fcf_margin=0.32, roic=0.34, cash_conversion=1.15,
    margin_stability=0.02, retention=1.05, unit_cost_decline=0.08, revenue_cagr3=0.19,
    opinc_cagr3=0.20, fcf_cagr3=0.20, reinvestment_rate=0.18, share_change=-0.03,
    buyback_accretion=2.2, sbc_to_revenue=0.01, fcf_per_share_cagr3=0.20,
    net_debt_to_ocf=0.0, interest_coverage=30.0, accrual_quality=1.3)
_MED=dict(BASE, op_margin=0.08, fcf_margin=0.05, roic=0.08, cash_conversion=0.7,
    margin_stability=0.25, retention=0.80, unit_cost_decline=0.0, revenue_cagr3=0.01,
    opinc_cagr3=0.01, fcf_cagr3=0.0, reinvestment_rate=0.03, share_change=0.02,
    buyback_accretion=0.3, sbc_to_revenue=0.09, fcf_per_share_cagr3=0.0,
    net_debt_to_ocf=3.5, interest_coverage=3.0, accrual_quality=0.8)
_KEYS=dict(op_margin="op_margin_general", fcf_margin="fcf_margin", roic="roic",
    cash_conversion="cash_conversion", margin_stability="margin_stability", retention="retention",
    unit_cost_decline="unit_cost_decline", revenue_cagr3="revenue_cagr3", opinc_cagr3="opinc_cagr3",
    fcf_cagr3="fcf_cagr3", reinvestment_rate="reinvestment_rate", share_change="share_change",
    buyback_accretion="buyback_accretion", sbc_to_revenue="sbc_to_revenue",
    fcf_per_share_cagr3="fcf_per_share_cagr3", net_debt_to_ocf="net_debt_to_ocf",
    interest_coverage="interest_coverage", accrual_quality="accrual_quality")
_ANC=dict(BASE, **{k: PARAM_REGISTER[p]["mid"] for k, p in _KEYS.items()})
s_ecc=bqs(_ECC)[0]; s_anc=bqs(_ANC)[0]; s_med=bqs(_MED)[0]
check("T13 archetipo eccezionale nella banda >=90", s_ecc>=90, f"BQS {s_ecc}")
check("T13b archetipo sulle ancore 'buona qualita' nella banda 70-79", 70<=s_anc<80, f"BQS {s_anc}")
check("T13c archetipo mediocre sotto 60", s_med<60, f"BQS {s_med}")

# T14 - integrita' delle ancore: mid sempre fra lo e hi, nella direzione della metrica
_bad=[k for k,p in PARAM_REGISTER.items() if p.get("mid") is not None and p["lo"]!=p["hi"]
      and not (min(p["lo"],p["hi"]) <= p["mid"] <= max(p["lo"],p["hi"]))]
check("T14 ogni ancora 'mid' e' compresa fra lo e hi", not _bad, str(_bad))
_nomid=[k for k,p in PARAM_REGISTER.items() if p.get("mid") is None]
check("T14b ogni parametro ha l'ancora di banda", not _nomid, str(_nomid))

# T15 - IOS instradato per modello economico (V4.1)
check("T15 instradamento delle varianti IOS",
      ios_variant("GENERAL")=="IOS_GENERAL" and ios_variant("BANK")=="IOS_BANK"
      and ios_variant("ASSETMGR_EXCH")=="IOS_BANK" and ios_variant("INSURANCE")=="IOS_INSURANCE"
      and ios_variant("REIT")=="IOS_REIT" and ios_variant("MARKETPLACE_NETWORK")=="IOS_GENERAL")

# una banca con OCF abbondante ma senza capitale/ROE non deve produrre un IOS via FCF
_bank_ios=dict(module="BANK", roe=0.14, margin_stability=0.03, retention=0.95,
    equity_to_assets=0.10, accrual_quality=1.1, net_margin=0.28, data_coverage_pct=100.0,
    market_cap=60e9, ocf=9e9, capex=0.4e9, sbc=0.3e9)
_sb,_cb,_,_=bqs(_bank_ios); _ib,_gb=ios(_bank_ios,_sb,_cb)
check("T15b banca senza book value/ROE-crescita: nessun IOS via OCF-capex-SBC",
      _ib is None and _gb.get("variant")=="IOS_BANK", f"BQS {_sb}, gate {_gb.get('gate')}")

_bank_ok=dict(_bank_ios, book_value=28e9, payout_ratio=0.45)
_ib2,_d2=ios(_bank_ok,_sb,_cb)
check("T15c banca valutata sul capitale proprio, non sull'OCF",
      _ib2 is not None and _d2["basis"].startswith("utile normalizzato"),
      f"IOS {_ib2}, base '{_d2.get('basis')}'")
check("T15d la SBC non e' sottratta due volte all'utile GAAP di una banca",
      abs(_d2["owner_earnings"] - 28e9*0.14) < 1.0, f"owner {_d2['owner_earnings']:.3e}")

_ins=dict(module="INSURANCE", roe=0.13, combined_ratio=0.94, margin_stability=0.04,
    retention=0.93, net_margin=0.10, accrual_quality=1.05, net_debt_to_ocf=0.5,
    interest_coverage=12.0, data_coverage_pct=100.0, market_cap=30e9,
    book_value=18e9, payout_ratio=0.40, ocf=4e9, capex=0.2e9, sbc=0.1e9)
_si,_ci,_,_=bqs(_ins); _ii,_di=ios(_ins,_si,_ci)
check("T15e assicuratore: IOS ancorato al capitale, combined ratio richiesto",
      _ii is not None and _di["variant"]=="IOS_INSURANCE", f"IOS {_ii}")
_ins_nocr=dict(_ins); _ins_nocr["combined_ratio"]=None
_i3,_g3=ios(_ins_nocr,_si,_ci)
check("T15f assicuratore senza combined ratio: nessun IOS, non un IOS approssimato",
      _i3 is None and "combined ratio" in _g3.get("gate",""), str(_g3.get("gate")))

_reit=dict(module="REIT", ffo_margin=0.55, occupancy=0.97, roic=0.09, margin_stability=0.03,
    net_debt_to_ocf=4.0, interest_coverage=6.0, accrual_quality=1.2, roe=0.11, retention=0.97,
    unit_cost_decline=0.02, revenue_cagr3=0.04, opinc_cagr3=0.05, fcf_cagr3=0.05,
    reinvestment_rate=0.12, share_change=-0.005, buyback_accretion=1.2, sbc_to_revenue=0.02,
    fcf_per_share_cagr3=0.05, data_coverage_pct=100.0,
    market_cap=12e9, ocf=1.1e9, capex=0.9e9, sbc=0.05e9)
_sr,_cr_,_,_=bqs(_reit); _ir,_gr=ios(_reit,_sr,_cr_)
check("T15g REIT senza AFFO: nessun IOS via FCF (capex sviluppo != manutenzione)",
      _ir is None and "AFFO" in _gr.get("gate",""), str(_gr.get("gate")))
_reit_ok=dict(_reit, affo=0.75e9); _ir2,_dr=ios(_reit_ok,_sr,_cr_)
check("T15h REIT valutato su AFFO", _ir2 is not None and _dr["basis"]=="AFFO", f"IOS {_ir2}")

# T16 - il modulo GENERAL non e' stato alterato dalla V4.1
_gen=dict(BASE, market_cap=100e9)
_sg,_cg,_,_=bqs(_gen); _ig,_dg=ios(_gen,_sg,_cg)
check("T16 percorso GENERAL invariato: owner earnings = OCF - capex - SBC",
      _dg["basis"]=="owner earnings = OCF - capex - SBC"
      and abs(_dg["owner_earnings"] - (BASE["ocf"]-BASE["capex"]-BASE["sbc"])) < 1.0, f"IOS {_ig}")

# ============================================================================
# T17 - BUGFIX: una componente completamente vuota deve essere PROVISIONAL
# Difetto individuato dal preflight post BR-01/BR-02 (par. 6 di quel report):
# con aw == 0 il codice usciva con `continue` SALTANDO il controllo PROVISIONAL,
# quindi una componente svuotata sfuggiva al proprio stesso controllo.
# Archetipi sintetici: nessun ticker reale.
# ============================================================================

# T17a - copertura 0% di una componente -> PROVISIONAL
_void = dict(BASE)
for _k in ("net_debt_to_ocf", "interest_coverage"):   # svuota interamente 'balance'
    _void[_k] = None
_sv, _cv, _dv, _ = bqs(_void)
check("T17a componente con copertura 0% -> PROVISIONAL",
      "balance" in _dv["_provisional_components"],
      f"provisional={_dv['_provisional_components']}")
check("T17a2 la confidence recepisce la componente vuota",
      bqs_confidence(_cv, 100.0, "PRESENT", _dv["_metric_coverage_pct"],
                     _dv["_provisional_components"]) == "PROVISIONAL")

# due componenti svuotate contemporaneamente
_void2 = dict(_void)
for _k in ("revenue_cagr3", "opinc_cagr3", "fcf_cagr3", "reinvestment_rate"):   # svuota 'runway'
    _void2[_k] = None
_s2, _c2, _d2, _ = bqs(_void2)
check("T17a3 piu' componenti vuote sono tutte segnalate",
      set(["balance", "runway"]).issubset(set(_d2["_provisional_components"])),
      f"provisional={_d2['_provisional_components']}")

# T17b - componente parzialmente coperta sotto il 60% -> PROVISIONAL (comportamento gia' atteso)
_part = dict(BASE)
for _k in ("op_margin", "fcf_margin"):      # economics: restano roic(5)+cash_conversion(3) = 8/25
    _part[_k] = None
_sp, _cp, _dp, _ = bqs(_part)
_ec = [(k, w) for k, _p, w in economics_spec("GENERAL")]
_avail = sum(w for k, w in _ec if _part.get(k) is not None)
_appl = sum(w for _, w in _ec)
check("T17b componente parzialmente coperta sotto il 60% -> PROVISIONAL",
      "economics" in _dp["_provisional_components"] and _avail/_appl < 0.60,
      f"economics {_avail}/{_appl} = {_avail/_appl*100:.0f}% del peso applicabile")

# T17c - componente sufficientemente coperta -> comportamento invariato
_ok = dict(BASE); _ok["cash_conversion"] = None      # economics: 22/25 = 88% >= 60%
_so, _co, _do, _ = bqs(_ok)
_avail_ok = sum(w for k, w in _ec if _ok.get(k) is not None)
check("T17c componente coperta a sufficienza -> nessun PROVISIONAL",
      "economics" not in _do["_provisional_components"] and _avail_ok/_appl >= 0.60,
      f"economics {_avail_ok}/{_appl} = {_avail_ok/_appl*100:.0f}%, provisional={_do['_provisional_components']}")

# la correzione non deve rendere PROVISIONAL una componente NON PERTINENTE
_na = dict(BASE)
for _k in ("net_debt_to_ocf", "interest_coverage"):
    _na[_k] = NA                                     # non applicabile, non mancante
_sn, _cn, _dn, _ = bqs(_na)
check("T17c2 componente con metriche NOT_APPLICABLE non e' PROVISIONAL",
      "balance" not in _dn["_provisional_components"],
      f"provisional={_dn['_provisional_components']}")

# T17d - nessuna variazione dei punteggi degli archetipi completamente coperti
# Valori d'oro registrati PRIMA della correzione, sul motore V4.1 immediatamente precedente.
_GOLDEN = {"BASE": 78.0, "ECC": 99.6, "ANC": 76.2, "MED": 15.6}
_ARCH = {"BASE": BASE, "ECC": _ECC, "ANC": _ANC, "MED": _MED}
_drift = {k: (_GOLDEN[k], bqs(v)[0]) for k, v in _ARCH.items() if bqs(v)[0] != _GOLDEN[k]}
check("T17d punteggi invariati sugli archetipi completamente coperti",
      not _drift, f"golden {_GOLDEN} — scostamenti: {_drift or 'nessuno'}")
check("T17d2 gli archetipi completamente coperti non hanno componenti PROVISIONAL",
      all(bqs(v)[2]["_provisional_components"] == [] and bqs(v)[2]["_metric_coverage_pct"] == 100.0
          for v in _ARCH.values()))
check("T17d3 la correzione non tocca il punteggio, solo la confidence",
      _sv == bqs(_void)[0] and isinstance(_sv, float),
      "il punteggio con componente vuota resta calcolato sulle componenti disponibili")

print("\n" + ("TUTTI I TEST PASSATI" if not FAIL else f"FALLITI: {FAIL}"))
sys.exit(1 if FAIL else 0)
