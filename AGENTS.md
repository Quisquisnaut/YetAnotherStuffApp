# Istruzioni per gli agenti

- Prima di implementare modifiche, discutere il piano con l'utente: obiettivo, ambito, conseguenze e verifiche previste. Quando esistono alternative utili, presentare opzioni chiare con relativi vantaggi e limiti, indicando quella consigliata. Attendere l'approvazione esplicita del piano o dell'opzione scelta prima di procedere all'implementazione; richieste di spiegazione o preferenze di workflow non costituiscono approvazione di una proposta in sospeso.
- Dopo l'approvazione del piano, procedere con le azioni comprese nell'ambito autorizzato senza chiedere conferma per ogni comando. Non richiedere approvazione per comandi di sola lettura. Discutere e far approvare eventuali ampliamenti dell'ambito prima di implementarli.
- Mantenere coerenti funzionalita, terminologia e comportamento tra Pythonista, GUI Windows e console, per quanto possibile. Riutilizzare i servizi condivisi e documentare le sole differenze necessarie alla piattaforma.
- Evitare suite locali ridondanti. Dopo un merge fast-forward dello stesso commit gia verificato, controllare identita del commit e stato pulito senza rieseguire i test.
- Non ripetere i test per modifiche che riguardano soltanto documentazione o pacchetti di distribuzione. Eseguire solo gli eventuali controlli di coerenza e integrita pertinenti.
- Per commit esclusivamente documentali o relativi ai pacchetti di distribuzione, evitare di rilanciare la CI, usando quando appropriato `[skip ci]`. Non saltare verifiche necessarie per modifiche funzionali, conflitti risolti o problemi ancora aperti.
