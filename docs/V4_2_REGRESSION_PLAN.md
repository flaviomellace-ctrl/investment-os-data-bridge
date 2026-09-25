# INVESTMENT OS V4.2 — REGRESSION & VALIDATION PLAN

- Documento: `V4_2_REGRESSION_PLAN`
- Versione: **1.0**
- Data: **2026-09-24**
- Dipendenza: `V4_2_CHANGE_CONTROL_SPEC.md`
- Stato: **PRE-CODE / PRE-RANKING**
- Sistema: **NOT LIVE**

---

## 1. Obiettivo

Dimostrare che V4.2 corregge difetti generali di routing/discovery/auditabilità senza:
- overfitting a UBER;
- riduzione della prudenza di valuation;
- aumento ingiustificato dei false positive;
- regressioni su missing data, sector fairness, variants IOS o Decision Gate.

---

## 2. Fasi e ordine obbligatorio

### R0 — Baseline seal
Verificare:
- V4.1 engine MD5 `68f626974592915d6c2a8e6583d6c77b`;
- V4.1 canonical SHA-256 `d2207e92bbe6cc0ef883db6a54d93ac965b08da487741b4de8e2459ed6282f45`;
- V4.1 freeze run `36045268572`;
- V4.1 blind hash `dcc2b650cc8f2d48e8cbee50bfea7dc464f4cc37b37141d1e4ee1727ef2bed88`.

Mismatch => STOP.

### R1 — Existing V4.1 suite
Eseguire `test_v4.py` invariato contro il baseline.
Tutti i test devono passare.

### R2 — New synthetic marketplace routing tests
Fixture senza ticker reali:
1. true two-sided marketplace => MARKETPLACE_NETWORK;
2. SaaS vendor con "platform" marketing language => NON marketplace;
3. retailer marketplace-like ma principal inventory economics => NON marketplace;
4. agency/network with underlying volume and take-rate economics => marketplace;
5. missing documentary evidence => original SIC module + PROVISIONAL candidate flag, non marketplace definitivo.

### R3 — Marketplace presentation invariance
Preservare T4/T4b:
- stessa economia gross-vs-net => delta BQS economics ~0 nel modulo marketplace;
- non deve dipendere dal margine su revenue presentation.

### R4 — Inflection archetypes
Almeno:
A. genuine inflection;
B. mature steady compounder;
C. one-off tax/valuation release;
D. working-capital/float-driven OCF jump;
E. cyclical rebound;
F. dilution-funded growth;
G. revenue growth without cash conversion;
H. cash growth with declining revenue.

Pass criteria:
- A deve essere surfaced nella Lane I;
- B non deve essere penalizzato in Lane V;
- C/D/E/F non devono essere surfaced come high-confidence inflection senza flag;
- nessun caso MISSING può diventare 0.

### R5 — Growth-treatment bake-off
Confrontare almeno 3 formule candidate esclusivamente sui synthetic archetypes.

Nessun ticker reale.
Se nessuna formula domina in robustezza, mantenere la formula IOS V4.1 e usare Lane I separata.

### R6 — Quality-of-cash tests
Verificare:
- reserve/float contribution;
- tax timing;
- equity revaluation;
- one-off working capital;
- absent data => MISSING;
- normalized OE mai prodotto senza provenance sufficiente.

### R7 — Off-balance tests
Verificare:
- quantified commitment;
- unquantified material commitment;
- immaterial commitment;
- leases already captured in debt => no double count.

### R8 — Sector variant regression
Preservare:
- BANK => IOS_BANK;
- ASSETMGR_EXCH => IOS_BANK;
- INSURANCE => IOS_INSURANCE;
- REIT => IOS_REIT;
- MARKETPLACE_NETWORK => IOS_GENERAL unless separately changed by an approved future change request.

### R9 — Data/transport regression
- 504-row continuity for the frozen fixture;
- schema integrity;
- T20 byte reassembly when applicable;
- duplicate ticker = 0;
- market cap direct source only;
- stale market policy explicit.

### R10 — Historical V4.1 comparison
Dopo il freeze del codice V4.2, ma prima del nuovo blind:
- run V4.2 sul frozen V4.1 dataset;
- confrontare distribuzioni aggregate, non ottimizzare sui nomi;
- produrre delta by module, confidence, coverage, gate population;
- registrare rank instability e cause;
- nessuna modifica a V4.2 dopo aver visto ticker reali, salvo bug tecnico documentato.

Bug tecnico != risultato sgradito.

### R11 — Hidden-control regression
Usare controlli sealed/non-current separati dal target noto.
Scoring pre-registrato.
Nessun target name nel codice o nei prompt di sviluppo.

### R12 — New blind/forward validation
Esecutore clean-room:
- non vede UBER validation;
- non vede questa conversazione;
- riceve solo V4.2 frozen artifacts e safe methodology;
- produce freeze prima di aprire il nuovo validation set.

---

## 3. Severity

### CRITICAL — qualsiasi fallimento blocca V4.2
- MISSING -> 0;
- market cap reconstructed;
- target/ticker hard-coded;
- post-result tuning;
- data conflict silenziato;
- BUY/ADD con unresolved material red flag;
- V4.1 artifact modificato;
- sector variant errato;
- regression negative control promosso come actionable.

### MAJOR
- marketplace routing false positive;
- inflection lane eccessivamente ampia;
- quality-of-cash provenance incompleta;
- unexplained rank instability;
- freeze package incompleto.

### MINOR
- naming;
- report formatting;
- non-material metadata omissions.

---

## 4. Acceptance criteria V4.2

Per andare al nuovo blind/forward validation:
- 100% CRITICAL PASS;
- existing V4.1 regression PASS;
- synthetic marketplace suite PASS;
- inflection negative controls PASS;
- no hard-coded real ticker;
- freeze audit artifacts complete;
- all formulas/thresholds/version hashes frozen;
- comparison report signed/frozen;
- system NOT LIVE.

Per andare a Bootstrap/IPS dopo il nuovo validation:
- validation >= pre-registered PASS threshold;
- nessun negative-control BUY/ADD;
- nessuna critical data failure;
- Decision Gate operational;
- broker auto-execution OFF.

---

## 5. Outputs

Produrre:
- `V4_2_ENGINE_MANIFEST.json`
- `V4_2_REGRESSION_RECEIPT.json`
- `V4_2_SYNTHETIC_TEST_REPORT.md`
- `V4_2_V41_COMPARISON.md`
- `V4_2_FREEZE_RECEIPT.json`
- `V4_2_BLIND_HANDOFF.md`

**END — V4.2 REGRESSION & VALIDATION PLAN 1.0**
