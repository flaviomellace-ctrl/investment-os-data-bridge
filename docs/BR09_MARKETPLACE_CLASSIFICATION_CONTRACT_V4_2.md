# BR-09 MARKETPLACE / NETWORK — CLASSIFICATION & ENRICHMENT CONTRACT V4.2

- Documento: `BR09_MARKETPLACE_CLASSIFICATION_CONTRACT_V4_2`
- Data: **2026-09-25**
- Stato: **PRE-CODE FROZEN CONTRACT**
- Sistema: **NOT LIVE**
- Dipendenza: `V4_2_CHANGE_CONTROL_SPEC.md`
- Natura: routing + enrichment documentale. Non modifica da solo BQS/IOS.

## 1. Problema

Il motore V4.1 contiene già `MARKETPLACE_NETWORK`, ma il real-data routing basato su SIC non può identificare in modo affidabile i marketplace digitali. Il risultato osservato nella V4.1 è stato `MARKETPLACE_NETWORK = 0` nell'universo reale, pur avendo un modulo dedicato nel motore.

Le metriche specifiche del modulo — underlying volume, take rate, retention, frequency, unit-cost decline — sono prevalentemente narrative/non-XBRL e richiedono fonti primarie documentali.

## 2. Regola fondamentale

**Il triage non assegna il modulo.**

Il triage produce soltanto `CANDIDATE_MARKETPLACE = true/false`.  
La classificazione finale `MARKETPLACE_NETWORK` richiede evidenza primaria documentale.

Nessuna whitelist ticker. Nessun override manuale non tracciato.

## 3. Fase 0 — Triage strutturato

Segnalare `CANDIDATE_MARKETPLACE=true` se sono soddisfatte almeno 2 delle seguenti condizioni:

1. evidenza di agency/net-revenue presentation o intermediazione;
2. struttura economica compatibile con modello capital-light di intermediazione;
3. nel filing primario ricorre lessico di intermediazione fra due popolazioni economiche distinte.

Il triage:
- NON assegna BQS;
- NON assegna IOS;
- NON promuove in shortlist;
- serve solo a determinare quali imprese richiedono classificazione documentale.

## 4. Fase 1 — Classificazione documentale

Fonte primaria obbligatoria: ultimo 10-K/20-F/annual report, Item 1/Business o sezione equivalente.

Domande binarie:

- `two_sided_intermediation`: l'impresa intermedia transazioni/interazioni economiche fra almeno due popolazioni distinte?
- `revenue_linked_to_underlying_volume`: la monetizzazione è collegata a un volume sottostante intermediato?
- `company_reports_underlying_volume`: l'impresa espone tale volume o un KPI equivalente?

Regola:

`MARKETPLACE_NETWORK` solo se le prime due risposte sono `YES`.

La terza risposta non decide da sola il modulo, ma determina se l'enrichment dei KPI di volume è possibile.

Se l'evidenza è insufficiente:
- mantenere il modulo SIC precedente;
- `marketplace_classification_status = PROVISIONAL`;
- non inventare dati.

## 5. Provenance obbligatoria della classificazione

Per ogni candidato registrare:

- ticker/entity key;
- original_module;
- candidate_marketplace;
- final_module;
- classification_status;
- source_type;
- source_url/accession;
- filing_date;
- classification_as_of;
- evidence_excerpt_or_hash;
- classifier_version;
- reason_code;
- reviewer/method.

## 6. Fase 2 — Recupero KPI

Gerarchia:

1. 10-K / 10-Q / annual report, MD&A / Key Metrics;
2. supplemental financial information / investor deck IR;
3. earnings call transcript solo per definizioni/chiarimenti, non come unico valore materiale.

Per ciascun KPI:

- value;
- unit;
- currency;
- period;
- data_as_of;
- source;
- source_type;
- definition_text;
- status = PRESENT | MISSING | CONFLICTING | NOT_APPLICABLE.

## 7. Fase 3 — Normalizzazione

### Underlying volume
Usare il valore lordo intermediato secondo la definizione dell'impresa. Non ricostruire da revenue se l'impresa non pubblica il volume.

### Take rate
`take_rate = net_revenue / underlying_volume`

Solo se numeratore e denominatore hanno lo stesso:
- periodo;
- perimetro geografico;
- segmento;
- definizione.

Altrimenti `CONFLICTING`.

### EBITDA / volume
`ebitda_on_volume = adjusted_or_operating_ebitda / underlying_volume`

La definizione dell'EBITDA deve essere esplicita e coerente.

### FCF / volume
`fcf_on_volume = FCF / underlying_volume`

FCF deve rispettare la policy owner-cash del sistema; nessuna ricostruzione se componenti materiali sono MISSING.

### Retention
Solo cohort-based o equivalente esplicitamente definito dall'impresa. Un dato aggregate/gross non può essere usato come proxy.

### Frequency
Usare solo metrica comparabile nel tempo e con denominatore coerente.

### Unit-cost decline
Solo se il costo unitario è definito e comparabile. Altrimenti MISSING.

## 8. Regole di stato

- `MISSING != 0`
- definizione cambiata tra periodi => `CONFLICTING` finché non riconciliata;
- proxy non documentato => vietato;
- KPI non pubblicato => `MISSING`;
- classificazione incerta => mantenere modulo precedente + PROVISIONAL;
- nessun singolo KPI può da solo assegnare il modulo.

## 9. Interazione con il motore V4.1/V4.2

Il motore già supporta:
- `ebitda_on_volume`
- `fcf_on_volume`
- `take_rate`
- `cash_conversion`
- `two_sided_growth`
- `retention`
- `unit_cost_decline`
- `frequency_growth`

BR-09 deve produrre/routare questi input; non deve cambiare le loro ancore senza separato change request.

`MARKETPLACE_NETWORK` continua a usare `IOS_GENERAL` finché una futura specifica approvata non autorizza una variante IOS diversa.

## 10. Test sintetici obbligatori prima di dati reali

R2-A True marketplace:
- due-sided = YES;
- revenue linked to underlying volume = YES;
- expected module = MARKETPLACE_NETWORK.

R2-B SaaS "platform":
- usa il termine platform ma vende software direttamente;
- expected = original SOFTWARE.

R2-C Retail principal:
- marketplace-like UX ma inventory principal economics;
- expected = original RETAIL/GENERAL/SIC module.

R2-D Agency network:
- intermediazione + volume sottostante + take economics;
- expected = MARKETPLACE_NETWORK.

R2-E Insufficient evidence:
- triage positive, documentary evidence incomplete;
- expected = original module + PROVISIONAL classification.

R2-F Definition drift:
- volume definition changes across periods;
- expected KPI series = CONFLICTING until reconciled.

## 11. Anti-overfitting

- nessun ticker reale nei test;
- nessun ticker hard-coded nel classifier;
- nessuna regola aggiunta perché favorisce un validation target noto;
- test prima sui synthetic archetypes;
- dopo il primo real-data run: no tuning in-place salvo bug tecnico documentato.

## 12. Acceptance criteria

BR-09 è implementabile solo se:
- tutti R2-A...R2-F passano;
- provenance completa;
- no ticker hard-coded;
- missing handling invariato;
- original module preservato in caso di evidenza insufficiente;
- nessun ranking reale è stato usato per scegliere le regole.

**END — BR-09 V4.2 CONTRACT**
