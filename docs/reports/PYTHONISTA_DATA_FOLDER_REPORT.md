# Pythonista — scelta della cartella dati e selettore nativo

**Data:** 16 ottobre 2026\
**Versione:** `0.3.2` → `0.3.5` (percorso manuale `0.3.3`, picker `0.3.4`, copia completa `0.3.5`)\
**Branch:** `feature/pythonista-data-folder`, checkout originale, senza worktree\
**Commit base:** `6e64bd3c449d724b00ff3efc6865195424452f9b`\
**Stato:** APPROVATO e INTEGRATO — percorso manuale `0.3.3`, picker `0.3.4` e versione finale `0.3.5` confermati funzionanti su iPhone dall'utente. Ricevuto **«Pythonista OK. Go on.»**; commit applicativo `5beb87924eebba6e5880c8699e3f960fe77fb190`, merge locale prima del push su `origin/main`. CI Windows/Linux/macOS verde.

Intervento aggiuntivo richiesto dall'utente dopo la chiusura dello Step 0. Il 16 ottobre l'utente ha approvato esplicitamente di anticipare le sole protezioni necessarie alla copia completa dal picker; reset, backup ordinari e restante Step 1 restano separati.

## Modifiche

- **Settings > Browse for an inventory folder...** apre il selettore nativo iOS per scegliere una cartella in File/iCloud Drive. Usa `public.folder` in modalita Open, preservando la directory scelta e il suo bookmark. Dopo la scelta: **Open this folder**, **Copy current inventory here**, **Cancel**.
- **Open** apre l'inventario gia presente, o uno vuoto se la cartella e vuota. **Copy** richiede conferma con sorgente/destinazione e copia tutti i file, inclusi foto, tipi, backups, trash, exports e file aggiuntivi; conserva l'originale e usa la copia solo dopo verifica. **Cancel** mantiene la posizione precedente. Non aggiunge automaticamente `StuffData` e non unisce inventari.
- **Enter an inventory folder path...** apre un campo con il percorso corrente precompilato: alternativa per aprire una cartella esistente e accessibile, senza copiarla. **Use this app's StuffData folder** / **Use app folder (iCloud Drive)** e **Use Pythonista's iCloud folder** sono le scorciatoie a destinazione fissa. Etichette, suggerimenti e conferma della loro vecchia copia ne spiegano il contenuto parziale.
- **How to move your inventory...** apre una nuova guida condivisa con differenze tra pulsanti, significato di Open/Copy/Cancel e procedura di trasferimento completo con conservazione dell'originale.
- Il percorso viene memorizzato per gli avvii successivi. Per la selezione nativa, le impostazioni locali conservano anche il bookmark iOS. Un solo accesso resta attivo per la cartella corrente; annullamenti ed errori rilasciano il candidato e conservano l'accesso precedente. Un percorso manuale interno alla cartella autorizzata ne conserva il permesso; una destinazione estranea lo rimuove.
- All'avvio il bookmark viene risolto prima che Store tocchi i file. Un riferimento obsoleto o un percorso spostato viene aggiornato solo dopo apertura e controlli riusciti. Se il permesso non e recuperabile, viene proposto di scegliere di nuovo la cartella; annullare termina l'avvio senza modificare impostazioni o creare un inventario sostitutivo. `--data` e `STUFFAPP_DATA` mantengono la precedenza.
- Settings mostra la cartella personalizzata attiva e mantiene il riconoscimento iCloud e le scorciatoie precedenti.
- Errori di percorso, permessi, apertura dell'inventario, avvio e lettura/salvataggio delle impostazioni mantengono attivi store, filtri e impostazioni precedenti. La cartella precedente puo essere scomparsa: non impedisce di selezionarne una nuova accessibile.
- `stuffapp/data_location.py` separa validazione e copia dalla UI, usando soltanto la libreria standard. `copy_inventory` esige una destinazione esistente e completamente vuota, inclusi file nascosti o cartelle vuote; rifiuta sorgente uguale/annidata, alias equivalenti, link simbolici, reparse point Windows e file speciali. Include anche directory vuote e file extra.
- La copia prepara i file dentro una directory temporanea della destinazione autorizzata, senza richiedere accesso al suo genitore o sostituire la directory selezionata. Confronta nomi/directory e SHA-256 di sorgente, staging e destinazione, rilevando cambiamenti della sorgente. La pubblicazione crea file in modo esclusivo, senza sovrascrivere collisioni. La pulizia rimuove solo elementi creati dall'operazione con identita ancora corrispondente; non cancella ricorsivamente contenuti estranei.
- Se apertura, controlli o salvataggio falliscono dopo una copia verificata, la copia resta disponibile e un errore ne indica il percorso; store, filtri, impostazioni e accesso precedenti restano attivi. Un blocco rientrante protegge l'intero flusso dal primo dialogo all'attivazione, impedendo cambi cartella/reset concorrenti; non modifica la logica di reset.
- `stuffapp/ios_folders.py` isola picker, delegate, accesso e bookmark. Le dipendenze native sono importate solo quando necessarie; Windows resta compatibile senza `objc_util`. Presentazione e chiusura del picker avvengono sul thread principale; l'attesa rimane sul thread di lavoro di Pythonista. Gestita anche l'interruzione dell'attesa.
- `stuffapp/config.py` aggiunge una lettura rigorosa opzionale per la nuova selezione: non sovrascrive impostazioni esistenti illeggibili o non valide. Il file mancante al primo utilizzo resta ammesso; i chiamanti preesistenti conservano la lettura tollerante.
- `stuffapp/touch.py` prepara lo store e ne esegue l'avvio prima di salvare e attivare la scelta. Le vecchie scorciatoie mantengono la copia parziale preesistente; il picker usa il nuovo servizio completo. Nessuna modifica al vecchio `config.copy_data` o alle copie Windows/console.
- `stuffapp/app.py` applica lo stesso ordine nel recupero all'avvio. I messaggi del controllo preliminare vengono consumati una sola volta dalla UI, evitando di ripetere riparazioni, backup o pulizie.
- Versione centrale `0.3.5`; Help, README e istruzioni Pythonista aggiornati. Schema dati e flusso Windows invariati. `AGENTS.md` memorizza la preferenza dell'utente: discutere piani/opzioni e attendere approvazione prima di implementare.

Il contratto nativo segue la [guida Apple all'accesso alle directory](https://developer.apple.com/documentation/uikit/providing-access-to-directories) e il bridge della [documentazione Pythonista objc_util](https://omz-software.com/pythonista/docs-3.4/py3/ios/objc_util.html). `dialogs.pick_document` importa un documento in una posizione temporanea, secondo la [documentazione Pythonista dialogs](https://omz-software.com/pythonista/docs-3.4/py3/ios/dialogs.html): per questo non viene usato per la cartella dati. I test con sostituti delle API non dimostrano il comportamento reale di iOS.

## Verifiche

| Controllo | Risultato |
|---|---|
| Test iniziali del nuovo comando sulla versione senza funzione | Fallimenti attesi: azione Settings assente |
| Regressioni e percorsi di errore | Verificati cartella precedente scomparsa, impostazioni illeggibili/non valide, bookmark malformati, annullamento/interruzione, refresh e recupero, guasti Store/startup/salvataggio senza perdere la scelta precedente |
| Test mirati finali `python -m unittest tests.test_touch tests.test_inventory_copy tests.test_ios_folders -v` | **71 passati**; 21 nuovi casi rispetto alla `0.3.4`, 66 rispetto alla base `0.3.2` |
| Suite completa `python -m unittest discover -s tests -t . -v`, tramite lo script locale di evidenza | **241 eseguiti: 240 passati, 1 fallimento ambientale launcher, 0 errori, 0 skip**, 39,732 s |
| Test launcher fallito, ripetuto isolatamente fuori dal sandbox | **1 passato**, 0,464 s; stessi sorgenti, nessuna modifica al launcher o alle impostazioni di sistema |
| Esito complessivo | **241 casi distinti verificati con successo** tra suite completa e singolo controllo launcher fuori sandbox; nessuna ripetizione dei 240 gia passati |
| Sintassi di main.py e stuffapp | 19 file compilati con l'interprete locale e analizzati anche con grammatica Python 3.8 |
| Dati/impostazioni esistenti prima e dopo la suite | **13 file invariati**, fingerprint uguale |
| Revisione indipendente in sola lettura | Rilievi corretti e confermati risolti; nessun rilievo residuo sul codice |
| `git diff --check` | Uscita 0 |
| Controllo prima del commit | 19 sorgenti applicativi e tre ZIP ancora identici alle evidenze verificate; nessuna nuova suite |
| Merge locale | Fast-forward allo stesso commit `5beb879` del branch; identita verificata e working tree pulito, nessuna suite duplicata |
| [CI del commit applicativo](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38870387745) | **Windows: 241 passati**; Linux/macOS: 240 passati e 1 skip launcher Windows per piattaforma. Build e console smoke verdi su tutti; launcher e GUI Windows verdi |

Ambiente: Windows 10 build 19045, CPython 3.14.7 AMD64. I test usano il vero controller Pythonista con sostituti delle API native/dialoghi, store reali e directory temporanee; i guasti sono simulati ai confini delle risorse interessate. Oltre alle verifiche bookmark/percorso della `0.3.4`, coprono copia completa, destinazioni apparentemente vuote con immagini/tipi/backup/trash/export, sorgente cambiata, disco pieno, interruzione, file estranei nello staging e nella destinazione, alias/link e concorrenza durante copia o conferma. I test dei link sono stati eseguiti sul PC Windows, senza skip.

Problema incontrato: `tests.test_smoke_release.ReleaseSmokeTests.test_launcher_preserves_python_failure_and_disables_pause_for_ci` fallisce nel sandbox perche `where py`/`where python` non trovano gli interpreti installati, pur avviabili da PowerShell. Riprodotto anche isolatamente; il comando identico fuori dal sandbox passa e preserva il codice di uscita atteso `7`. Non e stato corretto codice estraneo alla funzione. Il fallimento originale rimane nel log e nell'evidenza della suite; il risultato isolato e registrato separatamente, senza presentare la suite originale come interamente verde.

Evidenze locali, ignorate da Git e non distribuite nell'app:

- [Log completo dei 241 test, incluso il fallimento ambientale](../../dist/pythonista-data-folder-tests.log).
- [Ambiente, comandi, risultati e fingerprint](../../dist/pythonista-data-folder-verification.json).
- [Esito complessivo e comando/risultato del launcher fuori sandbox](../../dist/pythonista-data-folder-overall-verification.json).
- [Esito CI e controlli dei job](../../dist/pythonista-data-folder-ci.json); [log CI con conteggi test](../../dist/pythonista-data-folder-ci.log).
- [Script di raccolta delle evidenze](../../dist/verify_pythonista_data_folder.py).

Fingerprint prima/dopo: `2de3261862c3ace884bf48cd16fb36f28f81b853a2cbdd7bda55739a401bbef8`. Include l'inventario principale e i dati/impostazioni delle estrazioni sotto `dist/`. Nessun inventario dell'utente e stato aperto dall'app per i test; i file esistenti sono stati letti soltanto per calcolarne gli hash.

La suite completa `0.3.5` e stata eseguita una sola volta sul codice finale, dopo i test mirati e la revisione; il solo launcher ha richiesto diagnosi e verifica isolata fuori sandbox. La precedente `0.3.4` aveva superato 220 test, la `0.3.3` 193; entrambe sono state collaudate su iPhone dall'utente per le rispettive funzioni. [Evidenza storica `0.3.4`](../../dist/pythonista-data-folder-0.3.4-verification.json). Successivi aggiornamenti a rapporto, piano e pacchetti non richiedono una nuova suite, secondo `AGENTS.md`.

## Build

Comando: `python tools/make_release.py --platform all`, uscita 0. Pacchetti **di test** `0.3.5`, distinti dalle versioni precedenti, che restano disponibili, incluse `0.3.3` e `0.3.4` collaudate.

| Pacchetto | Verifica |
|---|---|
| [Pythonista ZIP](../../dist/YetAnotherStuffApp-0.3.5-pythonista.zip) | Inventario/hash e corrispondenza ai sorgenti OK; include entrambi i nuovi moduli e PYTHONISTA-SETUP |
| [Windows ZIP](../../dist/YetAnotherStuffApp-0.3.5-windows.zip) | Inventario/hash e corrispondenza ai sorgenti OK |
| [Sorgente ZIP](../../dist/YetAnotherStuffApp-0.3.5-source.zip) | Inventario/hash e corrispondenza ai sorgenti OK |

Controllo: `python dist/check_pythonista_data_folder_packages.py`, uscita 0. Verificati struttura, file richiesti, inventario SHA-256, digest complessivo, presenza di `data_location.py`/`ios_folders.py` e identita dei contenuti con i sorgenti correnti, normalizzando CRLF del batch come previsto dal builder. Nessuna ulteriore suite o esecuzione dell'app per i soli pacchetti.

[Risultati della verifica dei pacchetti](../../dist/pythonista-data-folder-packages.json); [SHA256SUMS](../../dist/SHA256SUMS.txt).

```text
089866da521171a7eaa2412f6da5b9a4a61abf6cb1e9673af13947a21de4edc6  YetAnotherStuffApp-0.3.5-pythonista.zip
8b7e2ab3c99344c7d979ab146630321ad21f2da0fb1f9ad161f02b8fc4450175  YetAnotherStuffApp-0.3.5-windows.zip
9fa840889a5f58026a1417bcebbd3a66f9d073548cbf5fd8a936a13ddda65168  YetAnotherStuffApp-0.3.5-source.zip
```

I manifest dei pacchetti collaudati riportano il commit base `6e64bd3`, precedente al commit applicativo; inventari/hash identificano i contenuti modificati distribuiti. I tre ZIP collaudati restano invariati. Gli ZIP escludono dati personali, impostazioni, test, strumenti, cache e report.

## Collaudo iPhone

La `0.3.3` con percorso manuale e il picker della `0.3.4` sono stati confermati funzionanti dall'utente. Per il nuovo collaudo `0.3.5`, usare una nuova estrazione e copie di inventari di prova. Il picker concede l'accesso alla cartella; per l'alternativa manuale resta possibile collegarla prima tramite **External Files > Open... > Folder...**. Le copie di app/impostazioni devono restare separate per dispositivo, dato che percorsi e autorizzazioni Windows e iOS sono diversi.

- [x] Collaudo complessivo `0.3.5`: **Pythonista OK**, confermato dall'utente con Go alla chiusura. I casi seguenti restano una traccia dettagliata: non sono stati rendicontati singolarmente dall'utente.
- [ ] Avvio senza errori; About mostra `0.3.5`. Etichette e suggerimenti leggibili su iPhone, comprese le due scorciatoie a destinazione fissa.
- [ ] **How to move your inventory...** apre la guida con differenze tra pulsanti, copia completa/parziale e procedura di trasferimento.
- [ ] **Browse for an inventory folder...** apre File: navigazione, scelta singola e menu **Open / Copy / Cancel** comprensibile.
- [ ] Scegliere una copia iCloud di StuffData e **Open**: inventario corretto, percorso esatto e nessuna copia automatica.
- [ ] Preparare una destinazione locale di prova completamente vuota; scegliere **Copy**. Conferma con fonte/destinazione, attivazione della copia, foto/tipi e file backups/trash/exports presenti, sorgente conservata.
- [ ] Ripetere la copia completa verso una cartella iCloud vuota; verificare inventario e accesso dopo riavvio di Pythonista.
- [ ] Provare **Copy** verso una cartella con sole foto, soli tipi o altro file: rifiuto, file preesistenti conservati, percorso corrente invariato. Rifiutare anche la sorgente stessa o una sua sottocartella.
- [ ] Annullare picker, menu azioni e conferma copia: inventario e percorso precedenti conservati.
- [ ] Chiudere e rilanciare main.py, poi terminare e riaprire Pythonista: cartella scelta ancora accessibile, dati presenti.
- [ ] Se riproducibile su una copia di prova, rendere il permesso non valido: nuovo picker all'avvio; annullamento senza inventario sostitutivo, nuova scelta con recupero dell'inventario atteso.
- [ ] **Enter an inventory folder path...** e precompilato con il percorso corrente; apre senza offrire copia.
- [ ] Inserire il percorso di una copia esistente di StuffData: conferma, inventario corretto, percorso esatto e indicazione della cartella selezionata.
- [ ] Chiudere e riaprire l'app: percorso e inventario scelti restano attivi.
- [ ] Annullare il campo e la conferma: scelta precedente conservata. Inserire lo stesso percorso: nessun cambio.
- [ ] Inserire un percorso inesistente o non accessibile: errore comprensibile e scelta precedente conservata.
- [ ] Scegliere una cartella di prova vuota e **Open**: inventario vuoto. Tornare alla cartella precedente e ritrovare i dati.

## Limiti e attivita residue

- Collaudo complessivo iPhone `0.3.5` confermato dall'utente. Non vengono dedotti esiti individuali per ogni provider, scenario di revoca/interruzione o voce della checklist non descritta separatamente. Il parsing con grammatica Python 3.8 non equivale a un test runtime Pythonista.
- La selezione nativa delle directory richiede iOS 13 o successivo. I comandi aprono una cartella esistente; non aggiungono StuffData o creano un percorso digitato inesistente. La disponibilita dei provider esterni dipende da iOS e dai relativi permessi.
- Aprire la destinazione applica i controlli ordinari gia presenti nell'app, incluse eventuali riparazioni, backup e pulizia del cestino. La conservazione dello store/impostazioni precedenti in caso di errore non e una transazione su tutti i file della destinazione.
- La verifica riguarda nomi, directory e byte; non promette identita di permessi/timestamp/metadati filesystem. La preparazione e la pubblicazione richiedono spazio per due copie aggiuntive nella destinazione; non e un'operazione atomica multi-file per altri programmi che guardano la cartella durante la copia.
- Errori di permessi, modifiche esterne o terminazione forzata del processo possono lasciare una destinazione parziale/staging da esaminare. La sorgente non viene cancellata e le impostazioni non vengono aggiornate prima della verifica. Non editare le cartelle da altre app durante l'operazione.
- Nessuna sincronizzazione cloud aggiunta. La nuova protezione riguarda soltanto la copia completa dal picker: i limiti della vecchia `config.copy_data` (Windows/console/scorciatoie) e il reset/backup restano per lo Step 1 separato.
- CI remota `0.3.5` completata con successo sul commit applicativo `5beb879`: [workflow 38870387745](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38870387745). Il launcher Windows passa anche nel runner CI ordinario; il fallimento locale resta documentato come limite del sandbox. Job di pubblicazione release saltato.

## Integrazione

L'utente ha confermato **«Pythonista OK. Go on.»**. Creato il commit applicativo `5beb87924eebba6e5880c8699e3f960fe77fb190` su `feature/pythonista-data-folder`; merge fast-forward nel `main` locale e successivo push su `origin/main` eseguiti in quest'ordine. La CI del commit e verde. Il branch locale viene conservato. Nessun worktree, PR, tag o release.

La registrazione finale degli esiti usa un commit solo documentale con `[skip ci]`, sempre sul branch e poi integrato localmente prima del push. Nessuna suite ripetuta per questa documentazione o per il fast-forward dello stesso commit: controllo di differenze, identita e working tree pulito. Gli ZIP collaudati non vengono rigenerati. Anticipata soltanto la copia completa dal picker approvata con opzione 2; il resto dello Step 1 resta separato.
