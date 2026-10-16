# YetAnotherStuffApp — Rapporto Step 03

**Data:** 16 ottobre 2026. **Versione precedente / nuova:** 0.3.8 / **0.3.10**; build intermedia 0.3.9 conservata.

**Branch:** `feature/step-03-box-tags-filters`, senza worktree. **Base:** `b690aa8c63466c232f9c3736191e855637cd402b`. **Stato: APPROVATO** — opzione A e feedback implementati; verifiche automatiche e build completate. Go finale ricevuto con «go on»: autorizzati commit sul branch, merge fast-forward nel main locale e successivo push, senza PR, tag o release. Integrazione in corso; checklist visuale conservata senza attribuire conferme non espresse per le singole voci.

## Ambito approvato e attivita completate

- **Tag delle box:** campo opzionale `tags`, indipendente dai tipi degli articoli. Inserimento/modifica nelle tre interfacce, anche multiplo, tramite etichette separate da virgole. Normalizzazione Unicode NFC e degli spazi; confronto senza distinzione di maiuscole/minuscole, mantenendo la prima grafia della singola box. Massimo **20 tag per box**, **64 caratteri per etichetta**; virgole separatrici e caratteri di controllo non ammessi nelle etichette. Input non valido rifiutato prima della scrittura.
- **Servizio condiviso `stuffapp/box_tags.py`:** identita, lettura legacy tollerante, filtraggio delle box, catalogo e conteggi delle associazioni, ordinamento A–Z/Z–A e maggior/minor numero di box. A parita di conteggio usa la chiave alfabetica; l'inversione dei conteggi conserva lo spareggio. Il catalogo conta ciascuna box una volta e mostra una grafia rappresentativa deterministica fra quelle registrate. Nessuna data temporale inventata per i tag.
- **Compatibilita:** box storiche senza `tags` sono considerate senza tag, senza migrazione o riscrittura in lettura. Letture di tag legacy malformati non fanno fallire la navigazione. Le API mantengono gli argomenti precedenti; `create_box()` e `search_items()` aggiungono opzioni compatibili. Modificare i tag aggiorna `modified`, preservando `created` e la logica dello Step 2.
- **Filtri combinabili:** il tag selezionato limita box e articoli appartenenti alle box associate. Tutti gli otto ordinamenti delle box rimangono utilizzabili. La ricerca degli articoli combina con AND testo, box, tag, tipo, posizione, origine, prezzi e fotografie, mantenendo gli ordinamenti dei risultati esistenti. La ricerca libera conserva il significato precedente; il filtro tag e una corrispondenza esatta senza distinzione di maiuscole/minuscole.
- **Modello condiviso `stuffapp/filters.py`:** copia di lavoro separata dai filtri attivi, schema comune dei campi e validazione completa prima dell'applicazione. Prezzi zero conservati; valori non validi, intervalli invertiti e riferimenti non piu disponibili segnalati. Un tag senza box associate rimane selezionabile e restituisce zero risultati.
- **Unico modulo Filter:** Windows usa una finestra con tutti i campi, combobox, checkbox, messaggio di errore e scrolling; Pythonista una schermata con campi, switch e scelte espandibili inline, senza dialoghi annidati per i criteri. Console mostra un riepilogo unico e permette di modificare solo i criteri necessari.
- **Apply / Clear / Cancel:** Apply valida l'intera bozza e applica una sola volta. Clear / Reset filters azzera i campi della bozza, incluso il testo; occorre Apply per attivare l'azzeramento. Cancel, Esc, Back o chiusura della finestra scartano la bozza. Un errore conserva filtri attivi e modulo aperto. All tags rimuove solo la condizione tag; All boxes solo la box specifica.
- **Preferenze:** A–Z predefinito per il selettore tag; quattro ordini e comando Reverse sempre disponibili. L'ordine viene salvato sul dispositivo solo dopo Apply riuscito, separatamente dall'inventario e dai suoi backup; percorso dati, bookmark Pythonista e altre impostazioni sono preservati. Annullare non scrive. I filtri attivi continuano a durare solo per la sessione; le associazioni dei tag sono persistenti nei dati delle box.
- **Coerenza Windows:** filtri e sidebar condividono la box scelta. Una combinazione tag/box incompatibile conserva entrambe le condizioni e mostra zero risultati; nessuna riga sbagliata viene selezionata se la box e nascosta dal tag. All boxes cancella esplicitamente solo la box. Se la box resta visibile, ordinare conserva la selezione per ID. Tag mostrati nella navigazione e nei dettagli.
- **Coerenza Pythonista:** Home > Filter boxes e Search > Filters usano lo stesso modello. Apply usa il lock esistente dei cambi cartella; una bozza appartenente a una cartella precedente viene rifiutata. I controlli di annullamento non cambiano filtri o preferenze. Tag presenti nei dettagli e nei riepiloghi delle box.
- **Feedback approvato nella 0.3.10:** riepiloghi persistenti `FILTERED`, conteggi visibili/totali e criteri distinti per box e articoli. Il tag interessa entrambi; gli altri criteri interessano solo gli articoli. Zero corrispondenze conserva lo stato filtrato; il solo ordinamento resta neutro. Liste box in ambra, risultati articoli in verde acqua, con palette condivisa e varianti per l'aspetto corrente. Windows ripristina gli stili nativi dopo la rimozione dei filtri e conserva colori leggibili per la selezione. Pythonista segue l'aspetto di sistema e lascia neutro il contenuto completo di una box, ora etichettato esplicitamente. Console conserva etichette e conteggi con `NO_COLOR` o senza ANSI. Nessuna nuova impostazione globale Light/Dark dello Step 11.
- **Clear filters immediato:** pulsante Windows accanto a Filter, azione diretta Home/Search su Pythonista e comando Search in console. Esegue la stessa operazione di **Search > Clear filters**: cancella condizioni attive e ricerca, aggiorna subito risultati/colori, senza aprire il modulo. **Clear box tag** elimina soltanto il tag e preserva i criteri degli articoli. Il precedente Clear interno al modulo conserva la semantica della bozza descritta sopra.
- **Move Windows:** finestra modale con destinazione scelta da una combobox di sola lettura e pulsanti Move/Cancel. Destinazioni secondo l'ordine box dello Step 2, esclusa la sorgente, incluse le box nascoste dal filtro tag. Etichetta e ID breve distinguono le destinazioni. Nessuna scrittura su Cancel/Esc/chiusura o senza destinazione valida; dopo lo spostamento risultati e conteggi aggiornati.
- **Backup ed esportazione:** associazioni preservate in backup/ripristino e cestino. Tag inclusi negli export Markdown/PDF di box e inventario. Gli export del singolo articolo mantengono campi e riferimento alla box gia esistenti; nessun nuovo formato o flusso di importazione introdotto.
- **Guida e distribuzione:** README, Help e tre setup aggiornati. Versione centrale **0.3.10**, manifest **Step 03**, nessuna nuova dipendenza obbligatoria. Step 4 e successivi non iniziati.

## Test automatici ed evidenze

Ambiente: **Windows 10, Python 3.14.7**. Suite finale sul codice funzionale definitivo:

```text
python -m unittest discover -s tests -t . -v
Ran 390 tests in 52.711s
OK
```

**390 passati, 0 fallimenti, 0 skip**: 318 precedenti e **72 nuovi** — tag/storage/export 12, modello filtri 8, console 8, Windows 6, Pythonista 13, riepiloghi/clear/palette condivisi 9, stato Windows/Move 7, stato Pythonista 9. Test esistenti adattati ai nuovi campi e al flusso Filter intenzionalmente riprogettato; conservate le verifiche dei comportamenti precedenti.

Copertura: normalizzazione/spazi/Unicode/duplicati, limiti e input malformati, scritture rifiutate senza modifiche, creazione e attivita, legacy senza riscrittura, quattro ordini/conteggi/spareggi, ricerca con criteri combinati e nessun risultato, backup/ripristino/cestino/export, Apply/Clear/Cancel, zero prezzi, validazione, annullamento delle preferenze, conservazione delle impostazioni, callback delle box, sidebar coerente e blocco cartella Pythonista. Le prove UI riusano Store, modello e file impostazioni reali; i sostituti riguardano i confini grafici non disponibili.

Nella build intermedia 0.3.9 una prima suite completa era passata con 364 test. Un controllo successivo ha riprodotto un difetto sui tag Unicode lunghi la cui chiave cresce con il case folding (`ß` → `ss`). Separata la validazione dell'identita da quella dell'etichetta persistita; limiti di scrittura 20/64 invariati. Aggiunta regressione catalogo → bozza → Apply → ricerca, verificata prima rossa e poi verde: suite 0.3.9 finale di 365 test passata. Il feedback funzionale approvato su indicatori, colori, Clear filters e Move ha poi richiesto questa nuova verifica 0.3.10. Nessuna suite ripetuta per sola documentazione.

**Dati preesistenti:** 35 file di inventario/impostazioni invariati prima/dopo la suite 0.3.10. Fingerprint SHA-256 aggregato `028ad7f76b00a0998e831cebe9b5ece6c653a953e402c21499c35acc6a997904`. Baseline aggiornata prima del follow-up per includere i dati creati dall'utente durante il collaudo 0.3.9; la precedente verifica preservava 28 file. Ambito: `StuffData` e impostazioni della radice e delle estrazioni preesistenti in `dist/`; verifiche funzionali con inventari temporanei.

**Compatibilita statica:** 25 sorgenti applicativi analizzati con grammatica Python 3.8 e compilati. Non equivale a esecuzione nativa Python 3.8/iOS. Nessun nuovo job CI o collaudo nativo Linux/macOS prima del Go; CI attesa dopo il push autorizzato.

**Revisione indipendente:** intero diff, nuovi moduli/test non tracciati, correzione Unicode e ulteriore revisione del feedback UX 0.3.10; nessun rilievo azionabile residuo accertato. Revisione di sola lettura, senza ripetere suite o build.

Evidenze locali correnti: `dist/step-03-colors-tests.log`, `dist/step-03-colors-verification.json`, `dist/step-03-colors-data-baseline.json`; conservati tutti i log/JSON e gli archivi 0.3.9 precedenti. Suite finale eseguita fuori sandbox per utilizzare i subprocess del launcher Windows. Le librerie Tcl/Tk della distribuzione Python locale sono state estratte temporaneamente dai suoi ZIP, senza modificare l'installazione o includerle nei pacchetti.

## Build prodotte e smoke test

```text
python tools/make_release.py --platform all
python tools/smoke_release.py dist/YetAnotherStuffApp-0.3.10-windows.zip dist/YetAnotherStuffApp-0.3.10-pythonista.zip dist/YetAnotherStuffApp-0.3.10-source.zip --report dist/step-03-colors-console-smoke.json
python dist/check_step03_colors_packages.py
python dist/smoke_step03_colors_gui.py
```

| Archivio in `dist/` | SHA-256 |
| --- | --- |
| `YetAnotherStuffApp-0.3.10-windows.zip` | `0ad9decd9e029c88fc6617dc60703b8c57daeb8a1b3b34582f80d773d083002e` |
| `YetAnotherStuffApp-0.3.10-pythonista.zip` | `1f24bbeaa46b0af8ff9c70189233afccde4a32c51ab860263f94b7ffaeb0f615` |
| `YetAnotherStuffApp-0.3.10-source.zip` | `8afe911bec7646fea62d9e8a9d373fdab0f4a4601c9d18732243a1321b7cf66d` |

Integrita ZIP, CRC, manifest, SHA-256 e corrispondenza con i sorgenti verificati. Inclusi `box_tags.py`, `filters.py` e `filter_appearance.py`; esclusi dati, impostazioni private, cache, test e helper locali. Manifest `build_kind=test`, Step `03`, commit base `b690aa8` e inventario dei contenuti con modifiche locali non ancora committate. Build precedenti conservate.

**Tre pacchetti estratti: PASSATI.** Avvio/versione/Help > About, veri menu console per tag + testo/posizione, Apply, Clear, Cancel, inversione e persistenza dell'ordine in un nuovo processo. Associazioni, backup/ripristino, export e composizione con tutti gli ordini delle box verificati nei pacchetti finali; incluso il limite Unicode corretto. Windows provato anche tramite BAT con percorso dati contenente spazi. Verificati anche i nuovi riepiloghi e Clear filters immediato nei tre pacchetti. Il pacchetto Pythonista eseguito in console Windows non costituisce collaudo nativo iOS.

**GUI Windows estratta: PASSATA.** Avvio/chiusura automatica, About, menu, focus/tastiera, nuovo modulo completo con criteri combinati, Enter/Esc, Cancel/chiusura, Clear/Apply, validazione e correzione, zero prezzo alla riapertura, ordinamento/inversione dei tag e conservazione della selezione. Verificati inoltre titoli/conteggi per ambito, colori ambra/verde acqua e ripristino degli stili, selezione nativa leggibile, solo ordinamento neutro, testo live e zero risultati, Clear filters nella toolbar e Clear box tag; Move con combobox reale, destinazioni ordinate anche nascoste dal tag, Enter/Esc, convalida, annullamento senza scritture e conteggi aggiornati. Il probe utilizza widget Tk reali; resta distinto dal collaudo visuale dell'utente.

Evidenze: `dist/step-03-colors-console-smoke.json`, `dist/step-03-colors-package-smoke.json`, `dist/step-03-colors-windows-gui-smoke.json`, `dist/step-03-colors-windows-gui-smoke.log`, `dist/SHA256SUMS.txt`. Controllo conclusivo senza rieseguire l'app in `dist/step-03-colors-final-integrity.json`.

Copia Windows pronta: `dist/YetAnotherStuffApp-0.3.10-windows/YetAnotherStuffApp/`. Avviare `Start Stuff App.bat`, eventualmente con `--console`; scegliere una cartella dati di prova separata.

## Difetti risolti e limiti residui

- Risolto e coperto da prova Tk prima rossa e poi verde: limite prezzo `0` mostrato vuoto alla riapertura. Risolto e coperto anche nei tre ZIP finali il limite Unicode della chiave tag descritto sopra.
- Lo script locale di smoke esteso aveva una quotatura `cmd /c` errata con nomi BAT e cartella dati contenenti spazi, causando timeout senza avvio dell'app. Corretto lo script con `call`; stessi flussi passati e nessuna modifica al launcher distribuito.
- Rendering, scrolling, tastiera, gesti di navigazione e permessi iCloud su iPhone/iPad richiedono collaudo reale. I 22 test filtri/stato dell'adattatore Pythonista non emulano tali comportamenti nativi.
- Filtri attivi validi per la sessione; tag e ordine del selettore persistenti. Il file impostazioni del dispositivo va conservato durante l'aggiornamento e non viene incluso nei backup dell'inventario.
- La grafia di un tag e conservata nella box; cambiare una box non rinomina automaticamente le associazioni nelle altre. Il catalogo raggruppa grafie equivalenti e usa conteggi globali, indipendenti dal filtro attivo.
- Restano i limiti gia documentati sulle operazioni multi-file, modifiche simultanee fra istanze/dispositivi e supporto Unicode del PDF. Nessuna nuova sincronizzazione o semantica di importazione delle box introdotta.

## Checklist visuale — usare inventari di prova

Su Windows GUI, console e Pythonista, dove applicabile:

- [ ] About mostra **0.3.10**; Help spiega tag e modulo Filter.
- [ ] Creare A con `Work, work, Blue`, B con `work`, C con `Home`: A conserva solo `Work, Blue`; il selettore mostra Work associato a 2 box, Blue e Home a 1.
- [ ] Aggiungere/rimuovere tag da Edit Box, annullare una modifica e riaprire; dati e grafia corretti. Provare un'etichetta oltre 64 caratteri: errore controllato, nessun salvataggio parziale.
- [ ] Provare A–Z/Z–A e maggior/minor numero box, piu Reverse; selezione tag mantenuta e risultati invariati quando cambia solo l'ordine delle opzioni.
- [ ] Filtrare per Work: lista box A/B, articoli solo da quelle box. Cambiare ciascun criterio/verso dello Step 2: filtro e ordinamento rimangono combinabili. All tags torna a tutte le box mantenendo gli altri criteri.
- [ ] Verificare riepiloghi FILTERED con conteggi e criteri: box in ambra soltanto con tag, articoli in verde acqua con qualunque filtro attivo. Solo ordinamento neutro; zero risultati resta filtrato.
- [ ] Premere Clear filters fuori dal modulo: ricerca e condizioni attive rimosse subito, tutte le righe tornano visibili e i colori diventano normali. Clear box tag rimuove soltanto il tag e conserva gli altri criteri.
- [ ] Windows: Move apre una combobox con tutte le altre box, comprese quelle nascoste dal tag; Move sposta nella destinazione scelta, Cancel/Esc non modifica dati.
- [ ] Aprire Filter: tutti i criteri nello stesso modulo. Combinare tag, testo e posizione o prezzo; Apply produce risultati corretti. Combinazione senza corrispondenze mostra zero risultati senza perdere condizioni.
- [ ] Modificare piu campi e ordine tag, poi Cancel/Esc/Back o chiusura: risultati e preferenza invariati. Clear seguito da Cancel conserva i filtri; Clear seguito da Apply azzera anche il testo.
- [ ] Prezzo non valido o minimo maggiore del massimo: modulo aperto, errore visibile, filtri attivi invariati. Correggere e applicare. Minimo `0` visibile anche riaprendo Filter.
- [ ] Windows: Tab/focus, scrolling, Enter ed Esc utilizzabili; box selezionata conservata se visibile. Box specifica incompatibile con tag mostra zero risultati e nessuna selezione sidebar errata; All boxes elimina solo la condizione box.
- [ ] Pythonista: scelte inline, scrolling su schermo piccolo, testo leggibile, tastiera e comandi Apply/Clear/Cancel raggiungibili; nessun dialogo annidato per ciascun criterio.
- [ ] Chiudere/riaprire: tag e ordine del selettore conservati, filtri di sessione azzerati. Pythonista/iCloud: cartella scelta, permesso e impostazioni precedenti preservati.
- [ ] Con ultima modifica attiva, cambiare tag: box riordinata quando la data e piu recente, creazione invariata. Lasciare almeno un secondo fra gli eventi.
- [ ] Inventario legacy di prova, creazione/modifica/ricerca, fotografie, backup/ripristino ed export box/inventario ancora utilizzabili; nessuna modifica involontaria ai dati.

## Stato del piano e decisione di avanzamento

- Step 0–2 e relativi follow-up gia integrati; rapporti storici invariati.
- Step 3 opzione A e feedback implementati e verificati; **Go finale ricevuto con «go on»**. Integrazione autorizzata in corso: commit sul branch, merge fast-forward nel `main` locale, controllo identita/stato pulito senza suite ridondanti, poi push.
- Nessun worktree, PR, tag o release previsto. Le singole voci della checklist nativa restano non confermate dove l'utente non ha fornito un esito esplicito.
- Step 4 e successivi non iniziati.
