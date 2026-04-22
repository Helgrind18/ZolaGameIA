import importlib
import time
import csv
import random
import concurrent.futures

# Importiamo solo la logica di gioco dal tuo file originale, ignorando la GUI
from ZolaGameS import ZolaGame
from tournament import NUMERO_PARTITE

# ==========================================
# CONFIGURAZIONE TORNEO
# ==========================================
FILE_STRATEGIA_ROSSO = "playerStrategyImplPasquale"  # Nome del file senza il .py
FILE_STRATEGIA_BLU = "playerExampleAlphaImplGiuseppe"  # Nome del file senza il .py
NUMERO_PARTITE = 15
TIMEOUT_MOSSA = 2
FILE_RISULTATI = "statistiche_"+FILE_STRATEGIA_ROSSO+"_"+FILE_STRATEGIA_BLU+"_NP_"+str(NUMERO_PARTITE)+"_TM_"+str(TIMEOUT_MOSSA)+".csv"


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
    game = ZolaGame(size=8, first_player="Red")
    state = game.initial

    strategies = {"Red": strategy_red, "Blue": strategy_blue}

    stats_partita = {
        "turni_totali": 0,
        "Red": {"timeouts": 0, "mosse_illegali": 0, "tempo_totale_mosse": 0.0, "mosse_giocate": 0},
        "Blue": {"timeouts": 0, "mosse_illegali": 0, "tempo_totale_mosse": 0.0, "mosse_giocate": 0}
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        while not game.is_terminal(state):
            current_player = state.to_move
            legal_moves = game.actions(state)

            if not legal_moves:
                state = game.pass_turn(state)
                continue

            strategy = strategies[current_player]
            start_mossa = time.time()

            future = executor.submit(strategy, game, state, TIMEOUT_MOSSA)
            try:
                move = future.result(timeout=TIMEOUT_MOSSA)
            except concurrent.futures.TimeoutError:
                future.cancel()
                move = None
                stats_partita[current_player]["timeouts"] += 1
                print(f"[{current_player}] Timeout!")
            except Exception as e:
                move = None

            tempo_impiegato = time.time() - start_mossa
            stats_partita[current_player]["tempo_totale_mosse"] += tempo_impiegato
            stats_partita[current_player]["mosse_giocate"] += 1

            if move not in legal_moves:
                stats_partita[current_player]["mosse_illegali"] += 1
                move = random.choice(legal_moves)

            state = game.result(state, move)
            stats_partita["turni_totali"] += 1

    winner = game.winner(state)

    # Ritorna non solo il vincitore, ma tutte le metriche
    return winner, stats_partita


def main():
    print(f"Inizio Torneo: {FILE_STRATEGIA_ROSSO} (Rosso) VS {FILE_STRATEGIA_BLU} (Blu)")
    print(f"Numero di partite: {NUMERO_PARTITE}")
    print("-" * 40)

    strat_red = load_strategy(FILE_STRATEGIA_ROSSO)
    strat_blue = load_strategy(FILE_STRATEGIA_BLU)

    # Statistiche standard
    stats = {
        "Red": 0,
        "Blue": 0,
        "Draw": 0
    }

    # Nuove statistiche aggregate per l'intero torneo
    agg_stats = {
        "turni_totali": 0,
        "Red_timeouts": 0,
        "Blue_timeouts": 0,
        "Red_illegali": 0,
        "Blue_illegali": 0,
        "Red_tempo_mosse": 0.0,
        "Blue_tempo_mosse": 0.0,
        "Red_mosse_totali": 0,
        "Blue_mosse_totali": 0
    }

    start_time = time.time()

    for i in range(1, NUMERO_PARTITE + 1):
        # spacchettiamo i due valori restituiti dalla nuova funzione
        winner, stats_partita = play_headless_game(strat_red, strat_blue, i)

        if winner == "Red":
            stats["Red"] += 1
        elif winner == "Blue":
            stats["Blue"] += 1
        else:
            stats["Draw"] += 1

        # Sommiamo i dati di questa partita ai totali del torneo
        agg_stats["turni_totali"] += stats_partita["turni_totali"]
        agg_stats["Red_timeouts"] += stats_partita["Red"]["timeouts"]
        agg_stats["Blue_timeouts"] += stats_partita["Blue"]["timeouts"]
        agg_stats["Red_illegali"] += stats_partita["Red"]["mosse_illegali"]
        agg_stats["Blue_illegali"] += stats_partita["Blue"]["mosse_illegali"]

        agg_stats["Red_tempo_mosse"] += stats_partita["Red"]["tempo_totale_mosse"]
        agg_stats["Blue_tempo_mosse"] += stats_partita["Blue"]["tempo_totale_mosse"]
        agg_stats["Red_mosse_totali"] += stats_partita["Red"]["mosse_giocate"]
        agg_stats["Blue_mosse_totali"] += stats_partita["Blue"]["mosse_giocate"]

    elapsed_time = time.time() - start_time

    # Calcolo delle medie
    media_turni = agg_stats["turni_totali"] / NUMERO_PARTITE if NUMERO_PARTITE > 0 else 0
    media_tempo_red = agg_stats["Red_tempo_mosse"] / agg_stats["Red_mosse_totali"] if agg_stats[
                                                                                          "Red_mosse_totali"] > 0 else 0
    media_tempo_blue = agg_stats["Blue_tempo_mosse"] / agg_stats["Blue_mosse_totali"] if agg_stats[
                                                                                             "Blue_mosse_totali"] > 0 else 0

    # Stampa risultati a schermo
    print("-" * 40)
    print("TORNEO CONCLUSO")
    print(f"Tempo totale: {elapsed_time:.2f} secondi")
    print(f"Media turni per partita: {media_turni:.1f}")
    print(
        f"Vittorie Rosso ({FILE_STRATEGIA_ROSSO}): {stats['Red']} (Timeouts: {agg_stats['Red_timeouts']} | Mosse Illegali: {agg_stats['Red_illegali']} | Tempo medio/mossa: {media_tempo_red:.3f}s)")
    print(
        f"Vittorie Blu ({FILE_STRATEGIA_BLU}): {stats['Blue']} (Timeouts: {agg_stats['Blue_timeouts']} | Mosse Illegali: {agg_stats['Blue_illegali']} | Tempo medio/mossa: {media_tempo_blue:.3f}s)")
    print(f"Pareggi: {stats['Draw']}")

    with open(FILE_RISULTATI, mode='a', newline='') as file:
        writer = csv.writer(file)

        # Scrive l'intestazione allargata se il file è vuoto
        if file.tell() == 0:
            writer.writerow([
                "Strategia Rosso", "Strategia Blu", "Partite Giocate",
                "Vittorie Rosso", "Vittorie Blu", "Pareggi", "Tempo Totale (s)",
                "Media Turni", "Timeouts Rosso", "Timeouts Blu",
                "Mosse Illegali Rosso", "Mosse Illegali Blu",
                "Tempo Medio Mossa Rosso (s)", "Tempo Medio Mossa Blu (s)"
            ])

        # Scrive i dati della riga
        writer.writerow([
            FILE_STRATEGIA_ROSSO,
            FILE_STRATEGIA_BLU,
            NUMERO_PARTITE,
            stats["Red"],
            stats["Blue"],
            stats["Draw"],
            round(elapsed_time, 2),
            round(media_turni, 1),
            agg_stats["Red_timeouts"],
            agg_stats["Blue_timeouts"],
            agg_stats["Red_illegali"],
            agg_stats["Blue_illegali"],
            round(media_tempo_red, 4),
            round(media_tempo_blue, 4)
        ])

    print(f"\nRisultati salvati in '{FILE_RISULTATI}'.")

if __name__ == "__main__":
    main()