# YetAnotherStuffApp — Rapporto Step 00

**Data:** 15 ottobre 2026\
**Versione precedente / nuova:** `0.3.0` → `0.3.2`; build intermedia `0.3.1` corretta dopo il collaudo Windows dell'utente; consolidato il riferimento iOS `0.3.0+ios.2`.\
**Branch:** `step-00-stabilization`, nel checkout originale `C:\YASA\YetAnotherStuffApp`, senza worktree.\
**Commit base:** `c1094e355ce6c259f58e16434e1ab7bd3375e205`. Go dell'utente ricevuto per il commit locale dello Step 0 sul branch indicato.\
**Stato:** **IN VERIFICA** — verifiche automatiche locali e build completate; collaudi Windows, console e Pythonista confermati dall'utente. Resta la verifica del workflow remoto, non eseguito senza autorizzazione al push.

## Ambito previsto

- Solo Step 0 del [piano effettivamente presente](../YetAnotherStuffApp_DEVELOPMENT_PLAN.md), letto integralmente. Il percorso inizialmente indicato `docs/DEVELOPMENT_PLAN.md` non esisteva; è stata conservata la copia locale con il suo nome originale.
- Stabilizzazione della pipeline Windows, avvio GUI/console, versione e Help/About coerenti, istruzioni corrette, pacchetti Windows/Pythonista/sorgente verificabili.
- Esame e integrazione puntuale del fix iCloud validato dall'utente su iPhone, senza spostare dati o sostituire ciecamente i moduli.
- Esclusi Step 1 e successivi, migrazioni/schema dati, sincronizzazione automatica, PDF Unicode aggiuntivo ed eseguibile Windows autonomo.

## Attività completate

### Fix iCloud e compatibilità

Confrontati separatamente `config.py`, `touch.py` e `__init__.py` del repository con `C:\YASA\Step0-iCloud-reference\stuffapp\`, versione `0.3.0+ios.2`. Applicate solo le differenze esaminate. Subito dopo l'integrazione tutti e tre i confronti `git diff --no-index` hanno restituito **0**; successivamente è cambiata solo la versione centrale, prima `0.3.1` e infine `0.3.2`. I due moduli del fix iCloud restano corrispondenti al riferimento.

- `stuffapp/config.py`: `is_icloud_drive_path()` riconosce i container sotto `Mobile Documents`, incluso `com~apple~CloudDocs` per progetti aperti da File e i container `iCloud~...`. Gestisce input non validi/eccezioni senza operazioni di copia o creazione.
- `stuffapp/touch.py`: Settings distingue cartella iCloud del progetto, cartella dedicata Pythonista e cartella iCloud attualmente selezionata. Conserva il percorso dati; la cartella Pythonista non rilevata non implica che iCloud Drive sia disattivato.
- Consolidati i cinque decoratori `objc_util.on_main_thread` del riferimento; non è stata aggiunta alcuna dipendenza Windows da `objc_util` o da Pythonista.
- Nuovi test su percorsi iCloud/Windows, falsi positivi, input errati, directory mancanti, impostazioni esistenti, selezione della cartella già attiva e conservazione dei file sentinella.

### Versione, interfacce e guida

- Fonte unica `stuffapp/__init__.py`: `__version__ = "0.3.2"`.
- `stuffapp/guide.py`: titolo/versione e About condivisi da tutte le UI; aggiornate le istruzioni GUI/console e i limiti di copia, backup/reset e iCloud.
- `stuffapp/app.py`: versione nel menu console e `--version`, che termina prima di aprire/creare l'inventario. Help > About conserva la numerazione delle voci preesistenti, aggiungendo About in fondo.
- `stuffapp/desktop.py`: versione nel titolo, menu Help con User guide e About; rimossa la voce duplicata da Tools, come richiesto nel collaudo.
- Pythonista conserva Settings > About e riceve About anche attraverso la guida condivisa.
- README e istruzioni Windows distinguono doppio clic/GUI da `--console`, specificano Python richiesto e un aggiornamento con copia preventiva dei dati.
- `config.copy_data()`, persistenza, formati dati, backup/reset e flussi di modifica dell'inventario **non modificati**.

### Correzioni dopo il collaudo Windows della 0.3.1

- **About:** eliminati gli a capo forzati dentro i paragrafi, inclusi `do not prove / that` e `Python uses / Tkinter`. Il testo si adatta alla larghezza della UI; regressione sui paragrafi superata.
- **Box:** il nuovo helper `stuffapp/desktop_dialogs.py` assegna il focus dopo la comparsa del dialogo, preservando OK/Cancel/Invio. Dopo Label + Invio, Description riceve automaticamente il focus. Logica di salvataggio e annullamento invariata.
- **Articoli:** Name riceve il focus iniziale; Cancel non salva un articolo.
- **Menu:** Help rimane nel proprio menu e viene rimosso da Tools.
- **Console Windows:** `stuffapp/terminal.py` verifica/abilita le modalità necessarie ai colori conservando gli altri flag; se non sono disponibili usa testo semplice. Restano rispettati `NO_COLOR`, `TERM=dumb` e l'uscita rediretta. Coperti modalità ereditate insolite e fallimenti API, secondo il [contratto Microsoft di SetConsoleMode](https://learn.microsoft.com/en-us/windows/console/setconsolemode).
- I codici colore non interpretati sono coerenti con i caratteri visibili riferiti dall'utente e omessi dal copia/incolla. Dopo la correzione, l'utente ha confermato «Console OK» sulla nuova build.
- `tools/probe_desktop.py` ha riprodotto nel pacchetto `0.3.1` Help duplicato, Name senza focus e Description senza focus. La stessa prova sulla `0.3.2` passa, salva una box da tastiera e annulla un articolo senza salvarlo, con finestre fuori schermo e soli dati temporanei.
- Conservati gli ZIP `0.3.1` e i dati della cartella estratta dall'utente; i nuovi pacchetti hanno nomi `0.3.2` distinti.

### Pipeline e distribuzione

- `.github/workflows/windows-release.yml`: console eseguita esplicitamente con `--console` sul codice estratto; smoke separati per launcher Windows e GUI Tkinter che termina autonomamente.
- Timeout per processi, step e job; in caso di timeout viene terminato anche l'albero del launcher Windows. Un timeout o un errore di avvio fa fallire la verifica.
- Test e smoke console configurati anche su Linux/macOS con Python 3.12. **Questi runner non sono stati eseguiti in questa sessione locale.**
- Artefatti separati per sistema operativo, con pacchetti e JSON di smoke, conservati in CI per 14 giorni. Upload tentato anche in caso di fallimento, quando esistono file.
- Il launcher batch mantiene gli argomenti, restituisce il codice d'uscita Python e supporta `STUFFAPP_NO_PAUSE=1` per i controlli automatici; uso normale con pausa sugli errori conservato.
- `tools/make_release.py`: preservato l'uso precedente `build(out_dir)`/build Windows predefinita; aggiunti pacchetti `pythonista` e `source`, `--platform all`, build di test predefinita e manifest deterministico `BUILD-INFO.json`.
- Manifest: versione, piattaforma, Step `00`, tipo build, commit base, hash di ogni file e digest dell'inventario del pacchetto. Il commit base **non è il commit finale del codice modificato**: i contenuti non committati sono identificati dagli hash.
- `tools/smoke_release.py`: verifica inventario, hash, percorsi, duplicati, contenuti inattesi, limiti e versione runtime prima dell'avvio; estrae in directory temporanee, usa `--data` esplicito, verifica console/About e opzionalmente launcher/GUI.
- Espansione degli argomenti `*.zip` gestita nello script anche sotto PowerShell. Lo strumento è destinato esclusivamente ai pacchetti locali fidati, non a eseguire archivi di provenienza sconosciuta.
- Nessun accesso a GitHub, esecuzione remota di Actions o pubblicazione di release effettuato. Rimane configurato il flusso preesistente di pubblicazione su tag esplicito, con verifica aggiunta di corrispondenza tag/versione.

## Test automatici

**Ambiente locale:** Windows 10 build `19045`, AMD64, CPython `3.14.7`, standard library. I moduli nativi Pythonista non sono disponibili su questo host.

| Verifica | Risultato effettivo |
|---|---|
| Suite originale, prima delle modifiche, `python -m unittest discover -s tests -t .` | **138 eseguiti: 137 passati, 1 fallito**, 33,562 s |
| Test mirati iCloud/Settings, `python -m unittest tests.test_config tests.test_touch -v` | **10 passati**, 0 falliti, 0 saltati |
| Ciclo test di versione/About/pacchetti | Funzioni mancanti rilevate prima della correzione; **10 test mirati passati** dopo |
| Smoke regressivi di pacchetto/launcher/timeout | Riprodotti l'errore del launcher e il glob PowerShell; inclusi nella suite finale |
| Test mirati terminale/guida, `python -m unittest tests.test_terminal tests.test_app.GuideTests -v` | **12 passati**; fallimenti pertinenti osservati prima delle correzioni |
| Suite completa finale prima del commit, `python -m unittest discover -s tests -t . -v`, tramite `python dist/verify_step00.py` | **175 passati**, **0 falliti**, **0 errori**, **0 saltati**, 49,547 s |
| Sintassi di `main.py` e dei moduli `stuffapp` | **17 file** compilati con l'interprete locale e analizzati anche con grammatica Python 3.8; non equivale a test runtime su Python 3.8/Pythonista |
| `git diff --check` | Uscita **0** |
| Dati prima/dopo la verifica finale | **13 file**, inventario principale e inventari/impostazioni estratti sotto `dist/`; fingerprint SHA-256 uguale, nessuna variazione rilevata |
| Riferimento `main` | Ancora al commit base `c1094e355ce6c259f58e16434e1ab7bd3375e205` |

Il fallimento iniziale era `tests.test_app.ConsoleUIStyleTest.test_terminal_styles_can_be_enabled`: dipendeva dall'ambiente del terminale, mentre il codice rispetta `NO_COLOR` e `TERM=dumb`. Il test ora isola l'ambiente e una regressione verifica esplicitamente `TERM=dumb`. Questa prima correzione riguardava il test; il successivo intervento ANSI Windows descritto sopra conserva la precedenza di queste impostazioni.

I 37 test aggiunti coprono riconoscimento iCloud e Settings (10), avvio/versione/console/About (5), terminale senza colori (1), pacchetti/manifest (3), smoke/launcher/timeout (9), capacità ANSI Windows (8) e paragrafi About (1). I controlli nativi di focus/tastiera sono aggiuntivi, non sommati al conteggio unittest. La suite originale continua a coprire persistenza, formati legacy, immagini, import/export, controlli di sicurezza, backup, tipi e promemoria. Non sono state introdotte le operazioni sui dati previste per lo Step 1.

Evidenze locali:

- [Log integrale dei 175 test](../../dist/step-00-tests.log).
- [Ambiente, comando, risultati e fingerprint](../../dist/step-00-verification.json).
- [Script locale di raccolta delle evidenze](../../dist/verify_step00.py), escluso dagli ZIP e ignorato da Git insieme a `dist/`.

Fingerprint dei dati prima/dopo la verifica finale: `2de3261862c3ace884bf48cd16fb36f28f81b853a2cbdd7bda55739a401bbef8`. Il perimetro include anche dati/impostazioni delle estrazioni sotto `dist/`, presenti dopo i collaudi dell'utente; non è confrontabile direttamente con i precedenti snapshot di 7 o 10 file. Nessun flusso automatico dell'app è stato eseguito sugli inventari dell'utente, letti soltanto per calcolarne gli hash.

### Revisione indipendente

Completata una revisione in sola lettura di diff, nuovi file, requisiti e prove, senza modificare branch, indice o dati. Nessun rilievo critico/importante. L'unico rilievo minore era un oracolo troppo debole nello smoke console: due menu con la versione avrebbero potuto simulare l'avvenuta visualizzazione di About. Aggiunta una regressione che disabilita Help nel vero pacchetto temporaneo mantenendo hash validi: il test ha fallito prima della correzione ed è passato dopo. Lo smoke ora richiede l'intero testo About della guida estratta. Il revisore ha confermato il rilievo risolto; suite completa e smoke console/launcher rieseguiti con successo dopo la correzione. Nessuna modifica ai contenuti degli ZIP, perché lo strumento non è distribuito al loro interno.

Il follow-up sul collaudo ha individuato un altro caso limite ANSI: occorre garantire elaborazione dell'output e VT insieme. Aggiunte due regressioni (modalità `0/2/4/6` e abilitazione fallita), rosse prima e verdi dopo la correzione. Il revisore ha confermato la risoluzione, senza rilievi residui. Le verifiche finali qui riportate si riferiscono alla `0.3.2` corretta.

## Build prodotte

Comando: `python tools/make_release.py --platform all`, uscita **0**. Build correnti **di test**, versione `0.3.2`, Step `00`. Gli archivi intermedi `0.3.1` sono conservati per confronto, non sono la consegna da collaudare.

| Archivio | Contenuto e risultato |
|---|---|
| [Windows ZIP](../../dist/YetAnotherStuffApp-0.3.2-windows.zip) | Codice, README, launcher batch, WINDOWS-SETUP, manifest; inventario/hash, console/About, launcher, GUI e focus/tastiera automatici **OK** |
| [Pythonista ZIP](../../dist/YetAnotherStuffApp-0.3.2-pythonista.zip) | Codice, README, PYTHONISTA-SETUP, manifest; inventario/hash e console del pacchetto su Windows **OK**; collaudo Pythonista finale **OK**, confermato dall'utente |
| [Sorgente/console ZIP](../../dist/YetAnotherStuffApp-0.3.2-source.zip) | Codice applicativo portatile, README, SOURCE-SETUP, manifest; inventario/hash e console/About su Windows **OK**; non è l'intero checkout di sviluppo |

Gli ZIP escludono inventari, impostazioni del dispositivo, backup privati, test, strumenti di sviluppo, cache, report e file temporanei. L'inventario completo e i relativi hash sono dentro ciascun manifest. Il test di build ripetuta verifica output identico a parità di sorgenti e commit.

Comandi di smoke eseguiti con uscita **0**:

```text
python tools/smoke_release.py dist/YetAnotherStuffApp-0.3.2-*.zip --report dist/console-smoke.json
python tools/smoke_release.py dist/YetAnotherStuffApp-0.3.2-windows.zip --launcher --report dist/launcher-smoke.json
python tools/smoke_release.py dist/YetAnotherStuffApp-0.3.2-windows.zip --gui --report dist/gui-smoke.json
```

Evidenze: [console](../../dist/console-smoke.json), [launcher](../../dist/launcher-smoke.json), [GUI e focus](../../dist/gui-smoke.json). Lo smoke ha eseguito `main.py` estratto, costruito widget/menu Tkinter reali in una finestra nascosta, controllato titolo, Help > About e chiusura del mainloop. Il probe aggiuntivo dei dialoghi fuori schermo attesta `keyboard_focus: passed`. I dialoghi informativi sono intercettati: **non è un controllo visuale di finestre o messaggi**.

SHA-256 degli archivi, verificati con `Get-FileHash -Path dist/*.zip -Algorithm SHA256`:

```text
af5d0f45cadb2ff2f6f5b9f574db4834af92f2a7001358820482bd904798a1e1  YetAnotherStuffApp-0.3.2-windows.zip
608fa5a69a0b799fb611a8ab7a05ade60ac9fc7d14ddaeee810c64463d27273f  YetAnotherStuffApp-0.3.2-pythonista.zip
8407ddcf73561b5acd934a47af3836dc07999c2ef81d9df04891864d8447f755  YetAnotherStuffApp-0.3.2-source.zip
```

Disponibile anche [SHA256SUMS.txt](../../dist/SHA256SUMS.txt).

Prima del commit verificata nuovamente, per tutti e tre gli ZIP, la corrispondenza byte per byte di ciascun file distribuito con i sorgenti attuali (normalizzazione CRLF del launcher prevista dal builder). Hash degli archivi invariati: restano i pacchetti 0.3.2 collaudati dall'utente.

## Checklist visuale per l'utente

**Esiti comunicati dall'utente il 15 ottobre 2026 per la 0.3.2:**

- [x] Windows OK.
- [x] Console OK.
- [x] Pythonista OK.

La conferma è complessiva per ciascuna interfaccia. Le singole voci del protocollo seguente restano come riferimento: non sono stati comunicati esiti separati per ogni caso.

Usare cartelle di prova separate. Per un controllo con dati esistenti, fare prima una copia indipendente dell'intera cartella dati, con l'app chiusa, e lavorare su quella copia.

### Windows — nuova build 0.3.2

- [ ] Estrarre lo ZIP in una cartella nuova e verificare presenza di codice, istruzioni, launcher e manifest, senza `StuffData` precompilato o impostazioni personali.
- [ ] Seguire WINDOWS-SETUP; doppio clic su `Start Stuff App.bat`: GUI con titolo `YetAnotherStuffApp 0.3.2`.
- [ ] Help > User guide e Help > About: versione `0.3.2`, testo leggibile, nessun a capo forzato nei punti segnalati e nessun Help duplicato in Tools.
- [ ] New box: scrivere Label e premere Invio; Description deve ricevere il focus. Scrivere senza cliccare, confermare e verificare i valori salvati.
- [ ] New item: digitare subito nel campo Name. Cancel deve annullare senza creare un articolo.
- [ ] Creare box e articolo fittizi; navigare ricerca, tipi, promemoria, cestino e backup senza eseguire reset o copie sull'inventario reale. Chiudere con File > Exit e con il pulsante della finestra; riaprire e verificare i dati di prova.
- [ ] Da PowerShell nella nuova estrazione, `& ".\Start Stuff App.bat" --console`: menu/versione leggibili, nessun prefisso o codice di controllo visibile; Help > About funziona; `0` termina senza GUI. Provare anche testo semplice con `NO_COLOR` se impostato.
- [ ] `py -3 main.py --version`: stampa `YetAnotherStuffApp 0.3.2` senza aprire un inventario.
- [ ] Eseguire `py -3 main.py --data "C:\percorso\inventario-di-prova"`; Settings mostra quel percorso. Con una copia di inventario legacy, verificare box, articoli, tipi e foto attesi dopo chiusura/riapertura.

### iPhone/iPad — pacchetto Pythonista 0.3.2

- [ ] Estrarre/importare il progetto completo e seguire PYTHONISTA-SETUP; avviare `main.py` in Pythonista senza errori dei decoratori.
- [ ] Home > Help > About e Settings > About riportano `0.3.2`; guida e navigazione sono leggibili sullo schermo del dispositivo.
- [ ] Aprire un progetto di prova da File in iCloud Drive: Settings seleziona `iCloud Drive (project folder)`; annotare e confrontare il percorso prima/dopo, che deve restare invariato.
- [ ] Chiudere e riaprire: inventario di prova, tipi e foto restano disponibili; nessuna copia o migrazione viene avviata dal semplice riconoscimento del percorso.
- [ ] Se disponibile, verificare anche la voce distinta `iCloud Drive (Pythonista folder)`; nessun falso messaggio "iCloud non disponibile" per il progetto già aperto in iCloud.
- [ ] Provare un progetto locale: resta `On this device`. Non considerare l'etichetta iCloud una prova di sincronizzazione con Windows.

### CI e altre piattaforme

- [ ] Dopo eventuale autorizzazione all'integrazione/remoto, eseguire il workflow corretto: test, console di tutti gli ZIP, launcher Windows, GUI con chiusura automatica e upload artefatti devono completarsi entro i timeout.
- [ ] Verificare i job Linux/macOS con Python 3.12; scaricare gli artefatti di prova e controllare i JSON. Nessuna pubblicazione/tag durante il collaudo dello Step 0.
- [ ] Eventuale prova console su Android/Termux: avvio, versione/About, uscita e inventario di prova. Non eseguita in questa sessione.

**Collaudi storici riconosciuti:** baseline Windows `0.3.0` e Settings iPhone `0.3.0+ios.2` confermati dall'utente. Il collaudo Windows `0.3.1` ha generato le cinque richieste di correzione sopra descritte. Queste prove non valgono come approvazione visuale della `0.3.2`.

**Collaudo finale 0.3.2:** l'utente ha comunicato «Windows OK. Console OK. Pythonista OK» e successivamente ha dato il Go al commit locale. Nessun Go a merge, push o avvio dello Step 1 è stato ricevuto.

## Difetti e problemi aperti

| Problema | Stato, conseguenze e seguito |
|---|---|
| Workflow bloccato sul launcher GUI | Corretto; comandi equivalenti eseguiti localmente con esito positivo. Esecuzione effettiva su GitHub **ancora non effettuata**, senza push autorizzato |
| Launcher perde il codice di errore dopo `pause` | Riprodotto (`7` diventava `0`), corretto e coperto da regressione Windows |
| Test colori dipendente dal terminale | Difetto di isolamento preesistente corretto nel test; successivo supporto ANSI Windows verificato separatamente. Suite finale tutta verde |
| Glob ZIP sotto PowerShell | Rilevato e corretto nello smoke script; regressione passata |
| Possibile falso positivo nello smoke About | Rilievo di revisione corretto, regressione red/green e follow-up del revisore completati; nessun difetto attuale della funzione About riscontrato |
| Feedback Windows 0.3.1: About, focus box/articolo, Help duplicato, prefissi console | Corretto nella 0.3.2; regressioni automatiche e probe nativo red/green superati. Collaudo finale Windows e console confermato OK dall'utente |
| Percorso piano diverso da quello iniziale | Identificato `docs/YetAnotherStuffApp_DEVELOPMENT_PLAN.md`; copia originale conservata e aggiornata, nessuna rinomina distruttiva |
| Copia verso destinazione parzialmente popolata e backup/reset incompleto | Rischi **preesistenti**, potenzialmente distruttivi: restano allo Step 1. Non corretti in questo step; limiti documentati in Help/README |
| Nuova UI Pythonista e resa visuale Windows | Collaudi finali confermati OK dall'utente; protocollo dettagliato conservato. Non è stata verificata una sincronizzazione iCloud tra dispositivi |

Non sono emersi fallimenti irrisolti nei 175 test finali o negli smoke della 0.3.2. Questo non garantisce assenza di difetti fuori dalle condizioni provate.

## Stato del piano

- Step 0: implementazione, revisione, suite, pacchetti e smoke locali pronti; collaudi Windows, console e Pythonista approvati dall'utente, Go al commit locale ricevuto. Resta la futura verifica Actions prima della chiusura del gate della pipeline.
- Step 1–13: **non iniziati**. Nessuna modifica alle operazioni di copia/backup/reset è anticipata.
- `main` e i riferimenti remoti sono invariati; Go limitato al commit sul branch `step-00-stabilization`. Nessun merge, push, tag o release effettuato. I pacchetti restano locali in `dist/`, ignorata da Git.

## Decisione di avanzamento

**Approvazione dell'utente: RICEVUTA per i collaudi Windows, console e Pythonista e per il commit locale dello Step 0.**

Creare il commit sul branch locale senza integrare in `main`, effettuare push o pubblicazioni o iniziare lo Step 1. Queste azioni richiedono successive istruzioni esplicite. Il workflow remoto resta non verificato e non viene dichiarato verde.
