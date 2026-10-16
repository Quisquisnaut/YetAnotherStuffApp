# YetAnotherStuffApp — Rapporto Step 02

**Data:** 16 ottobre 2026. **Versione precedente / nuova:** 0.3.7 / **0.3.8**.

**Branch:** `feature/step-02-box-sorting`, senza worktree. **Base:** `2b7f1bd5a9cf2246d1586a207d0f8a130da7152c`. **Commit applicativo:** `8d93d060425a32e3d06db1f9757e1b0921321e81`. **Stato: APPROVATO e integrato in main** — Go ricevuto; commit sul branch, merge fast-forward nel `main` locale e successivo push completati. CI verde su Windows, Linux e macOS. Nessuna PR, tag o release. La checklist visiva conserva le voci non confermate singolarmente.

## Ambito approvato

Step 2 del piano: ordinamento condiviso delle box. Approvata con «a» l'opzione **A**, che conserva criterio e direzione nelle impostazioni locali del dispositivo, separatamente dai dati dell'inventario. Coerenza fra Pythonista, GUI Windows e console; protezione dei dati esistenti e compatibilita delle interfacce interne.

| Criterio | Direzione normale | Direzione inversa |
| --- | --- | --- |
| Numero di articoli | Maggiore prima, predefinita | Minore prima |
| Nome | A–Z | Z–A |
| Creazione box | Piu recente prima | Meno recente prima |
| Ultima modifica | Piu recente prima | Meno recente prima |

Non sono iniziati tag/nuovi filtri dello Step 3, ordinamento degli articoli dello Step 4 o altri step successivi.

## Attivita completate

- **Modulo condiviso `stuffapp/box_order.py`:** otto ordinamenti, inversione corrente, descrizioni/azioni comuni, aggregazione di conteggi e attivita con un passaggio sugli articoli. A parita di valore usa nome senza distinzione di maiuscole/minuscole e ID; l'inversione di date/conteggi conserva tali spareggi. Per nomi uguali rimane stabile l'ID. Le date sconosciute restano in fondo in entrambi i versi.
- **Preferenze del dispositivo:** `box_order` in `stuffapp_settings.json`, con criterio e booleano di inversione. Letture mancanti/non valide usano il default senza scrivere. Le modifiche preservano percorso dati, bookmark Pythonista e chiavi estranee; un file impostazioni illeggibile non viene sovrascritto. Cancel non modifica il file; un errore di salvataggio mantiene la preferenza precedente e viene segnalato.
- **Date persistenti:** riuso di `box.modified`, senza nuovo formato dell'inventario. Il punto comune `Store._write_item()` registra le box interessate per creazione/import, modifica, clone, cambio tipo, modifiche di valori dovute ai campi dei tipi, promemoria, fotografie, ripristino e riassegnazione durante il controllo dati. Uno spostamento registra entrambe le box; uno spostamento verso la stessa box non scrive. Eliminazione degli articoli, operazioni fotografiche e ripristino dal cestino proteggono la data prima delle operazioni sui file. La creazione della box rimane invariata e un orologio arretrato non cancella una data successiva gia registrata.
- **Eventi dopo uscita/eliminazione:** il timestamp resta nella box anche se diventa vuota, il cestino viene svuotato o il processo viene riaperto. I normali backup includono il campo e il ripristino conserva il valore archiviato.
- **Dati legacy:** l'ordinamento considera le date valide disponibili nella box e negli articoli presenti, senza migrare o riscrivere i record solo per visualizzarli. Non ricostruisce eventi storici mai registrati. `Store.list_boxes()` conserva firma e ordine alfabetico per esportazioni e altri consumatori; le UI e i loro selettori applicano il servizio condiviso.
- **Interfacce:** Windows mostra **Sort...** sopra la lista, il riepilogo dell'ordine e i conteggi; e disponibile anche **Box > Sort boxes...**. Pythonista ha **Home > Sort boxes**, con riepilogo della scelta; console ha **Boxes > Sort boxes...**. Il selettore comune offre le otto direzioni e **Reverse current order**. Windows conserva la box selezionata tramite ID e aggiorna ordine/conteggi dopo modifiche pertinenti. **All boxes** rimane prima nella navigazione Windows. I selettori delle box, inclusi quelli dei filtri esistenti, seguono la preferenza senza riprogettare i filtri.
- **Tastiera e Pythonista:** il selettore desktop riceve focus dopo l'apertura, Invio conferma, Esc annulla. In Pythonista la scelta/scrittura dell'ordine usa il lock esistente delle operazioni sulla cartella, per evitare sovrapposizioni con salvataggi di percorso/bookmark.
- **Guida e distribuzione:** Help > Boxes, README e tre setup aggiornati. Versione centrale **0.3.8** e manifest di build **Step 02**. Nessuna nuova dipendenza obbligatoria.

## Test automatici ed evidenze

Ambiente: **Windows 10, Python 3.14.7**. Suite completa sul codice funzionale finale, prima delle build:

```text
python -m unittest discover -s tests -t . -v
Ran 318 tests in 61.333s
OK
```

**318 passati, 0 fallimenti, 0 skip**: 289 precedenti e **29 nuovi** (`test_box_activity.py`: 11; `test_box_order.py`: 12; `test_box_order_ui.py`: 6). Eseguita una sola suite completa dello step, preceduta da verifiche mirate red/green; non ripetuta per documentazione o pacchetti successivi.

Copertura nuova: tutti gli otto ordini con risultati attesi indipendenti, spareggi stabili, inventario vuoto, date assenti/malformate/fusi orari, default, preferenze persistenti/corrotte/non valide, conservazione di percorso e bookmark, Cancel/inversione, errori di scrittura, modifica e foto, spostamento di entrambe le box, eliminazione e pulizia cestino, riapertura, clone/import/cambio tipo, modifica dei valori dei campi dei tipi, riparazione di riferimenti e backup/ripristino. Gli adattatori UI esercitano record reali e impostazioni temporanee, compresa la mancata scrittura durante un cambio cartella Pythonista.

**Dati preesistenti:** 18 file di inventario/impostazioni invariati prima/dopo la suite. Fingerprint SHA-256 aggregato `d97e55fa770baee3ab0620594ab14470efe1c75060611387181075098f198dbf`. Ambito: `StuffData`/impostazioni della radice e delle estrazioni preesistenti sotto `dist/`. Le verifiche usano inventari temporanei; nessuna migrazione applicata ai dati reali.

**Compatibilita statica:** 22 file applicativi analizzati con grammatica Python 3.8 e compilati. Non equivale a esecuzione su Python 3.8/iOS. Dopo il push autorizzato, verificata anche la CI con Python 3.12 su Windows, Linux e macOS; dettagli nella sezione di integrazione.

**Revisione indipendente:** due passaggi di sola lettura, nessun rilievo critico/importante residuo. Esaminati flussi di modifica, date legacy, preferenze, selettori, aggiornamenti Windows, lock Pythonista e probe nativo. Il revisore non ha modificato file ne ripetuto test.

Evidenze locali: `dist/step-02-tests.log`, `dist/step-02-verification.json`, `dist/step-02-data-baseline.json`. La suite e stata eseguita fuori sandbox con eccezione una tantum per utilizzare Python e il launcher Windows installati; stesso limite ambientale gia noto negli step precedenti.

## Build prodotte e smoke test

```text
python tools/make_release.py --platform all
python dist/check_step02_packages.py
python tools/smoke_release.py dist/YetAnotherStuffApp-0.3.8-windows.zip dist/YetAnotherStuffApp-0.3.8-pythonista.zip dist/YetAnotherStuffApp-0.3.8-source.zip --report dist/step-02-console-smoke.json
python dist/smoke_step02.py
python tools/smoke_release.py dist/YetAnotherStuffApp-0.3.8-windows.zip --gui --timeout 30 --report dist/step-02-windows-gui-smoke.json
```

| Archivio in `dist/` | SHA-256 |
| --- | --- |
| `YetAnotherStuffApp-0.3.8-windows.zip` | `0a38988f9909908463d01a973d4e70c0b6d5f6dd8559c2e14ef9f88441d1173e` |
| `YetAnotherStuffApp-0.3.8-pythonista.zip` | `9430ec269f63c0226f4a3b91b71c14f88c45adab7d06d7ee3eb9ed8b15fe297e` |
| `YetAnotherStuffApp-0.3.8-source.zip` | `d65b221ddd789355c538560d9e7f7663f7df1a081254c2244411c8f52edc8d33` |

Integrita ZIP/manifest/SHA-256 e corrispondenza con i sorgenti verificati. Incluso il nuovo modulo `box_order.py`; esclusi inventari, impostazioni private, cache, test e helper locali. Manifest `build_kind=test`, Step `02`, commit base `2b7f1bd` e inventario preciso dei file con le modifiche locali non ancora committate. Build precedenti conservate.

**Tre ZIP estratti: PASSATI.** Avvio, versione e Help > About; veri menu console per default per quantita, A–Z, inversione, Cancel e ordinamento per modifica. Riapertura in un nuovo processo con preferenza conservata; spostamento, foto, eliminazione, svuotamento cestino e ulteriore riapertura con ordine corretto e creazioni invariate. Windows esercitato tramite `.bat`, con percorso dati contenente spazi. Il pacchetto Pythonista e stato eseguito in console Windows: non e un collaudo nativo iOS.

**GUI Windows estratta: PASSATA** per avvio/chiusura automatici, versione/About, menu, tastiera/focus e nuovo selettore. Il probe usa veri widget Tk, verifica default, A–Z, inversione, Cancel, salvataggio e conservazione della selezione per ID. I controlli visivi e l'esecuzione nativa Pythonista rimangono nella checklist.

Evidenze: `dist/step-02-packages.json`, `dist/step-02-console-smoke.json`, `dist/step-02-package-smoke.json`, `dist/step-02-windows-gui-smoke.json`, `dist/SHA256SUMS.txt`.

Controllo finale senza nuova esecuzione dell'app: i 22 sorgenti coincidono con quelli della suite e con i payload dei tre ZIP, CRC/checksum degli archivi validi, 18 file originari ancora invariati e `main`/`origin/main` alla base. Evidenza: `dist/step-02-final-integrity.json`.

## Integrazione e CI dopo il Go

- L'utente ha autorizzato l'integrazione con «go on» e confermato esplicitamente commit, merge locale e push, senza PR. La checklist nativa non viene considerata confermata voce per voce.
- Commit `8d93d060425a32e3d06db1f9757e1b0921321e81` creato sul branch; `main` aggiornato con merge fast-forward allo stesso commit e successivamente pubblicato su `origin/main`. Identita dei commit e working tree pulito verificati prima e dopo il push.
- Dopo il merge, i contenuti di **52 file Python** (app, test e strumenti) sono invariati, confrontando i fine riga normalizzati. Git ha convertito da LF a CRLF soltanto `stuffapp/box_order.py` e `stuffapp/storage.py` fra i 22 sorgenti della suite; nessuna modifica funzionale. Tre ZIP locali e 18 file dati/impostazioni preesistenti ancora identici. Evidenza: `dist/step-02-integration-integrity.json`. Nessuna suite locale o build ripetuta.
- [CI 38924208559](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38924208559), evento push sul commit applicativo, **completata con successo**: Windows **318 passati, 0 fallimenti, 0 skip**; Linux/macOS **316 passati, 0 fallimenti, 2 skip** ciascuno, per controlli specifici Windows (alias dei percorsi e launcher).
- Build dei tre pacchetti e smoke console superati su tutte le piattaforme. Su Windows superati anche launcher, GUI e tastiera/focus. Tre artefatti caricati; job release correttamente saltato. Risultati letti dai job e dai log, riepilogo locale in `dist/step-02-ci.json`.
- Chiusura del rapporto e del piano con commit esclusivamente documentale e `[skip ci]`, senza ripetere suite o rigenerare le build collaudate. Step 3 non iniziato.

## Problemi riscontrati e limiti residui

- Il probe nativo ha riprodotto un difetto del selettore desktop: Invio non confermava. Aggiunti Invio/Esc e focus dopo apertura; prova mirata rossa prima e verde dopo, poi verificata anche sullo ZIP Windows finale. Nessun fallimento nella suite completa finale.
- La data viene registrata **prima** della modifica ai dati per non perdere eventi in caso di uscita/eliminazione. Un successivo errore I/O puo lasciare la data del tentativo, anche se l'articolo rimane invariato; l'errore viene segnalato e il test copre questo comportamento. Un errore nel salvataggio preliminare dell'attivita impedisce di proseguire con lo spostamento. Questo step non trasforma tutte le operazioni multi-file preesistenti in transazioni atomiche.
- I timestamp esistenti hanno precisione di un secondo; eventi nello stesso secondo usano gli spareggi deterministici. Le date storiche senza fuso conservano l'ora registrata; quelle con offset sono normalizzate a UTC per il confronto. Non e possibile ricostruire fusi o vecchie cancellazioni/spostamenti non registrati.
- La preferenza appartiene alla copia dell'app sul dispositivo, non alla cartella dati o ai suoi backup. Per conservarla durante un aggiornamento mantenere `stuffapp_settings.json`; usare impostazioni distinte sui diversi dispositivi.
- Modifiche simultanee da altre istanze/dispositivi e modifica manuale dei file rimangono nei limiti di concorrenza esistenti, da affrontare nello Step 10. Il recupero reset/restore dello Step 1 rimane attivo; nessuna promessa di sincronizzazione cloud automatica.
- Rendering e interazione reali su iPhone, compreso accesso persistente iCloud dopo riavvio, restano da collaudare. I test con adattatori Pythonista non emulano il sistema nativo.

## Checklist visuale — usare inventari di prova

Su Windows GUI, console e Pythonista, dove applicabile:

- [ ] About mostra **0.3.8**; Help > Boxes descrive criteri, inversione, preferenza e date.
- [ ] Preparare tre box A/B/C con 0/1/3 articoli; al primo avvio senza preferenze l'ordine e C, B, A e i conteggi sono corretti.
- [ ] Aprire Sort, scegliere ogni criterio e il suo inverso; verificare nomi simili, date diverse e parita stabili. Lasciare almeno un secondo fra gli eventi di prova.
- [ ] Reverse current order inverte il criterio corrente; Cancel/Esc mantiene l'ordine precedente. In Windows Invio conferma e il focus e visibile.
- [ ] Riordinare mentre una box e selezionata: Windows mantiene la stessa box e mostra i suoi articoli, con All boxes sempre prima.
- [ ] Con ultima modifica attiva, modificare descrizione box, dettagli articolo, aggiungere/togliere una foto: la box pertinente cambia posizione quando la data la rende piu recente.
- [ ] Spostare un articolo fra due box: entrambe registrano l'evento, anche se l'origine diventa vuota; verificare che le altre box non risultino modificate dall'operazione.
- [ ] Eliminare l'ultimo articolo, riavviare e poi provare il ripristino dal cestino: ogni evento resta ordinabile, senza cambiare la data di creazione.
- [ ] Chiudere e riaprire l'app: criterio e verso restano scelti. I selettori per creazione/spostamento/filtro box mostrano un ordine coerente e aprono la box giusta.
- [ ] Aprire un inventario legacy di prova: nessun crash per date mancanti e nessun riordino distruttivo dei record; esportazioni e ordine articoli restano indipendenti.
- [ ] Pythonista: controllare leggibilita di riepilogo/opzioni, scrolling e annullamento. Riavviare con cartella iCloud selezionata: percorso e permesso conservati, preferenza presente.
- [ ] Normale creazione, modifica, ricerca, backup e navigazione ancora utilizzabili su entrambe le GUI e in console.

Copia Windows gia estratta: `dist/YetAnotherStuffApp-0.3.8-windows/YetAnotherStuffApp/`. Avviare `Start Stuff App.bat`; per console passare `--console`. Usare una cartella dati di prova separata e conservare la versione precedente.

## Stato del piano e decisione di avanzamento

- Step 0/1 e follow-up fino alla 0.3.7 gia integrati; rapporti storici invariati. Le precedenti checklist native non ricevono conferme implicite da questo lavoro.
- **Go Step 2 ricevuto con «go on»**, seguito da conferma esplicita della sequenza commit, merge locale e push, senza PR. Il Go autorizza l'integrazione; non attribuisce conferme non espresse alle singole voci della checklist visiva, incluso Pythonista/iCloud nativo.
- Controllo prima del commit: 22 sorgenti identici allo stato della suite, tre ZIP con gli stessi SHA-256 e 18 file dati/impostazioni preesistenti invariati. Suite e build non ripetute.
- **Integrazione completata:** commit applicativo `8d93d06`, fast-forward di `main` al medesimo commit e successivo push; CI Windows/Linux/macOS verde. Controlli di identita, integrita e stato pulito eseguiti senza ripetere la suite locale. Nessun worktree, PR, tag o release.
- Step 3 e successivi non iniziati. I tag, il pannello unico dei filtri e l'ordinamento degli articoli restano separati.
