# YetAnotherStuffApp — Piano di sviluppo incrementale e verifica

**Data:** 15 ottobre 2026\
**Repository di riferimento:** `Quisquisnaut/YetAnotherStuffApp`\
**Branch di partenza verificato:** `main`, commit `c1094e355ce6c259f58e16434e1ab7bd3375e205` (14 ottobre 2026)\
**Versione esaminata:** `0.3.0`\
**Stato aggiornato (15 ottobre 2026):** **Step 0 APPROVATO e integrato** in `main`, versione condivisa `0.3.2`, commit applicativo `00fdc7f`. Fix iOS `0.3.0+ios.2` consolidato; feedback Windows recepito. 175 test locali superati prima del commit; collaudi Windows, console e Pythonista confermati OK dall'utente. Merge fast-forward e push eseguiti dopo autorizzazione esplicita. [CI verde su Windows, Linux e macOS](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38781729987). Nessun tag o release; Step 1 non iniziato.\
**Destinazione prevista nel repository:** `docs/DEVELOPMENT_PLAN.md` (da pubblicare quando saranno disponibili i permessi).\
**File attuale:** copia locale del piano, non sincronizzata con GitHub.

**Intervento aggiuntivo autorizzato dopo lo Step 0:** scelta della cartella dati in Pythonista, con percorso manuale `0.3.3` e selettore nativo `0.3.4` collaudati dall'utente; estensione `0.3.5` approvata con scelta **2** il 16 ottobre: etichette/guida chiare e copia completa verificata dal picker. Anticipate solo le protezioni necessarie a questa copia; resto dello Step 1 da affrontare separatamente. Branch locale `feature/pythonista-data-folder`, senza worktree. [PYTHONISTA_DATA_FOLDER_REPORT](reports/PYTHONISTA_DATA_FOLDER_REPORT.md); commit dopo Go, merge finale locale prima del push.

**Collaudo e integrazione finale `0.3.5`:** **Pythonista OK**, seguito da **«Go on»** dell'utente. Commit applicativo `5beb879`, merge fast-forward nel `main` locale e poi push completati. [CI Windows/Linux/macOS verde](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38870387745). Nessun worktree, PR, tag o release; medesimi sorgenti/pacchetti verificati senza suite locali ridondanti.

## Avanzamento del lavoro

- **Step 1 — opzione A approvata e implementata nella `0.3.7`:** backup ordinari parziali conservati, recovery ZIP completi e protetti prima di reset/restore, copia legacy senza overwrite, staging verificato, journal/rollback e recupero prima dell'apertura. Test su JSON danneggiati, guasti, import, alias Windows e interfacce coerenti: **289 passati, 0 fallimenti, 0 skip**; 17 file dati/impostazioni invariati. Tre ZIP Step 01 verificati, veri menu console reset/restore sui pacchetti e GUI/focus Windows superati. Branch `feature/step-01-data-safety`, senza worktree, base/main `3b083be` invariata; nessun commit/merge/push. Collaudo nativo e Go in attesa; Step 2 non iniziato. [STEP_01_REPORT](reports/STEP_01_REPORT.md).
- Go Step 1 ricevuto con «go on»: autorizzati commit, merge nel `main` locale e successivo push, senza worktree o PR. I 21 sorgenti e i tre ZIP sono ancora identici allo stato verificato; suite e build non ripetute. Checklist nativa conservata senza attribuire conferme non espresse per le singole voci. Step 2 non iniziato.

- Follow-up `0.3.6` approvato con «Unify Both and keep consistent»: gestione cartella unificata Pythonista/Windows GUI/console, etichette Default e Reset richieste, scelta Open / Copy complete folder / Cancel per ogni selettore, nessuna copia parziale da Settings. Branch `feature/unified-data-location`, senza worktree; **258 test passati**, veri dialoghi Tk verificati, 14 file dati/impostazioni invariati, tre ZIP verificati in `dist/`. Regola generale di coerenza salvata in `AGENTS.md`. Nessun commit/merge/push; `main` invariato a `ead832e`. Collaudo visivo e Go in attesa; resto dello Step 1 separato. [UNIFIED_DATA_LOCATION_REPORT](reports/UNIFIED_DATA_LOCATION_REPORT.md).
- Go `0.3.6` ricevuto con «Go on»: autorizzati commit sul branch, merge nel `main` locale e successivo push, senza worktree o PR. Sorgenti applicativi e tre ZIP ancora identici allo stato verificato; suite locale non ripetuta. Checklist visiva conservata senza attribuire conferme non espresse per le singole voci.
- Integrazione `0.3.6` completata: commit applicativo `dc74e8693ede1de105f0492605e739de318bd972`, fast-forward del `main` locale allo stesso commit e successivo push. [CI 38881741874](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38881741874) verde: 258 test Windows; 257 passati e 1 skip Windows-only su Linux/macOS; build/smoke console e launcher/GUI Windows superati. Sorgenti e ZIP locali invariati; chiusura documentale con `[skip ci]`, senza nuove suite o build. Nessun worktree, PR, tag o release; ulteriori attivita dello Step 1 separate. [Rapporto](reports/UNIFIED_DATA_LOCATION_REPORT.md).

- Baseline `main` `c1094e3` v0.3.0: generati i pacchetti di riferimento Windows/Pythonista. Avvio Pythonista verificato dall’utente dopo la correzione del decoratore `objc_util.on_main_thread`.
- Step 0, correzione locale iCloud: rilevamento delle cartelle aperte con File sotto `com~apple~CloudDocs`, etichette Settings aggiornate senza spostare i dati, build iOS `0.3.0+ios.2` e test automatici locali.
- **Verifica visiva su iPhone completata per la correzione iCloud**: iCloud Drive (project folder) selezionato, percorso dei dati invariato, `0.3.0+ios.2` visualizzato in About. **Build Windows 0.3.0 di riferimento confermata funzionante dall’utente.** Non equivale al collaudo di una futura build Windows modificata nello Step 0.
- Completata l'implementazione locale dello Step 0: pipeline console/GUI con timeout, gestione errori launcher, versione centrale `0.3.2`, Help > About, istruzioni e pacchetti con inventario/hash. Suite completa: **175 passati, 0 fallimenti, 0 skip**. Smoke dei pacchetti estratti e focus/tastiera Windows superati; inventari principali e delle estrazioni di prova invariati durante la verifica. Revisione indipendente e follow-up completati, rilievi risolti.
- Feedback Windows `0.3.1` corretto nella `0.3.2`: About senza a capo forzati, focus Description dopo Label/Invio, focus iniziale Name, Help solo nel proprio menu e colori ANSI Windows verificati/abilitati con fallback a testo semplice. Probe nativo red sulla `0.3.1` e verde sulla `0.3.2`; archivi precedenti conservati.
- Collaudo finale `0.3.2` confermato dall'utente: **Windows OK, Console OK, Pythonista OK**; successivo Go al commit locale sul branch. Verifica prima del commit: 175 test passati, 13 file dati/impostazioni invariati e contenuti degli ZIP corrispondenti ai sorgenti attuali.
- Autorizzazione esplicita «Merge e poi push» ricevuta: `main` aggiornato tramite fast-forward a `00fdc7f` e pubblicato su `origin/main`. [Workflow 38781729987](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38781729987) completato con successo su Windows, Linux e macOS; artefatti scaricati e JSON di console, launcher e GUI/focus controllati. Nessuna release pubblicata.
- Rapporto e checklist: [docs/reports/STEP_00_REPORT.md](reports/STEP_00_REPORT.md); build locali in `dist/`. Stato dello Step 0: **APPROVATO e integrato**. Step 1 non iniziato.
- Regola operativa richiesta dall'utente e salvata in `AGENTS.md`: niente suite ridondanti per fast-forward dello stesso commit verificato; niente test per sole modifiche a documentazione o pacchetti di distribuzione. Usare controlli di coerenza/integrita pertinenti e non rilanciare la CI per tali aggiornamenti.
- Intervento Pythonista `0.3.3`: aggiunta voce Settings per un percorso esistente, verifica di accesso, conferma e memorizzazione senza copiare l'inventario corrente. **193 test passati**, pacchetti verificati, 13 file dati/impostazioni invariati. L'utente ha confermato il funzionamento su iPhone e richiesto anche un dialogo per scegliere la cartella.
- Estensione `0.3.4`: selettore nativo iOS, permesso persistente tramite bookmark e recupero prima dell'apertura dei dati se la cartella deve essere autorizzata di nuovo; percorso manuale conservato. **220 test passati**, revisione senza rilievi residui, 13 file dati/impostazioni invariati e pacchetti Windows/Pythonista/sorgente verificati in `dist/`. Step 0 resta chiuso alla `0.3.2`; questo intervento separato attende collaudo del picker e Go. Nessun commit, merge o push; Step 1 non iniziato.
- Collaudo `0.3.4`: l'utente conferma il picker funzionante su Pythonista iOS. Richiesti testi piu chiari e opzione di copia nel picker; dopo discussione e confronto tra alternative, approvata esplicitamente l'opzione 2. La `0.3.5` aggiunge Open / Copy / Cancel, copia completa verso cartella completamente vuota, verifica SHA-256, conservazione dell'originale e serializzazione dei cambi cartella; include backups, trash ed exports. Non modifica reset o backup ordinari, ne la vecchia copia parziale Windows/console/scorciatoie. **241 test verificati**: 240 passati nella suite completa, 1 launcher fallito nel sandbox e passato isolatamente fuori sandbox senza modifiche ai sorgenti. Revisione senza blocchi, 13 file dati/impostazioni invariati; build Windows/Pythonista/sorgente `0.3.5` verificate in `dist/`. Nessun commit/merge/push; collaudo iPhone della nuova copia e Go in attesa.
- Collaudo finale `0.3.5` confermato: **Pythonista OK**. Go ricevuto per commit e prosecuzione del workflow concordato: merge locale prima del push, senza worktree o PR. Sorgenti applicativi e hash dei tre ZIP ancora identici a quelli verificati; aggiornamenti di chiusura solo documentali, nessuna nuova suite.
- Integrazione `0.3.5` completata con commit applicativo `5beb87924eebba6e5880c8699e3f960fe77fb190`: commit sul branch, fast-forward di `main` allo stesso commit e successivo push, working tree pulito. [Workflow 38870387745](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38870387745) verde: 241 test passati Windows; 240 passati e 1 skip launcher Windows su Linux/macOS; build/console e launcher/GUI Windows superati. Chiusura documentale con `[skip ci]`, senza nuove suite o rigenerazione degli ZIP collaudati. Resto dello Step 1 separato.

## 1. Obiettivi e limiti

Migliorare affidabilità, sicurezza, usabilità, importazione, catalogazione e distribuzione dell'app, conservandone la natura **offline-first**, i file dati locali, le tipologie personalizzabili e il supporto alle interfacce **Windows/Tkinter**, **iOS/Pythonista** e **console** (inclusi gli ambienti dove Tkinter non è disponibile).

**Vincoli espliciti:**

1. Procedere **per step distinti**, senza aggiungere modifiche estranee allo step in corso.
2. Mantenere un'architettura **modulare**. La logica condivisa risiede nei servizi/moduli, non nelle singole UI; preservare la separazione tra persistenza, importazione, esportazione, query, controlli e presentazione.
3. Non introdurre regressioni nei dati, nei flussi esistenti o nelle interfacce; mantenere compatibilità con gli inventari precedenti e prevedere migrazioni dei campi quando necessarie.
4. Prevenire ove possibile **overflow, crash, corruzione dei dati e vulnerabilità**, specialmente durante importazioni, operazioni sui file, elaborazione di immagini, ordinamenti e ripristini.
5. **Non** sviluppare per ora il supporto a caratteri Unicode aggiuntivi nei PDF; resta escluso dal piano attivo.
6. Aggiornare **la versione dell'applicazione** quando viene completato uno step che modifica una build; utilizzare come fonte unica `stuffapp/__init__.py` e mostrare la versione nelle interfacce.
7. **Ogni step richiede test automatici, build versionate, smoke test del pacchetto distribuito, checklist di controllo visivo/manuale e approvazione prima di passare allo step seguente.**
8. **Alla conclusione di ogni step produrre un rapporto** con attività realizzate, risultati dei test, artefatti, istruzioni di verifica visuale, difetti, rischi residui, modifiche non effettuate e attività ancora da svolgere.
9. Non effettuare modifiche non richieste e non integrare in `main` una fase non approvata.
10. **Trasferimento e sincronizzazione dei dati Windows–iCloud:** trattare qualsiasi copia, importazione o sostituzione come operazione potenzialmente distruttiva. Prevedere anteprima, confronto, backup di entrambe le destinazioni, commit/rollback e gestione delle modifiche divergenti; non promettere sincronizzazione bidirezionale automatica senza sistema anticollisione.
11. **Usabilità e temi:** impiegare colori funzionali, contrasto leggibile e uno stile visivo coerente, con **tema scuro opzionale** selezionabile dall’utente; i filtri vanno raccolti in una sola schermata/modulo, senza la sequenza di domande attuale. Conservare accessibilità e compatibilità multipiattaforma.

## 2. Ciclo di lavoro di ogni step

1. **Preparazione:** verificare il commit di partenza, creare un branch dedicato, confermare per iscritto ambito e criteri di accettazione. Evidenziare eventuali problemi della base già presenti prima dello step.
2. **Implementazione limitata:** modificare solo i moduli interessati; evitare duplicazione di algoritmi tra UI. Conservare commenti esistenti quando si interviene sul codice, salvo richiesta esplicita.
3. **Verifiche statiche e automatiche:** eseguire tutti i test esistenti e quelli nuovi; includere input malformati, limiti dimensionali, eccezioni I/O, perdita di spazio, dati legacy e rollback. I risultati devono riportare numeri e ambiente, non formule generiche come "test superati".
4. **Build:** generare pacchetti versionati. Provare i file estratti/distribuiti, non soltanto i sorgenti in working tree. Pubblicare gli artefatti intermedi per il collaudo; riservare le Release definitive alle versioni approvate.
5. **Smoke test e controllo visivo:** verificare avvio, navigazione, risultati, messaggi, finestre/dialoghi, comportamento con dati reali non sensibili e possibilità di recupero. Fornire una checklist concreta all'utente per le piattaforme non collaudabili automaticamente.
6. **Rapporto di fine step:** produrre un file `reports/STEP-XX-REPORT.md` (o il corrispondente allegato locale fino all'accesso in scrittura) con evidenze, stato e piano residuo.
7. **Gate di approvazione:** lo step seguente non inizia senza esito accettabile di test/build/checklist e approvazione esplicita dell'utente. Eventuali difetti danno luogo a correzioni e nuova verifica dello stesso step.

### Condizioni minime di accettazione

- Tutti i test pertinenti e di regressione superati, senza fallimenti non spiegati.
- Nessun bug noto introdotto che comprometta l'integrità dei dati; errori d'importazione ed I/O gestiti in modo controllato.
- Build generata, avviabile, con versione coerente e contenuto verificato.
- Checklist visuale completata e risultati annotati; piattaforme non ancora testate dichiarate come tali.
- Rapporto finale dello step consegnato e lavori residui aggiornati.

## 3. Piano operativo per step

### Step 0 — Stabilizzazione della pipeline, build, versione e istruzioni

**Interventi:**
- Correggere il workflow GitHub Actions Windows: il suo smoke test attuale invia `0` a un launcher che, quando disponibile, apre Tkinter e resta in `mainloop()`. Eseguire il test console esplicitamente con `--console` e aggiungere un test GUI separato che termini autonomamente.
- Rendere affidabili i controlli automatici del pacchetto ZIP, con timeout appropriati per evitare job bloccati.
- Organizzare produzione e conservazione degli artefatti di test. Valutare test su Linux/macOS quando praticabili.
- Mostrare il numero di versione nella GUI desktop, nell'interfaccia Pythonista e nella console, anche tramite **Help > About**; leggere il valore dalla definizione centrale di versione.
- Allineare README, istruzioni e launcher Windows al comportamento GUI attuale, distinguendo avvio GUI e console.
- Definire nomi, versione e inventario dei pacchetti: ZIP Windows richiedente Python, archivio Pythonista, archivio sorgente/console. Non promettere un `.exe` autonomo senza una specifica fase aggiuntiva.
- **Difetto iOS già corretto localmente e validato visivamente:** rilevamento delle cartelle esterne di iCloud Drive in Pythonista, senza spostare o sovrascrivere `StuffData`. Consolidare fix e test nella futura build condivisa; non interpretare la corretta etichetta iCloud come prova di sincronizzazione tra dispositivi.

**Controllo visivo/manuale:** estrarre ZIP pulito; avviare GUI Windows, uscire correttamente; avviare `--console`, uscire; verificare numero versione e Help > About; seguire le istruzioni di installazione su una cartella nuova. Confermare il riconoscimento della cartella iCloud e la preservazione del percorso dati su iOS. **Esito finale:** Windows, console e Pythonista confermati OK dall'utente sulla `0.3.2`; smoke del workflow corretto superati su GitHub.

### Step 1 — Sicurezza delle operazioni sui dati e backup/reset

**Interventi:**
- Rafforzare `config.copy_data()` affinché non cancelli dati preesistenti nella destinazione considerata erroneamente vuota, inclusi file di tipologie e immagini senza `boxes/*.json` o `items/*.json`.
- Usare preparazione/staging e validazione delle copie prima di attivare una nuova cartella dati, con comportamento esplicito se la destinazione contiene dati.
- Distinguere backup ordinario e **backup completo prima di reset**: il backup attuale esclude cestino ed esportazioni, mentre il reset li cancella. Assicurare che tali contenuti siano recuperabili quando previsti; documentare esattamente il contenuto dei backup.
- Introdurre casi limite e simulazioni di guasto: permessi, disco pieno, archivi corrotti, rollback, interruzioni, cartelle parzialmente popolate.

**Controllo visivo/manuale:** copia verso cartella vuota, cartella contenente sole immagini o tipologie, conferme e rifiuti; backup, reset e ripristino con inventario, cestino ed esportazioni di prova; assenza di perdite silenziose.

### Step 2 — Ordinamento delle box

**Interventi:** introdurre una logica condivisa di ordinamento, indipendente dalle UI, usando campi esistenti e metadati calcolati. Le box supportano:

| Criterio | Direzione normale | Direzione inversa |
|---|---|---|
| Numero articoli | **Decrescente, predefinita dell'app** | Crescente |
| Nome | A–Z | Z–A |
| Data creazione box | Più recente prima | Meno recente prima |
| Ultima modifica box | Più recente prima | Meno recente prima |

Per **ultima modifica** considerare tanto variazioni della box (nome, descrizione, tag) quanto creazione, modifica, eliminazione, spostamento e modifiche fotografiche degli articoli pertinenti. Gestire correttamente entrata e uscita di un articolo da una box. Definire un meccanismo persistente affidabile per registrare le modifiche in modo che cancellazioni e spostamenti non facciano sparire la data dell'evento. La data di creazione della box resta invariata. Ordinamenti stabili e deterministici in caso di parità (es. nome e ID). Possibilità di ricordare le preferenze dell'utente.

**Controllo visivo/manuale:** creare box con 0, 1 e molti articoli; verificare default per quantità; invertire ogni criterio; modificare un articolo, spostarlo e verificare che l'ordine per ultima modifica reagisca; chiudere e riaprire.

### Step 3 — Tag e filtri delle box

**Interventi:** campo opzionale `tags` delle box, lista di etichette normalizzate, non dipendente dai tipi degli articoli. Consentire aggiunta/rimozione/tag multipli e filtro per un tag specifico; opzione "Tutte le box"; filtro combinabile con tutti gli ordinamenti dello Step 2. Documentare regole per spazi, duplicati, maiuscole/minuscole e limiti agli input. Compatibilità con box storiche senza il campo `tags`.

**Riprogettazione del comando Filter, nello stesso step:** sostituire la sequenza attuale di più domande e schermate con **un solo pannello/modulo** in cui siano visibili e impostabili insieme tutti i criteri di filtro già supportati, compreso il nuovo filtro per tag, quando pertinente. Mostrare i criteri attivi, consentire più condizioni nella stessa operazione e offrire comandi ben distinguibili **Apply**, **Clear/Reset filters** e **Cancel**. L'applicazione delle modifiche avviene una sola volta, con Apply; Cancel non altera i filtri in uso. Mantenere invariato il significato della ricerca e dei filtri, evitando regressioni. GUI Windows e Pythonista: form unico con controlli adatti alla piattaforma, evitando schermate annidate; console: acquisizione raggruppata dei criteri in un unico flusso breve, senza domande superflue, preservando l'accessibilità da tastiera. Separare il modello dei filtri condiviso dal codice UI e dalla persistenza, anche in presenza di input incompleti o non validi.

**Ordinamento dell’elenco dei tag:** alfabetico A–Z/Z–A e per numero di box associate (maggior numero/minor numero), con comando di inversione sempre disponibile. L’ordinamento riguarda il selettore/elenco dei tag, non altera l’ordine degli articoli o le associazioni. I tag non hanno una data di creazione persistente nella versione proposta: non introdurre un criterio temporale fittizio. Default proposto: A–Z; da confermare nel collaudo della relativa UI.

**Controllo visivo/manuale:** tag singolo/multiplo, due box con medesimo tag, rimozione e modifica tag, nessun risultato, ordinamento A–Z/Z–A e per numero box, inversione ordinamento mentre filtro attivo, riapertura dell'app e import/export quando pertinente. Aprire Filter e verificare che **tutti i criteri siano nello stesso modulo**; combinarne almeno due, premere Apply e controllare i risultati; riaprire e modificare i criteri; verificare Clear/Reset e Cancel (nessuna variazione), comportamento su schermo piccolo iPhone e via tastiera su Windows.

### Step 4 — Ordinamento articoli all'interno delle box

**Interventi:** nei contenuti di ciascuna box prevedere:

| Criterio | Direzione normale | Direzione inversa |
|---|---|---|
| Nome articolo | **A–Z (default iniziale)** | Z–A |
| Data aggiunta alla box | Più recente prima | Meno recente prima |
| Ultima modifica articolo | Più recente prima | Meno recente prima |

**Distinzione essenziale:** la data di aggiunta alla box non equivale sempre alla creazione dell'articolo nell'inventario. Registrare esplicitamente l'entrata nella box e aggiornare il valore in caso di trasferimento; prevedere migrazione o comportamento documentato per i record legacy. Impostazioni degli articoli indipendenti da quelle delle box.

**Controllo visivo/manuale:** nomi simili, date diverse, spostamento tra box, modifica di dettagli e fotografie, inversione di tutti gli ordinamenti, gestione dei record preesistenti.

### Step 5 — Ordinamento dei types

**Interventi:** ordinamento dell’elenco delle tipologie di articolo (**types**) nella logica condivisa, con scelta e inversione del verso per ciascun criterio:

| Criterio | Direzione proposta | Direzione inversa |
|---|---|---|
| Nome type | A–Z | Z–A |
| Numero di articoli assegnati | Dal maggiore al minore | Dal minore al maggiore |

L’ordinamento non deve alterare ID, definizioni, campi, opzioni né assegnazioni degli articoli. Preservare la possibilità di identificare i types predefiniti, modificati e personalizzati; evitare ordinamenti temporali basati su date non registrate. Preferenza iniziale proposta: ordine per nome, con direzione invertibile. Type senza articoli e types rimossi/restaurabili non devono provocare crash. A parità di valore usare nome e ID come criteri stabili.

**Controllo visivo/manuale:** tipi predefiniti e personali, due types con lo stesso conteggio, uno vuoto, scelta A–Z/Z–A, conteggio crescente/decrescente, assegnazione di un articolo a un altro type e aggiornamento dell’ordine.

### Step 6 — Import/export dei types e ripristino delle definizioni predefinite

**Interventi:**
- **Export di un type o di tutti:** formato JSON versionato e validato, contenente nome, campi, tipi dei campi, opzioni, ID di origine e metadati necessari, senza esportare automaticamente gli oggetti. Dichiarare chiaramente quali dati vengono inclusi.
- **Import di un type o di più types:** anteprima, mappatura dei nomi/ID, scelta tra creazione di nuovi types, aggiornamento esplicitamente autorizzato o salto, risoluzione dei conflitti; non alterare in silenzio articoli esistenti né perdere i campi già valorizzati.
- **Reset di un type predefinito:** riutilizzare e testare `Store.reset_type(type_id)`, già esistente nel codice per i tipi forniti dall'app; non riscriverlo inutilmente. Mostrare differenze e richiedere conferma, con backup preventivo quando esistono personalizzazioni.
- **Reset di tutti i types predefiniti:** nuova operazione esplicita con anteprima dei tipi coinvolti, inclusi quelli modificati o rimossi, backup e possibilità di annullamento/rollback. Conservare per impostazione predefinita i types personalizzati e tutti gli articoli.
- **Types creati/importati dall’utente:** non esiste una definizione di fabbrica a cui tornare. Prima di offrire «Reset to default» individuare una definizione iniziale salvata (snapshot) o richiedere all’utente quale base ripristinare; non cancellare types personalizzati o i loro dati sotto l’etichetta «Reset».
- Protezioni: limiti dimensionali e strutturali sui file, validazione di JSON, campi, opzioni e riferimenti, gestione versioni e duplicati, prova di import interrotta e rollback. Moduli di interscambio distinti dalla persistenza e dalle UI.

**Controllo visivo/manuale:** export→import di un type di prova, export/import multiplo, conflitti di nome, campi a scelta e personalizzati, reset singolo e globale dei predefiniti, confronto prima/dopo di oggetti e campi, annullamento, file danneggiato, verifica del backup recuperabile. **Da chiarire prima dell'implementazione:** cosa significhi «default» per un type personalizzato senza snapshot iniziale.

### Step 7 — Importazione delle box da Markdown

**Interventi:** importare le box già esportate in Markdown dal programma, inclusi gli articoli e, quando presenti e validi, i riferimenti alle immagini. Analizzare l'attuale formato Markdown senza presumere una fedeltà perfetta dei dati per le informazioni non serializzate. Anteprima dell'importazione, scelta della destinazione, gestione di conflitti e duplicati, report dei campi non ricostruibili o delle immagini mancanti. Nuovi ID dove appropriato. Non confondere il flusso con l'importazione di un singolo articolo.

**Controllo visivo/manuale:** esportare box di prova con articoli/tipi/foto; importarla; confrontare numero e campi; provare nomi duplicati, file incompleti e immagini mancanti; verificare che un errore non lasci importazioni parziali.

### Step 8 — Formato completo e importazione selettiva delle box

**Interventi:** introdurre export/import di box tramite ZIP strutturato e versionato, con manifest, definizioni dei tipi richiesti, oggetti e fotografie. Validare tutti i percorsi e i nomi di archivio, dimensioni decompresse, numero file, estensioni/contenuti, riferimenti, manifest, duplicati e compatibilità. Evitare path traversal, ZIP bomb, symlink o elementi inattesi, decompressioni eccessive e overwrite accidentali. Staging, anteprima, conferma e commit/rollback per l'importazione. Consentire di importare box selezionate senza sostituire l'intero inventario.

**Controllo visivo/manuale:** trasferire una box completa tra inventari di test, con tipi personalizzati e immagini; ri-importare lo stesso ZIP; provare ZIP danneggiato, fuori formato, molto grande; verificare inventario invariato in caso di rifiuto.

### Step 9 — Trasferimento/sincronizzazione controllata tra Windows e iCloud Drive

**Obiettivo minimo:** permettere all’utente di aggiornare manualmente l’inventario tra YetAnotherStuffApp su Windows e quello aperto in Pythonista da iCloud Drive, **senza un server applicativo e senza sovrascritture silenziose**. Distinguere chiaramente il trasferimento unidirezionale da una vera sincronizzazione bidirezionale.

**Percorso A: scambio manuale raccomandato.**
1. Chiudere l'app su entrambe le piattaforme. Effettuare backup indipendenti dei due inventari prima del trasferimento.
2. Esportare uno **snapshot portatile, versionato e completo** dell'inventario sorgente (box, articoli, foto, tipi, tag, metadati e quanto esplicitamente incluso nel pacchetto; chiarire trattamento di cestino/esportazioni), con manifest, checksum e limiti contro archivi pericolosi. Se riutilizza il formato ZIP dello Step 8, completarne prima i requisiti mancanti per l'intero inventario.
3. Trasferire lo ZIP via app File/iCloud Drive e iCloud per Windows, quando disponibile, oppure con trasferimento manuale controllato tramite un archivio scaricato su Windows.
4. Sul dispositivo di destinazione mostrare **anteprima e confronto**: versione origine/destinazione, numero box/articoli/foto/types, modifiche non presenti nell'altro inventario, conflitti di identità, possibili cancellazioni. Se entrambi sono cambiati, **non unire o sostituire automaticamente**: richiedere scelta esplicita o interrompere il trasferimento.
5. Salvare un backup della destinazione, estrarre e verificare lo snapshot in staging, applicare con sostituzione atomica/rollback dove possibile, quindi verificare conteggi e campioni di dati. Registrare data, origine, identificativo snapshot ed esito. Documentare il percorso inverso Windows → iPhone.

**Percorso B: cartella iCloud condivisa (facoltativo, solo dopo il rafforzamento dei conflitti dello Step 10).** Valutare l'uso di iCloud per Windows per accedere allo stesso inventario. Prima di abilitarlo, verificare la reale disponibilità della cartella specifica su Windows e iOS; evitare scritture simultanee, dati «solo cloud» non ancora scaricati, file parziali, conflitti tra revisioni e perdita di modifiche. Non considerare una directory `com~apple~CloudDocs` come prova che i dati siano già sincronizzati con Windows.

**Sicurezza:** nessun accesso automatico alle credenziali iCloud, nessun trasferimento nascosto, nessun percorso imposto. Nessuna modifica ai dati reali durante i test. Se non è possibile definire come risolvere conflitti tra due inventari modificati, il sistema deve **fermarsi e conservare entrambi**.

**Controllo visivo/manuale:** inventari di prova distinti Windows/iPhone; esportazione iOS→Windows e Windows→iOS; confronto di types, tag, box, articoli e foto; ripetizione dello stesso import, import corrotto, inventario di destinazione modificato, annullamento e ripristino del backup. Verificare che i dati reali restino invariati fino a esplicita conferma.

### Step 10 — Conflitti tra dispositivi e operazioni multi-file

**Interventi:** completare la protezione contro la perdita silenziosa di aggiornamenti se più dispositivi usano la stessa cartella sincronizzata; confronto delle revisioni prima del salvataggio e strategia di conflitto che conservi i dati. Migliorare la coerenza delle operazioni multi-file (ad esempio modifiche delle definizioni dei tipi che coinvolgono numerosi articoli), con rollback/ripresa idempotente quando praticabile. Documentare limiti delle cartelle cloud e casi non risolubili automaticamente.

**Controllo visivo/manuale:** modificare lo stesso articolo in due copie di un inventario di prova, simulare conflitto; verificare avviso e conservazione delle versioni; interrompere operazione multi-file in simulazione controllata e verificare recupero.

### Step 11 — Colori, tema chiaro e modalità scura opzionale

**Interventi:** applicare **colori funzionali e coerenti** alle interfacce, distinguendo azioni principali, informazioni, selezioni, messaggi di successo, avvisi ed operazioni distruttive; evitare colori decorativi che compromettono la leggibilità. Progettare una **palette condivisa di ruoli semantici** (sfondo, testo, selezione, bordi, primario, avviso, errore), con adattatori per Tkinter e Pythonista e senza duplicare i colori nei singoli componenti. Consentire all'utente di scegliere **Light (predefinito)** o **Dark (facoltativo)** da Settings; memorizzare la preferenza in modo persistente e specifico del dispositivo, non insieme ai dati dell'inventario da trasferire tra sistemi. Non imporre il tema scuro né cambiare l'aspetto dopo un aggiornamento senza richiesta. Dove il sistema non permetta di tematizzare un elemento nativo, mantenere il comportamento nativo leggibile e documentare il limite.

La console conserva il supporto già esistente ai colori ANSI e a `NO_COLOR`; non deve produrre sequenze di controllo su terminali che non le supportano. Nessun tema deve alterare salvataggi, esportazioni o file dati. Nessuna dipendenza obbligatoria nuova per eseguire Pythonista o la GUI desktop.

**Test automatici:** selezione e persistenza Light/Dark, fallback su preferenza mancante o invalida, ruoli semantici, coerenza di comportamento tra temi, compatibilità con terminali senza colori e `NO_COLOR`, assenza di accessi a risorse non disponibili e di crash al cambio tema.

**Controllo visivo/manuale:** navigare schermate principali, liste, dialoghi, editor, pulsanti, filtri e Help con Light e Dark su Windows e iPhone; verificare contrasto e leggibilità di testo, elementi disabilitati, azioni distruttive, selezione/focus, campi lunghi e tastiera; cambiare tema, chiudere e riaprire l'app, verificare la scelta conservata. La modalità scura è **opzionale**, non il tema predefinito.

### Step 12 — Miglioramenti pratici dell'interfaccia

**Interventi:** galleria Windows con miniature, selezione e riordinamento immagini; inserimento rapido ripetuto di articoli nella box corrente con tipo predefinito e flusso semplificato, senza perdere campi avanzati. Riutilizzare i servizi esistenti e non duplicare la logica dei dati nelle interfacce.

**Controllo visivo/manuale:** foto multiple, apertura, rimozione, ordine e persistenza, aggiunta consecutiva di più articoli, annullamento e gestione degli errori, in tema chiaro e scuro.

### Step 13 — Ricerca, Help e completamento regressioni

**Interventi:** ottimizzare la ricerca in inventari grandi (es. debounce UI e cache con invalidazione corretta); evitare letture ripetitive superflue. Ampliare il **menu Help già presente**, con istruzioni concise sulle funzioni meno ovvie: import box e formati, tag/filtri e ordinamento dei tag, uso del nuovo **Filter a modulo unico** (Apply/Clear/Cancel), ordinamento e import/export/reset dei types, direzione degli ordinamenti e significato delle date, editor dei tipi, promemoria, backup/cestino, trasferimento manuale e sincronizzazione Windows–iCloud, scelta **Light/Dark** e versione/About. Completare prove multipiattaforma, documentazione di regressione, eventuali guide alle build.

**Controllo visivo/manuale:** ricerca con filtri, risultati corretti dopo modifica, navigazione della guida, istruzioni comprensibili, coerenza delle schermate su piattaforme supportate, leggibilità in entrambe le modalità di colore.

## 4. Sicurezza e qualità trasversali

Valgono per ogni step pertinente:

- Validazione di numeri, contatori, date, prezzi e tipi di input; limiti documentati e proporzionati, inclusi valori molto grandi, date impossibili e campi assenti.
- Prevenzione di path traversal, link simbolici problematici, lettura/scrittura fuori dalla directory consentita, ZIP bomb, nomi riservati e file non validi.
- Limitazione dell'uso di memoria (streaming quando appropriato), gestione di immagini e archivi pesanti senza bloccare la UI.
- Gestione controllata di errori disco, permessi, file mancanti, JSON incompleti, corruzione e ripristini interrotti.
- Operazioni che modificano più file con staging, convalida e rollback dove praticabile.
- Import/export e reset dei types non devono eliminare campi valorizzati degli articoli, alterare gli ID dei record o cancellare definizioni personalizzate senza anteprima, conferma e recupero.
- Ogni trasferimento Windows–iCloud va prima provato su inventari fittizi; copia cloud e sincronizzazione effettiva non sono sinonimi, e conflitti non risolti non devono essere nascosti.
- Test automatici su inventari vuoti, grandi, legacy e volutamente danneggiati; verifiche di integrità prima e dopo l'operazione.
- Filtri con applicazione esplicita: combinazioni di criteri, Clear e Cancel non devono produrre modifiche involontarie. Tema chiaro/scuro e colori devono preservare contrasto, leggibilità e funzionamento, senza accesso o modifica dei dati.
- Evitare promesse di sicurezza o assenza assoluta di crash: registrare risultati delle verifiche e rischi residui reali.

## 5. Strategia delle build e delle versioni

- **Windows:** usare ed estendere `tools/make_release.py` e `.github/workflows/windows-release.yml`. Il pacchetto ZIP attuale richiede Python installato; nessun eseguibile autonomo è implicito.
- **iPhone/iPad Pythonista:** preparare archivio sorgente con i file necessari e istruzioni di importazione/esecuzione, poi richiedere collaudo reale su dispositivo.
- **Console/Linux/macOS/Android:** archivio sorgente e istruzioni; eseguire gli smoke test negli ambienti disponibili, dichiarando le piattaforme non collaudate.
- Ogni pacchetto contiene **versione e identificativo dello step/commit** rintracciabili; niente dati personali, backup privati, cache, test o file temporanei incorporati.
- Gli artefatti di prova sono distinti dalle release approvate; mantenere possibilità di tornare alla build precedente.
- Verificare la coerenza del valore `__version__` nei nomi dei file, nell'interfaccia e nel rapporto di step.

## 6. Rapporto obbligatorio alla fine di ogni step

Produrre un file individuale e aggiornare l'avanzamento del piano. Il rapporto deve avere almeno questa struttura:

```markdown
# YetAnotherStuffApp — Rapporto Step XX

Data:
Versione precedente / nuova:
Branch e commit:
Stato: IN VERIFICA | DA CORREGGERE | APPROVATO

## Ambito previsto
- ...

## Attività completate
- Moduli/file interessati; comportamento introdotto; modifiche escluse.

## Test automatici
- Comandi eseguiti; ambiente; numero di test passati/falliti/skippati.
- Edge cases, sicurezza, regressioni, limiti noti.

## Build prodotte
- Nomi/percorsi/link effettivamente verificati, contenuto, checksum se disponibile.
- Smoke test eseguiti per ogni piattaforma e risultato.

## Checklist visuale per l'utente
- [ ] Operazione 1, risultato atteso...
- [ ] Operazione 2, risultato atteso...
- [ ] Operazione 3, risultato atteso...

## Difetti e problemi aperti
- Riproduzione, severità, conseguenze e rimedio previsto.

## Stato del piano
- Step completati:
- Step corrente e attività ancora da fare:
- Prossimi step e dipendenze:

## Decisione di avanzamento
- Approvazione dell'utente: IN ATTESA | APPROVATO | RESPINTO
- Note e azioni prima dello step successivo:
```

Al termine dello step consegnare **sia il rapporto sia le build**. Il rapporto non deve dichiarare verificati test, controlli manuali, pacchetti o permessi che non siano stati effettivamente verificati.

## 7. Stato corrente del piano

| Step | Stato | Build | Test automatici | Controllo visuale | Rapporto |
|---|---|---|---|---|---|
| 0. Pipeline / build / versione / iCloud | **APPROVATO e integrato in main** | Windows/Pythonista/sorgente `0.3.2` in `dist/`; `0.3.1` conservate | 175 passati locali; CI Windows/Linux/macOS verde; console/launcher/GUI/focus OK | Windows, console e Pythonista `0.3.2` confermati OK dall'utente | [STEP_00_REPORT](reports/STEP_00_REPORT.md) |
| 1. Dati / backup / reset | **Go ricevuto**, opzione A implementata; integrazione in corso | Windows/Pythonista/sorgente `0.3.7` in `dist/`, manifest Step 01 | 289 passati; round-trip dei pacchetti e GUI/focus Windows OK; 17 file dati invariati | Checklist nativa non confermata voce per voce | [STEP_01_REPORT](reports/STEP_01_REPORT.md) |
| 2. Ordinamento box | Da iniziare | No | No | No | No |
| 3. Tag box / filtri / ordinamento tag | Da iniziare | No | No | No | No |
| 4. Ordinamento articoli | Da iniziare | No | No | No | No |
| 5. Ordinamento types | Da iniziare | No | No | No | No |
| 6. Import/export/reset types | Da iniziare | No | No | No | No |
| 7. Import box Markdown | Da iniziare | No | No | No | No |
| 8. Import/export box ZIP | Da iniziare | No | No | No | No |
| 9. Trasferimento manuale Windows–iCloud | Da iniziare | No | No | No | No |
| 10. Concorrenza / atomicità | Da iniziare | No | No | No | No |
| 11. Colori / Light-Dark opzionale | Da iniziare | No | No | No | No |
| 12. Galleria / aggiunta rapida | Da iniziare | No | No | No | No |
| 13. Ricerca / Help / regressioni | Da iniziare | No | No | No | No |

**Nota di contesto (verifica iniziale del 15 ottobre 2026):** il workflow Windows aveva eseguito correttamente 138 test e creato il pacchetto, ma il controllo di avvio del launcher era rimasto bloccato finché il job era stato annullato. Problema corretto nello Step 0 e pipeline rieseguita con successo: run `38781729987`.

**Esclusioni correnti:** supporto Unicode esteso per PDF; creazione automatica di un `.exe` Windows; sincronizzazione automatica bidirezionale senza un meccanismo di conflitto robusto; nuove funzionalità non espressamente approvate.

**Il piano è stato ampliato il 15 ottobre 2026 su richiesta dell’utente** con ordinamento types e tag, import/export e reset dei types, scambio manuale protetto Windows–iCloud, **Filter a modulo unico** al posto di più domande consecutive, **colori coerenti e tema scuro opzionale** (tema chiaro predefinito). Il piano contiene ora **14 step (0–13)**. **Il piano verrà aggiornato dopo ogni step**, conservando traccia dei lavori completati, dei problemi aperti e delle decisioni dell'utente.
