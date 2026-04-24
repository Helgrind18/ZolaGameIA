# Zola AI Player - Implementazione e Strategia

Questo repository contiene un'implementazione avanzata di un agente intelligente per il gioco da tavolo **Zola**, progettato per competere ottimizzando il tempo di calcolo e sfruttando al massimo le regole del gioco.

## Panoramica del Gioco: Zola
Zola è un gioco da tavolo per due giocatori (Rosso e Blu) su una scacchiera 8x8. Il gioco si basa sul concetto di **distanza dal centro**, con la scacchiera divisa in "livelli" (dal livello 1, il più centrale, al livello 6, il più esterno). 

* **Mossa Non Catturante:** Un pezzo si sposta di una casella (come il Re degli scacchi) verso uno spazio vuoto che si trova a un livello *più distante* dal centro.
* **Mossa Catturante:** Un pezzo si sposta in linea retta di quante caselle vuole (come la Regina), scavalcando caselle vuote per catturare un pezzo avversario, purché la destinazione si trovi a un livello *uguale o più vicino* al centro.

Vince chi cattura tutti i pezzi dell'avversario.

## Architettura del Bot
Il bot utilizza l'algoritmo **Minimax con Potatura Alpha-Beta** ed **Iterative Deepening** per massimizzare la profondità di ricerca entro il limite di tempo imposto di 3 secondi (impostato a un sicuro 2.9s).

### Componenti Chiave
1.  **Iterative Deepening:** L'algoritmo non ha una profondità fissa. Cerca la mossa migliore a profondità 1, poi a 2, poi a 3, ecc., finché non scatta il limite di 2.9 secondi, restituendo l'ultima mossa completata.
2.  **Move Ordering:** Le mosse di cattura vengono esplorate per prime, ottimizzando esponenzialmente i tagli (pruning) dell'Alpha-Beta.
3.  **Memoizzazione (EVAL_CACHE):** Gli stati già calcolati vengono salvati in memoria. Se l'algoritmo incontra la stessa scacchiera attraverso un ramo diverso, recupera istantaneamente il punteggio pre-calcolato.

---

## La Strategia "Cecchino" (Bot Base / Rosso)

La funzione euristica valuta la scacchiera secondo tre parametri principali:

1.  **Materiale (Peso: 1000):** La conservazione dei propri pezzi e la cattura di quelli avversari è la priorità assoluta. Il bot non sacrificherà mai un pezzo per un vantaggio posizionale.
2.  **Controllo dei Bordi (Peso: 10 per livello):** *Questa è l'intuizione chiave.* Poiché le catture devono muoversi verso il centro, i pezzi al centro sono bersagli vulnerabili. I pezzi sui bordi (livelli alti) rappresentano il "terreno alto": possono attaccare verso l'interno senza poter essere attaccati dall'interno. Il bot premia il posizionamento sui livelli più esterni.
3.  **Mobilità (Peso: 5):** A parità di materiale, si preferiscono posizioni che offrono più mosse legali rispetto all'avversario.

**Comportamento:** Giocando come Rosso (il primo giocatore), il bot capitalizza il vantaggio dell'iniziativa, giocando in modo matematico, deterministico e spietato.

---

## La Strategia Ibrida (L'Arma 1 / Blu)

In un gioco a informazione perfetta con setup fisso come Zola, il primo giocatore (Rosso) ha un vantaggio matematico, essendo obbligato a iniziare con una cattura a causa della scacchiera piena. Se si fanno scontrare due intelligenze artificiali identiche, deterministiche e perfette, il Rosso vincerà quasi sempre.

Per contrastare questo svantaggio quando il bot gioca come **Blu** (secondo giocatore), è stata introdotta un'asimmetria strategica: il **Fattore Caos**.

### Come funziona il Fattore Caos
Quando l'agente gioca come Blu, la funzione euristica aggiunge un micro-rumore casuale (tra 0.0 e 0.9) al punteggio di ogni scacchiera valutata. 

* Questo valore è troppo basso per far compiere al bot mosse stupide (es. sacrificare un pezzo, che vale 1000 punti).
* Tuttavia, interviene come *tie-breaker* infallibile: se il bot trova due mosse con lo stesso identico valore strategico, sceglierà in modo creativo.

**Risultato:** Il bot Blu diventa imprevedibile. Rompe le simmetrie e i rami "standard" dell'albero delle mosse, costringendo il bot Rosso avversario a valutare scenari nuovi in cui potrebbe esaurire il tempo o commettere un errore di profondità, riequilibrando le sorti della partita.
