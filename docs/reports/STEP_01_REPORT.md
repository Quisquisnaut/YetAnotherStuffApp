# YetAnotherStuffApp — Rapporto Step 01

**Data:** 16 ottobre 2026. **Versione precedente / nuova:** 0.3.6 / **0.3.7**.

**Branch:** `feature/step-01-data-safety`, senza worktree. **Base:** `3b083be4b78fc98e75ba062017f71d0c96c0e73b`. **Stato:** verifiche locali completate; **Go ricevuto** per commit, merge locale e successivo push. Integrazione in corso. Checklist nativa non confermata voce per voce; nessun PR, tag o release previsto.

## Ambito approvato

Step 1 del piano: sicurezza copia, backup e reset/ripristino. Approvata l'opzione **A**: mantenere leggeri i backup ordinari e creare backup completi di recupero prima di reset/ripristino, protetti dalla pulizia automatica. Condividere logica e testi tra Pythonista, GUI Windows e console. Non iniziare lo Step 2.

Per **Full recovery** si intendono tutti i file e le cartelle vuote nei sei percorsi gestiti: `boxes/`, `items/`, `images/`, `meta/`, `trash/`, `exports/`. `backups/` e i file estranei nella radice non vengono eliminati dal reset e non sono archiviati ricorsivamente. Le impostazioni del dispositivo accanto all'app rimangono separate.

## Attivita completate

- **Copia legacy sicura:** `config.copy_data()` mantiene firma e ambito parziale originari, ma riusa lo staging verificato di `data_location.copy_inventory`. Rifiuta qualsiasi contenuto preesistente nella destinazione, comprese sole immagini/tipologie, file nascosti e cartelle vuote; nessuna cancellazione per considerare una destinazione vuota. Sono conservati il supporto alla destinazione mancante e il controllo preventivo dei percorsi annidati. Le copie da Settings rimangono complete.
- **Backup modulari:** `backup.py` coordina le operazioni; il nuovo `backup_archive.py` gestisce formato ZIP, manifest, validazione e estrazione. I nuovi archivi hanno manifest versione 2 con scope e SHA-256. I backup precedenti rimangono leggibili; nessuna migrazione dei JSON dell'inventario.
- **Backup ordinari:** automatici/manuali, inventario nei quattro percorsi principali, esclusi cestino/esportazioni e `.tmp`/`.bak`; etichetta **Inventory only (partial)**, ultimi 15 conservati.
- **Recupero completo:** prima di ogni reset o restore viene creato, verificato e pubblicato un ZIP **Full recovery (protected)**. Include ogni file dei sei percorsi, anche dati danneggiati, `.tmp`, `.bak` e cartelle vuote. Un primario JSON corrotto non impedisce la copia di sicurezza necessaria a ripristinare un backup sano. I nuovi recovery ZIP usano il prefisso `stuff-recovery-` e non vengono eliminati automaticamente. Anche i vecchi snapshot con motivo `before-reset`/`before-restore` sono protetti, mantenendo esplicita la loro eventuale natura parziale.
- **Reset/ripristino recuperabili:** il nuovo `folder_transaction.py` registra identita delle directory, inventario e stato prima delle sostituzioni. Verifica che sorgente e staging coincidano ancora con i contenuti protetti/verificati. Esegue rollback anche su `KeyboardInterrupt`, conserva originali e file estranei se il rollback non puo terminare e recupera un processo interrotto prima che `Store` crei directory mancanti o esegua controlli. Una sostituzione gia confermata completa soltanto la pulizia. Journal/staging incoerenti bloccano l'apertura senza creare un inventario vuoto sostitutivo; il launcher termina con codice 1 e un messaggio di recupero, senza traceback per questo caso.
- **Scope del restore:** ZIP ordinario/legacy sostituisce solo i quattro percorsi dell'inventario e conserva cestino/export correnti; un recovery ZIP sostituisce tutti e sei i percorsi. Prima di entrambi viene protetto lo stato corrente completo. I backup e i file estranei nella radice rimangono in posto.
- **Import ZIP:** verifica prima e dopo la copia, confronto anche dello scope/protezione, nomi distinti senza sovrascrivere un import precedente. La pubblicazione riserva esclusivamente il nome finale.
- **Compatibilita Windows:** i nomi dei percorsi gestiti vengono selezionati secondo le regole del filesystem e archiviati con prefisso canonico; una directory fisica `Boxes` non viene omessa su Windows.
- **Interfacce:** etichette, policy di conservazione, conferme reset/restore e messaggi finali sono condivisi. Lo scope compare all'inizio delle voci per essere visibile anche in finestre strette. Pythonista serializza anche il restore con i cambi cartella/reset tramite il lock gia esistente. Help, README e setup aggiornati.
- **Versione/build:** fonte centrale `0.3.7`; i manifest di distribuzione identificano correttamente **Step 01**. Nessuna nuova dipendenza obbligatoria.

## Test automatici

Ambiente: **Windows 10, Python 3.14.7**. Verifica completa sullo stato finale, prima di commit/build:

```text
python -m unittest discover -s tests -t . -v
Ran 289 tests in 121.854s
OK
```

**289 passati, 0 fallimenti, 0 skip**: 258 precedenti e **31 nuovi test**, con verifiche red/green mirate durante l'implementazione. La suite completa e stata eseguita una volta; nessuna ripetizione per successive sole modifiche documentali o pacchetti.

Copertura aggiunta: destinazioni contenenti solo immagini/tipi o file estranei; disco pieno; annullamento; JSON corrente corrotto; ZIP corrotti/versioni sconosciute; duplicati/case alias, link, nomi Windows non sicuri, percorsi e directory fuori ambito, limiti dimensionali; import ripetuti e modifica del manifest durante la copia; cambi successivi al backup o nello staging; ripristino esatto di foto, tipi, cestino/export e temporanei; protezione dalla retention; rollback fallito; file aggiunti da altri processi; avvio bloccato con journal invalido; ripartenza dopo terminazione reale del processo; coerenza dei dialoghi e lock Pythonista.

Revisione indipendente di sola lettura completata, inclusi follow-up. Risolti tutti i rilievi importanti: casing Windows, verifica esatta dello staging, snapshot di JSON danneggiati, semantica del manifest importato e conservazione di candidati reset modificati. Nessun blocco critico/importante residuo segnalato; il revisore non ha ripetuto test.

**Dati esistenti:** 17 file inventario/impostazioni invariati prima/dopo la suite, hash aggregato `293d0b609c5b216f7a9c2e31e43bac20da60e2e863531f5ccff76d8dfab31f7b`. Ambito: `StuffData`/impostazioni alla radice e nelle estrazioni preesistenti sotto `dist/`.

**Compatibilita statica:** 21 file applicativi analizzati con grammatica Python 3.8 e compilati; non equivale a esecuzione su Python 3.8 o su iOS.

Evidenze locali: `dist/step-01-tests.log`, `dist/step-01-verification.json`. Quest'ultimo registra ambiente, commit base, ramo, hash dei 21 sorgenti e fingerprint dei dati. Suite eseguita fuori sandbox con eccezione una tantum per utilizzare Python/launcher Windows installati, evitando il limite ambientale gia diagnosticato negli step precedenti.

## Build prodotte e smoke test

```text
python tools/make_release.py --platform all
python dist/check_step01_packages.py
python dist/smoke_step01.py
python tools/smoke_release.py dist/YetAnotherStuffApp-0.3.7-windows.zip --gui --timeout 30 --report dist/step-01-windows-gui-smoke.json
```

| Archivio in `dist/` | SHA-256 |
| --- | --- |
| `YetAnotherStuffApp-0.3.7-windows.zip` | `4f2c5406f5c0f36682efc4d3a5da29331b64f4413ea409ae6e25595f277f3ebb` |
| `YetAnotherStuffApp-0.3.7-pythonista.zip` | `46a6140a23580dd31e371c25533a014da4f2d20fdd98ed3f98e7ca27ef84e37e` |
| `YetAnotherStuffApp-0.3.7-source.zip` | `97d62967d74825cbfe55fde421050beeb245a94582f2c516147dce3a450eb45f` |

Manifest, inventario e hash verificati; contenuti confrontati con i file attuali, inclusi entrambi i nuovi moduli. Nessun inventario reale, impostazione privata, test o cache incluso. Manifest con Step `01`, versione `0.3.7`, commit base e hash dei contenuti non ancora committati. Build precedenti conservate.

**Smoke dei tre ZIP estratti: PASSATI.** Avvio della vera console, creazione di dati di prova con foto/tipi/cestino/export, reset confermato dai menu, import del recovery ZIP e restore confermato dai menu: ripristino completo verificato tramite hash dei sei percorsi. Windows esercitato anche tramite il `.bat`, con percorso dati contenente spazi. Pacchetto Pythonista eseguito in console Windows: non e un collaudo nativo iOS.

**Windows GUI: PASSATA** per avvio/uscita automatici, versione/About, menu e controlli di tastiera/focus del pacchetto estratto. Rendering e nuovi dialoghi distruttivi restano nella checklist visiva.

Evidenze: `dist/step-01-packages.json`, `dist/step-01-package-smoke.json`, `dist/step-01-windows-gui-smoke.json`, `dist/SHA256SUMS.txt`.

## Problemi riscontrati e limiti residui

- Il primo smoke console si e fermato al timeout: il probe costruiva male l'invocazione `cmd /c` con nome `.bat` e percorso dati entrambi contenenti spazi. Corretto solo il probe usando la quotatura completa `cmd /s /c`; ripetuto il solo smoke interessato, passato su tutti e tre i pacchetti. Nessuna modifica al prodotto, agli ZIP o nuova suite per tale correzione.
- Il recupero e verificato per errori I/O, interruzioni Python e terminazione del processo. **Nessuna garanzia verificata contro guasti hardware/perdita di alimentazione**, modifiche ostili del filesystem o conflitti cloud fra dispositivi. Tenere chiuse altre istanze durante copia/reset/restore.
- La cartella dati stessa rimane in posto; staging e sostituzioni avvengono al suo interno, preservando il percorso e il bookmark Pythonista. Permessi iOS e comportamento reale dei provider iCloud della nuova build richiedono collaudo sul dispositivo.
- Limiti ZIP documentati: 200.000 voci, 8 GiB totali decompressi inclusi metadati, manifest 32 MiB; JSON ordinari 5 MiB. Recovery JSON preservato come byte sotto il limite totale. I nomi devono essere portabili; file/link speciali o nomi non supportati fanno fermare l'operazione prima del reset. Prevedere spazio per ZIP, staging ed eventuali originali conservati.
- I recovery ZIP protetti si accumulano finche eliminati esplicitamente. Conservare copie indipendenti; gestire manualmente lo spazio quando opportuno. Un vecchio backup parziale non acquisisce dati mancanti solo perche ora e protetto.
- Un journal/staging modificato o permessi insufficienti possono richiedere intervento: il programma conserva i file e blocca l'apertura. Ripristinare accesso/spazio e riprovare; non cancellare i metadati di recupero per aggirare il blocco. In alternativa mantenere tutto l'originale e ripristinare il recovery ZIP in un inventario vuoto separato.
- Gli snapshot completi possono contenere record gia danneggiati: integrita dei byte non significa validita del record. I normali controlli, riparazioni da `.bak` e scadenza del cestino restano attivi sui successivi avvii.

## Checklist visuale — inventari di prova, mai dati reali

Su **Windows GUI, console e Pythonista**, dove disponibile:

- [ ] About mostra `0.3.7`; Help distingue copia completa, backup ordinario parziale e Full recovery protetto.
- [ ] Preparare una box, un articolo con foto, un tipo personalizzato, un articolo nel cestino e un export; annotare il percorso dati.
- [ ] Back up now crea un ZIP etichettato **Inventory only (partial)**; lista e messaggi ne mostrano chiaramente lo scope.
- [ ] Annullare reset e restore: nessuna variazione dei dati o nuova copia di sicurezza.
- [ ] Confermare reset: inventario/cestino/export svuotati, recovery ZIP protetto elencato, percorso e backup precedenti conservati.
- [ ] Ripristinare quel recovery ZIP: ritornano box, articolo/foto, tipo, cestino ed export; viene creato un altro snapshot protetto dello stato precedente.
- [ ] Ripristinare un backup ordinario: la conferma dice che cestino/export correnti restano in posto; verificare quel risultato.
- [ ] Provare un vecchio ZIP e un ZIP volutamente corrotto in dati fittizi: il primo leggibile, il secondo rifiutato senza modificare l'inventario.
- [ ] Copia Settings verso cartella con sole immagini o tipi rifiutata senza alterare i file; copia verso cartella vuota ancora funzionante.
- [ ] Riavvio e navigazione normali; su Pythonista, percorso in iCloud invariato e permesso persistente conservato. Controllare leggibilita dei testi lunghi e delle etichette in lista.
- [ ] Pythonista: durante conferma restore/cambio cartella non parte un'altra operazione di location/reset. Non simulare arresti forzati su dati reali; tali guasti sono gia coperti automaticamente su copie temporanee.

Per Windows e disponibile anche l'estrazione in `dist/YetAnotherStuffApp-0.3.7-windows/YetAnotherStuffApp/`; avviare `Start Stuff App.bat`, o passare `--console` per il menu testuale. Usare una cartella di prova separata.

## Stato del piano e decisione di avanzamento

- Step 0 e follow-up fino alla 0.3.6: gia integrati, rapporti storici invariati.
- Step 1: implementato e verificato automaticamente; build consegnabili. **Go all'integrazione ricevuto** con «go on»; la checklist nativa rimane disponibile senza attribuire conferme non espresse alle singole voci.
- Step 2 e successivi: non iniziati. Nessuna sincronizzazione automatica, modifica ai types o ordinamenti aggiunta in questo step.
- Workflow autorizzato: commit sul branch, merge locale fast-forward del medesimo commit, controllo identita/stato pulito senza suite ridondante, poi push. Dopo il Go, i 21 sorgenti applicativi e i tre ZIP coincidono ancora con le evidenze verificate; nessuna nuova suite o build. Nessun PR o release previsto.
