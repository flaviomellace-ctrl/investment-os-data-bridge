# INVESTMENT OS V4.2 — CHANGE CONTROL SPEC

- Documento: `V4_2_CHANGE_CONTROL_SPEC`
- Versione: **1.0**
- Data: **2026-09-24**
- Stato: **PRE-IMPLEMENTATION FROZEN SPEC**
- Sistema: **NOT LIVE**
- Scopo: correggere esclusivamente carenze strutturali dimostrate dalla validazione V4.1, senza ottimizzare retroattivamente il ranking su UBER o su qualunque altro ticker noto.
- V4.1: **immutabile**. Nessun file, hash, ranking, BQS, IOS, coda o risultato V4.1 può essere riscritto.
- Frozen V4.1 engine MD5: `68f626974592915d6c2a8e6583d6c77b`
- Frozen canonical fundamentals SHA-256: `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`
- V4.1 quantitative freeze run: `36045268572`
- V4.1 blind-result SHA-256: `dcc2b650cc8f2d48e8cbee50bfea7dc464f4cc37b37141d1e4ee1727ef2bed88`
- V4.1 UBER validation v2: **FAIL**
- Broker execution: **OFF**

---

## 0. Principio di change control

V4.2 NON nasce per "far passare UBER".

Ogni modifica deve soddisfare tutte le condizioni seguenti:

1. correggere un difetto generale dimostrato da evidenza V4.1;
2. avere una giustificazione economica indipendente da un ticker;
3. essere specificata prima di eseguire ranking V4.2 su società reali;
4. essere testata prima su archetipi sintetici e controlli non correnti;
5. non peggiorare missing-data handling, prudenza di valutazione, Red Team, integrità o riproducibilità;
6. non cambiare retroattivamente V4.1;
7. se non è possibile dimostrare un miglioramento generale senza target leakage, la modifica resta fuori da V4.2.

Un errore che gonfia il valore resta peggiore di uno che lo deprime.

---

## 1. Baseline V4.1 realmente osservata

### 1.1 Ciò che ha funzionato

- canonical/T20 integri;
- `MISSING != 0`;
- market cap diretto da fonte, mai ricostruito da prezzo × shares del bridge;
- BQS price-independent;
- IOS calcolato per tutte le società con BQS >=60 e data coverage >=70, non solo Top-30 BQS;
- Decision Gate A/B/C indipendente;
- unresolved material red flag => no BUY/ADD;
- leverage indeterminate => PROVISIONAL / reconciliation manuale;
- blind freeze e validation separati;
- nessun ranking modificato dopo la validation.

### 1.2 Difetti dimostrati dalla V4.1

**D1 — Marketplace routing non attivato su dati reali.**

Il motore V4.1 contiene già il modulo `MARKETPLACE_NETWORK`, con metriche specifiche e regression test. Il problema reale è a monte: il bridge/preflight assegna il modulo principalmente da SIC; la funzione `module_of(sic)` non può identificare i marketplace. Nella copertura reale il modulo `MARKETPLACE_NETWORK` era 0/504. UBER è quindi arrivata al motore come `SOFTWARE`.

Conclusione: NON va inventato un nuovo modulo; va resa operativa la classificazione/enrichment BR-09 già prevista.

**D2 — Discovery insufficiente per inflection economics.**

V4.1 usa, per IOS_GENERAL:
- owner earnings = OCF - capex - SBC;
- crescita `g` da `revenue_cagr3`, limitata a 15%;
- DCF base con crescita massima 12%;
- expected return con contributo crescita massimo 10%;
- score comune: 30 expected return + 25 margin of safety + 20 scenario asymmetry + 15 BQS + 10 hurdle spread.

La validation ha dimostrato che una società con dati completi e forte traiettoria di cassa può restare fuori dalla fase qualitativa quando il livello corrente di owner yield/MoS/downside non è sufficientemente forte. Questo è un problema di **discovery breadth**, non prova che i pesi di valuation siano sbagliati.

**D3 — Freeze audit package incompleto per la validation.**

Il ranking completo esisteva nel repository ma non era incluso nel clean-room handoff/final blind record; la riga UBER ha dovuto essere recuperata separatamente. La post-validation deve poter ricostruire immediatamente qualunque riga congelata.

**D4 — FCF quality e obbligazioni economiche non sono abbastanza esplicite nel layer qualitativo.**

La validation ha mostrato classi generali di aggiustamenti che possono rendere OCF-capex-SBC economicamente troppo ottimistico o incompleto:
- variazioni di riserve/float;
- DTA/NOL e cash-tax transitori;
- rivalutazioni di partecipazioni / valuation allowance;
- purchase commitments/off-take e altre obbligazioni fuori bilancio;
- stress leverage dopo SBC.

Questi non autorizzano automaticamente una nuova formula IOS. Autorizzano prima un **quality-of-cash diagnostic layer** e controlli di Gate.

---

## 2. Correzioni V4.2 autorizzate

### CH-42-01 — Attivazione reale MARKETPLACE_NETWORK [MANDATORY]

**Tipo:** routing + data enrichment.  
**Motore BQS marketplace esistente:** da preservare salvo bug indipendente.

Implementare BR-09 prima del BQS:

**Fase A — candidate triage**
- identifica `CANDIDATE_MARKETPLACE` con segnali documentali/economici generali;
- il triage NON assegna il modulo.

**Fase B — documentary classification**
Assegna `MARKETPLACE_NETWORK` solo se da fonte primaria risultano almeno:
1. intermediazione tra due popolazioni economiche distinte;
2. ricavi/take economico collegati a un volume sottostante intermediato.

Registrare:
- source URL/accession;
- filing date;
- classification_as_of;
- evidence excerpt/hash;
- classifier version;
- outcome + reason.

**Fase C — KPI enrichment**
Quando pubblicati:
- underlying volume (GB/GMV/TPV o equivalente);
- EBITDA/on-volume;
- FCF/on-volume;
- take rate;
- two-sided growth;
- frequency growth;
- retention/cohort metric;
- unit-cost decline / scale-efficiency proxy.

Regole:
- MISSING resta MISSING;
- nessuna ricostruzione inventata da revenue quando il volume non è pubblicato;
- nessun marketplace viene retro-classificato usando ticker whitelist nel codice.

### CH-42-02 — Freeze Audit Package [MANDATORY]

Ogni freeze V4.2 deve contenere e hashare:
- universe full ranking;
- Top-30 BQS;
- Top-20 IOS;
- tutte le discovery lanes;
- deep-dive queue;
- market snapshot;
- per-ticker row lookup;
- engine source hash;
- adapter/classifier source hash;
- data canonical hash;
- regression receipt;
- exact IOS formula/version identifier;
- exact selection and tie-break rules.

Il final blind record deve poter puntare a questi artefatti senza dover ricostruire dati dopo l'apertura della validation.

### CH-42-03 — Inflection Discovery Lane [AUTHORIZED FOR IMPLEMENTATION, NOT FOR TUNING]

Aggiungere una seconda corsia di **discovery**, separata dall'IOS.

Principi obbligatori:
- non modifica BQS;
- non modifica IOS;
- non sostituisce la valuation lane;
- non attribuisce BUY/ADD;
- serve soltanto a garantire che forte miglioramento economico osservabile possa ottenere revisione qualitativa anche quando la valuation corrente non entra nella Top-IOS;
- i criteri numerici devono essere congelati PRIMA di eseguire V4.2 su ticker reali;
- calibrazione solo su archetipi sintetici e controlli non correnti, mai su UBER o altri target noti;
- deve richiedere owner earnings positivi o una metrica di cassa equivalente valida;
- deve usare almeno una misura per-share per evitare crescita comprata con diluizione;
- deve avere una penalità/flag per one-off e base-effect, non ignorarli.

**Non autorizzato in questa specifica:** un threshold scelto perché porterebbe un target noto nella coda.

La scelta finale fra:
- percentile lane;
- multi-metric inflection score;
- Pareto lane;
deve essere effettuata nel regression-design step senza vedere il ranking reale V4.2.

### CH-42-04 — Quality-of-Cash Diagnostics [MANDATORY DIAGNOSTIC, NON SCORE CHANGE]

Aggiungere campi diagnostici:
- reported OCF;
- reported capex;
- reported SBC;
- reported owner earnings;
- reserve/float contribution to OCF quando materialmente separabile;
- cash taxes vs normalized tax burden quando materialmente separabile;
- one-off tax/valuation allowance;
- equity revaluation non-cash;
- working-capital anomaly flag;
- normalized_owner_earnings: solo se la normalizzazione è documentabile e con provenance;
- otherwise MISSING.

Per V4.2 iniziale:
- questi campi NON cambiano automaticamente IOS;
- se la differenza tra reported e normalized owner earnings è materialmente elevata, IOS confidence deve diventare almeno PROVISIONAL e il deep dive deve riconciliare la cassa;
- qualsiasi futura modifica dell'IOS basata su normalized OE richiede un change request separato + regression.

### CH-42-05 — Off-Balance / Commitments Gate [MANDATORY]

Per ogni candidato che avanza:
- purchase obligations;
- take-or-pay/off-take;
- long-term content/capacity commitments;
- guarantees;
- material leases non già nel debt metric;
- pension/other material fixed claims quando pertinenti.

MISSING != zero.

Impegni materialmente non quantificati => confidence ridotta e, se possono cambiare la solvibilità/valuation in modo decisivo, Decision Gate = INVESTIGARE.

### CH-42-06 — Leverage Stress View [MANDATORY SECONDARY VIEW]

Mantenere la metrica di leva primaria del modello per continuità.

Aggiungere una vista secondaria:
- gross debt / EBITDA;
- net debt / EBITDA;
- debt / (EBITDA - SBC) quando SBC è materialmente ricorrente;
- module-specific treatment per banche/assicurazioni/captive finance.

La vista SBC-stress NON sostituisce retroattivamente la soglia V4.1; serve a confidence e Red Team.

---

## 3. Modifiche NON autorizzate in V4.2 senza nuovo change request

1. cambiare i pesi BQS per far salire un target noto;
2. cambiare i pesi IOS 30/25/20/15/10 basandosi sul caso UBER;
3. abbassare la soglia IOS o alzare il numero di candidati solo perché UBER era #38;
4. inserire whitelist/blacklist ticker nel classifier;
5. rendere positivo un bear case perché una società cresce rapidamente;
6. sostituire market cap diretto con price × bridge shares;
7. convertire MISSING in 0;
8. rimuovere il Gate BQS>=60 e coverage>=70;
9. rimuovere la penalità di diluizione;
10. far attribuire punti all'optionality;
11. rendere BUY un esito automatico di BQS/IOS elevati;
12. modificare V4.1, la validation v1/v2 o i relativi hash.

---

## 4. Regole per il growth treatment V4.2

Il cap del 10% nell'expected return e il 12% nel DCF sono ora **oggetto di verifica**, non automaticamente aboliti.

Prima di qualunque modifica:
1. definire 6+ archetipi sintetici:
   - mature compounder;
   - genuine inflection;
   - one-off fake inflection;
   - dilution-funded growth;
   - cyclical rebound;
   - cash-flow deterioration;
2. testare almeno tre growth treatments senza ticker reali;
3. scegliere il trattamento che:
   - riconosce genuine inflection;
   - non promuove one-off/cyclical rebound;
   - penalizza dilution;
   - mantiene downside discipline;
   - produce comportamento monotono e spiegabile;
4. congelare formula e parametri;
5. solo dopo eseguire real-data regression.

Il parametro scelto deve avere una voce nel PARAM_REGISTER con:
- value;
- unit;
- economic rationale;
- synthetic test;
- failure mode;
- owner;
- change history.

---

## 5. Selection architecture V4.2

La discovery deve avere almeno due output distinti:

**Lane V — Valuation Opportunity**
- ranking IOS ufficiale;
- formula V4.2 congelata;
- nessun override manuale.

**Lane I — Economic Inflection**
- price-independent o quasi price-independent;
- nessun BUY;
- individua aziende che richiedono un dossier per traiettoria economica, non perché economiche.

Il merge verso il deep-dive set deve essere:
- deterministico;
- pre-registrato;
- max candidati definito prima del run;
- tie-break dichiarati;
- nessuna sostituzione discrezionale dopo aver visto nomi.

Se il cap complessivo resta 10, la regola di merge deve essere congelata nel regression plan PRIMA del primo ranking reale V4.2.

---

## 6. Regression invariants

V4.2 deve preservare:

- `MISSING != 0`;
- BQS indipendente dal prezzo;
- IOS price-aware;
- market cap diretto;
- data conflicts non silenziati;
- BQS confidence e metric coverage;
- leverage indeterminate => PROVISIONAL;
- optionality = 0 punti;
- bank/insurance/REIT IOS variants;
- Decision Gate A/B/C;
- no BUY/ADD con red flag materiale irrisolta;
- system NOT LIVE finché checklist non completata.

Ogni regressione critica = BLOCK.

---

## 7. Anti-overfitting protocol

### 7.1 Target isolation

UBER e qualunque validation target già noto:
- NON può essere usato per scegliere pesi, cap, soglie, lane quota o tie-break;
- può essere usato solo come **post-hoc historical check** dopo il freeze V4.2;
- non può essere il solo caso che giustifica una modifica.

### 7.2 Synthetic-first

Tutte le nuove regole numeriche devono superare prima archetipi sintetici.

### 7.3 Hidden/non-current controls

Il regression plan deve includere controlli non correnti o sealed controls non usati per tuning. Il codice non deve contenerne nomi/ticker.

### 7.4 Negative controls

Almeno due controlli devono verificare che V4.2 NON promuova:
- crescita apparente da one-off;
- FCF gonfiato da working capital/float/tax timing;
- alta crescita con forte diluizione e downside povero.

### 7.5 No post-result tuning

Dopo il primo ranking reale V4.2:
- pesi/soglie/regole restano congelati;
- se il test fallisce, si apre una V4.3 change request; non si corregge V4.2 in-place.

---

## 8. Evidence package richiesto prima del coding

Prima di modificare il motore:
- copia immutabile di `v4_scoring.py` V4.1;
- copia immutabile di `test_v4.py`;
- V4.1 ranking full + freeze receipt;
- validation v2;
- BR-09 marketplace contract/procedure;
- PARAM_REGISTER corrente;
- questa specifica;
- regression plan V4.2.

---

## 9. Definition of Done — V4.2 code complete

V4.2 è "code complete" solo se:

1. nuova versione engine ha hash/versione propri;
2. V4.1 hash resta intatto;
3. marketplace routing funziona su fixture sintetiche/documentali;
4. nessun ticker hard-coded;
5. freeze audit package completo;
6. inflection lane implementata con regola congelata;
7. quality-of-cash diagnostics presenti;
8. off-balance/commitments gate presente;
9. regression suite tutta verde;
10. comparison report V4.1 vs V4.2 prodotto senza modificare V4.1;
11. nessun BUY/ADD emesso;
12. sistema ancora NOT LIVE.

---

## 10. Definition of Done — Ready for new blind/forward validation

Prima del nuovo test:

- V4.2 engine/version/hash congelati;
- adapter/classifier/hash congelati;
- canonical data snapshot/hash congelati;
- regression PASS;
- hidden control material non aperto nel contesto esecutore;
- selection lanes e merge rule congelati;
- market snapshot policy congelata;
- clean-room instructions generate;
- validation target non noto al clean-room executor.

Solo allora è autorizzato un nuovo blind/forward validation run.

---

## 11. Stop rule

Dopo una V4.2 che:
- supera le regression critiche;
- non genera false positive sui negative controls;
- supera il nuovo blind/forward validation secondo criteri pre-registrati;

si procede a Bootstrap + IPS + ledgers + routine dry-run.

Miglioramenti ulteriori non critici vanno nel backlog post-LIVE e NON riaprono automaticamente il motore.

**END — V4.2 CHANGE CONTROL SPEC 1.0 — FROZEN BEFORE IMPLEMENTATION**
