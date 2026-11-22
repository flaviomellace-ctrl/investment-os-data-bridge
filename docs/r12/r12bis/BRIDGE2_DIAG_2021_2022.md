# BRIDGE-2: diagnosi sulle date già usate (informativo, non decisivo)

Copertura IOS con pipeline 1.1 invariata, prima e dopo BRIDGE-2:
- 15/11/2021: 101/505 = 20,0% → 189/505 = 37,4%
- 15/11/2022: 125/503 = 24,9% → 210/503 = 41,8%
Causa principale risolta: "share_change MISSING" da 46 a 1–2 (i dataset SEC FSDS contengono solo i prospetti
principali; il numero medio di azioni diluite di molte società sta nelle note). Dati aggiunti solo dalla stessa
filing selezionata (stesso accession number), via SEC companyfacts, date arrotondate a fine mese come FSDS.
Due correzioni durante la diagnosi: arrotondamento delle date (senza, BR03-T02 falliva per periodi doppi).
Le code e i rendimenti di queste date sono già noti: questi numeri non entrano nel verdetto R12-ter.
Hash della versione usata per il test decisivo: docs/r12/R12TER_BRIDGE2_SHA256SUMS.
