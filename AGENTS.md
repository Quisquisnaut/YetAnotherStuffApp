# Istruzioni per gli agenti

- Evitare suite locali ridondanti. Dopo un merge fast-forward dello stesso commit gia verificato, controllare identita del commit e stato pulito senza rieseguire i test.
- Non ripetere i test per modifiche che riguardano soltanto documentazione o pacchetti di distribuzione. Eseguire solo gli eventuali controlli di coerenza e integrita pertinenti.
- Per commit esclusivamente documentali o relativi ai pacchetti di distribuzione, evitare di rilanciare la CI, usando quando appropriato `[skip ci]`. Non saltare verifiche necessarie per modifiche funzionali, conflitti risolti o problemi ancora aperti.
