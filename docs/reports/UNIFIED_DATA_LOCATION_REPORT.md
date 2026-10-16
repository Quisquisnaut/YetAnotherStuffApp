# Gestione cartella dati unificata — 0.3.6

**Data:** 16 ottobre 2026. **Stato:** **INTEGRATO** dopo Go; commit applicativo `dc74e8693ede1de105f0492605e739de318bd972`, merge fast-forward nel `main` locale e successivo push completati. **CI Windows/Linux/macOS verde**.

Branch locale `feature/unified-data-location`, senza worktree. Base verificata: `ead832e25df1028d0c636339b55683ce25c56e31` (0.3.5). L'utente ha autorizzato l'integrazione con «Go on»; nessun PR, tag o release creato.

## Ambito approvato

Seguito separato dello Step 0 e dell'intervento Pythonista, dopo «Unify Both and keep consistent»: unificare le azioni di gestione cartella tra Pythonista, GUI Windows e console. Il resto dello Step 1 rimane separato; nessuna modifica al formato dati, al motore di reset o al ciclo dei backup.

Regola generale salvata in `AGENTS.md`: mantenere funzionalita, terminologia e comportamento coerenti fra le tre interfacce, riutilizzando servizi condivisi e documentando le differenze necessarie alla piattaforma.

## Modifiche

- Etichette richieste: **Use default folder (StuffData)** e **Reset current data folder**. Il percorso predefinito rimane accanto al progetto, anche in iCloud Drive; Pythonista mostra il percorso del preset.
- Browse, inserimento percorso e preset offrono le stesse azioni **Open this folder / Copy complete folder here / Cancel**. Windows e console ricevono anche inserimento manuale e guida dedicata. Il preset iCloud dedicato rimane disponibile nell'interfaccia Pythonista quando rilevato.
- `stuffapp/data_location.py` centralizza etichette, conferme, validazione e preparazione del cambio cartella. Tutte le copie da Settings usano la copia completa gia verificata nella 0.3.5: file extra, cartelle vuote, foto, tipi, backup, cestino ed esportazioni; verifica SHA-256, nessuna fusione, nessuna cancellazione dell'originale. Destinazione completamente vuota e separata dalla sorgente; collegamenti e file speciali rifiutati.
- Impostazioni lette rigorosamente prima delle scritture; cartella candidata aperta e preparata prima di salvare la nuova scelta e sostituire lo Store attivo. Errori di copia o attivazione mantengono la scelta precedente. Una copia verificata resta disponibile se l'attivazione fallisce; gli errori identificano la destinazione e gli eventuali residui parziali.
- I soli preset possono creare una cartella mancante, dopo conferma. I controlli sui percorsi annidati precedono anche questa creazione. Browse e percorso manuale richiedono cartelle esistenti; annullare non crea cartelle.
- Windows/Pythonista conservano i selettori nativi; console usa un browser testuale. Pythonista conserva la serializzazione dei cambi cartella e i bookmark; anche la console eseguita in Pythonista conserva un permesso valido per una sottocartella e rilascia quello precedente solo dopo una sostituzione riuscita.
- Eliminata la copia parziale dalle azioni di Settings. `config.copy_data` rimane soltanto come API legacy, documentata come parziale. Guida, README, setup e conferme distinguono copia completa, backup ordinario parziale ed eventuale copia incompleta dopo un errore. Versione centrale aggiornata a `0.3.6`.

## Verifiche

| Verifica | Risultato |
| --- | --- |
| `python -m unittest discover -s tests -t . -v` | **258 passati, 0 fallimenti, 0 skip**, 40,146 s; suite completa eseguita una volta sullo stato finale |
| Nuovi test | **17** oltre i 241 della 0.3.5: selettori Windows/console, copia completa con backup reale e cestino recente, annullamento, errori, preset, bookmark e nuove azioni Pythonista |
| Probe con veri dialoghi Tk | Settings → Browse → copia completa, Default → Cancel, guida condivisa e sorgente invariata: **passati**; selezione nativa cartella simulata |
| Compatibilita sintattica Python 3.8 e compilazione | **19 file applicativi** verificati; non equivale a esecuzione su interprete Python 3.8 o su iOS |
| Revisione indipendente, inclusa verifica successiva | Nessun difetto critico/importante residuo; sola lettura, nessuna suite duplicata dal revisore |
| Inventari/impostazioni esistenti | **14 file invariati** prima/dopo la suite, SHA-256 aggregato `f9feaa99ebbc46ec7a79ee643f3ea731c3ec83f6d67d20691b686401d956b2fd` |
| Archivi | Manifest, hash e contenuti confrontati con i sorgenti attuali; nessun inventario, impostazione dispositivo o file di test incluso |
| CI sul commit applicativo | Windows: **258 passati**; Linux/macOS: **257 passati e 1 skip** Windows-only ciascuno; build e smoke console verdi, launcher/GUI Windows verdi; pubblicazione release saltata |

Ambiente locale: Windows 10, Python 3.14.7. Evidenze in `dist/unified-data-location-tests.log`, `dist/unified-data-location-verification.json`, `dist/unified-data-location-gui.json` e `dist/unified-data-location-packages.json`. I 19 hash dei sorgenti fissano lo stato verificato prima del commit.

Il primo probe GUI nel sandbox non trovava il runtime Tcl. La stessa verifica e passata fuori sandbox senza modifiche al prodotto. La suite completa e stata eseguita direttamente fuori sandbox per usare Python e launcher Windows installati, evitando il limite del launcher gia diagnosticato nella 0.3.5. Nessuna suite ripetuta per le successive sole attivita documentali o di packaging.

[Workflow 38881741874](https://github.com/Quisquisnaut/YetAnotherStuffApp/actions/runs/38881741874) completato con successo sul commit applicativo esatto. Evidenze aggiuntive: `dist/unified-data-location-ci.json`, `dist/unified-data-location-ci.log` e `dist/unified-data-location-ci-watch.log`. Nessun rilancio manuale della CI.

## Build generate

Tutti gli ZIP in `dist/`, versione **0.3.6**; le build precedenti sono conservate. I manifest identificano il commit base e i contenuti applicativi non ancora committati tramite hash.

| Archivio | SHA-256 |
| --- | --- |
| `YetAnotherStuffApp-0.3.6-windows.zip` | `7689d453cbc82ad67070f4c7805aa8def6ce2cf04d34e9f4a94533adee3c2f28` |
| `YetAnotherStuffApp-0.3.6-pythonista.zip` | `b3839cd09ee62df1ddfc33040805bb3776309db5417d377dd4f0f0372da9d7aa` |
| `YetAnotherStuffApp-0.3.6-source.zip` | `1bbb2738a3d50f12152c3bbb1752272459ecdb2a2ad8189e9084d395f0525ba9` |

Comandi eseguiti: `python tools/make_release.py --platform all` e controllo manifest/confronto byte tramite `dist/check_unified_data_location_packages.py`. I tre ZIP collaudabili sono rimasti identici dopo il Go, il commit e il merge; non sono stati rigenerati. La CI ha prodotto separatamente i propri artefatti sul commit integrato. Nessuna modifica alla pipeline CI.

## Limiti e attivita residue

- Go all'integrazione ricevuto; la checklist visiva non e stata confermata voce per voce e rimane disponibile sotto. I test sostituiscono soltanto i dialoghi e i confini nativi: non attestano rendering, provider iCloud o persistenza reale dei permessi della nuova build su iOS.
- La copia e verificata prima dell'apertura; successivamente restano attivi i normali controlli, riparazioni, backup/retention e scadenza del cestino. Questa manutenzione puo modificare la copia appena aperta, come gia nella 0.3.5 e come indicato nella conferma/guida. L'originale non viene cancellato.
- Copia e verifica riguardano nomi e contenuti, non ACL o altri metadati del filesystem. Servono spazio per copia temporanea e finale e assenza di modifiche concorrenti. Dopo perdita di permessi/interruzione possono restare file parziali: l'errore lo segnala e occorre ispezionare la destinazione.
- Se la cartella corrente scompare, Browse console segnala l'errore; inserire un percorso esistente permette di recuperare. Per cambiare unita Windows si puo usare il percorso manuale. Nessuna sincronizzazione cloud o risoluzione dei conflitti aggiunta.
- Il reset e i backup mantengono il comportamento esistente: il backup e parziale, senza cestino, esportazioni e file extra. Le ulteriori protezioni dello Step 1 restano da affrontare separatamente.
- Workflow eseguito sul commit applicativo: commit sul branch, merge fast-forward del medesimo commit nel `main` locale, controllo identita/stato pulito senza nuova suite, quindi push. I 19 sorgenti applicativi coincidono ancora con le evidenze locali verificate. Chiusura documentale separata con `[skip ci]`, seguendo lo stesso ordine commit/merge locale/push senza ripetere test o build.

## Checklist visiva — usare inventari di prova

- [ ] About indica 0.3.6 su Pythonista, Windows GUI e console; Settings mostra le due etichette richieste e il percorso corrente.
- [ ] Browse, percorso e preset mostrano Open / Copy complete folder / Cancel con le stesse spiegazioni; iCloud dedicato presente solo dove disponibile.
- [ ] Open usa un inventario diverso senza importare dati dall'originale; annullare selettore, menu o conferma mantiene scelta e dati.
- [ ] Copy verso cartella separata e vuota conserva foto, tipi, backup, cestino recente, esportazioni e file extra; controllare destinazione e originale.
- [ ] Destinazione non vuota rifiutata senza alterarne i file; cartella annidata rifiutata. Annullare un preset mancante non crea cartelle.
- [ ] Default torna a StuffData accanto al progetto; un progetto in iCloud mantiene quel percorso. Nessuno StuffData aggiunto sotto una cartella selezionata manualmente.
- [ ] Riavvio conserva la scelta; Pythonista riapre una cartella scelta da Files con il relativo permesso. Nessun inventario vuoto sostitutivo se l'accesso non e disponibile.
- [ ] Console: navigare cartella/parent, Use this folder e annullamento; provare anche percorso manuale con spazi/unita diversa.
- [ ] Guida condivisa leggibile; conferma reset esplicita sui limiti del backup parziale. Verificare annullamento senza resettare dati reali.

Il rapporto chiuso `STEP_00_REPORT.md` e il rapporto della 0.3.5 rimangono invariati.
