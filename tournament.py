import importlib
import time
import csv
import random
import concurrent.futures

# Importiamo solo la logica di gioco dal tuo file originale, ignorando la GUI
from ZolaGameS import ZolaGame

# ==========================================
# CONFIGURAZIONE TORNEO
# ==========================================
FILE_STRATEGIA_ROSSO = "playerExampleAlphaImplGiuseppe"  # Nome del file senza il .py
FILE_STRATEGIA_BLU = "playerExampleAlphaImplGiuseppe"  # Nome del file senza il  .py
NUMERO_PARTITE = 20
TIMEOUT_MOSSA = 3
FILE_RISULTATI = "ciao.csv"


# ==========================================

def load_strategy(module_name):
    """Carica dinamicamente il modulo Python contenente la strategia."""
    try:
        module = importlib.import_module(module_name)
        return module.playerStrategy
    except ImportError:
        print(f"ERRORE: Impossibile trovare il file '{module_name}.py'. Assicurati che sia nella stessa cartella.")
        exit(1)


def play_headless_game(strategy_red, strategy_blue, game_index):
    """Gioca una singola partita senza interfaccia grafica e restituisce il vincitore."""
    game = ZolaGame(size=8, first_player="Red")
    state = game.initial

    strategies = {
        "Red": strategy_red,
        "Blue": strategy_blue
    }

    # Usiamo un executor per gestire i timeout esattamente come faceva la GUI
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        while not game.is_terminal(state):
            current_player = state.to_move
            legal_moves = game.actions(state)

            # Se non ci sono mosse, il giocatore salta il turno
            if not legal_moves:
                state = game.pass_turn(state)
                continue

            strategy = strategies[current_player]

            # Avviamo il calcolo della mossa
            future = executor.submit(strategy, game, state, TIMEOUT_MOSSA)
            try:
                move = future.result(timeout=TIMEOUT_MOSSA)
            except concurrent.futures.TimeoutError:
                future.cancel()
                move = None
            except Exception as e:
                print(f"Errore nell'IA {current_player}: {e}")
                move = None

            # Controllo validità e fallback
            if move not in legal_moves:
                move = random.choice(legal_moves)

            # Applichiamo la mossa
            state = game.result(state, move)

    # La partita è finita
    winner = game.winner(state)
    print(f"Partita {game_index} terminata. Vincitore: {winner}")
    return winner


def main():
    print(f"Inizio Torneo: {FILE_STRATEGIA_ROSSO} (Rosso) VS {FILE_STRATEGIA_BLU} (Blu)")
    print(f"Numero di partite: {NUMERO_PARTITE}")
    print("-" * 40)

    strat_red = load_strategy(FILE_STRATEGIA_ROSSO)
    strat_blue = load_strategy(FILE_STRATEGIA_BLU)

    stats = {
        "Red": 0,
        "Blue": 0,
        "Draw": 0  # In Zola i pareggi non dovrebbero esistere, ma lo teniamo per sicurezza
    }

    start_time = time.time()

    for i in range(1, NUMERO_PARTITE + 1):
        winner = play_headless_game(strat_red, strat_blue, i)
        if winner == "Red":
            stats["Red"] += 1
        elif winner == "Blue":
            stats["Blue"] += 1
        else:
            stats["Draw"] += 1

    elapsed_time = time.time() - start_time

    # Stampa risultati a schermo
    print("-" * 40)
    print("TORNEO CONCLUSO")
    print(f"Tempo totale: {elapsed_time:.2f} secondi")
    print(f"Vittorie Rosso ({FILE_STRATEGIA_ROSSO}): {stats['Red']}")
    print(f"Vittorie Blu ({FILE_STRATEGIA_BLU}): {stats['Blue']}")
    print(f"Pareggi: {stats['Draw']}")

    # Salvataggio nel CSV
    with open(FILE_RISULTATI, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Scrive l'intestazione se il file è vuoto
        if file.tell() == 0:
            writer.writerow(
                ["Strategia Rosso", "Strategia Blu", "Partite Giocate", "Vittorie Rosso", "Vittorie Blu", "Pareggi",
                 "Tempo Totale (s)"])

        writer.writerow([
            FILE_STRATEGIA_ROSSO,
            FILE_STRATEGIA_BLU,
            NUMERO_PARTITE,
            stats["Red"],
            stats["Blue"],
            stats["Draw"],
            round(elapsed_time, 2)
        ])

    print(f"\nRisultati salvati in '{FILE_RISULTATI}'.")


if __name__ == "__main__":
    main()