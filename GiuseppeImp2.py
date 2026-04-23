import math
import random
import time

# --- COSTANTI DI SISTEMA ---
# Limite di sicurezza a 2.9 come da tua richiesta.
# Se il calcolo supera questo tempo, il bot restituisce l'ultima mossa migliore trovata.
TIME_LIMIT = 2.9

# Memoria globale per non ricalcolare scacchiere già viste
EVAL_CACHE = {}


def evaluate_state(game, state, root_player):
    """
    Funzione di Valutazione Euristica - Versione "Cecchino" + Ibrida (Caos solo per Blu).
    """
    # 1. CONTROLLO CACHE: se abbiamo già valutato questa posizione, usiamo il dato pronto
    board_hash = str(state.board)
    cache_key = (board_hash, root_player)

    if cache_key in EVAL_CACHE:
        return EVAL_CACHE[cache_key]

    # 2. CONTROLLO STATI TERMINALI
    winner = game.winner(state)
    if winner == root_player:
        return 100_000
    if winner == game.opponent(root_player):
        return -100_000
    if winner is not None:
        return 0

    opponent = game.opponent(root_player)

    # 3. MATERIALE (Peso 1000: priorità assoluta alla conservazione dei pezzi)
    my_pieces = state.count(root_player)
    opp_pieces = state.count(opponent)
    material_score = 1000 * (my_pieces - opp_pieces)

    # 4. MOBILITÀ (Peso 5: preferenza per posizioni con più opzioni)
    my_moves = game._actions_for_player(state, root_player)
    opp_moves = game._actions_for_player(state, opponent)
    mobility_score = 5 * (len(my_moves) - len(opp_moves))

    # 5. CONTROLLO DEI BORDI (Versione "Cecchino": i bordi sono i livelli più alti)
    border_score = 0
    levels = game.get_all_distance_levels()

    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is not None:
                # Premiamo le pedine sui bordi (livelli alti come 5 o 6)
                pos_value = levels[r][c] * 10

                if piece == root_player:
                    border_score += pos_value
                else:
                    border_score -= pos_value

    # --- ARMA 1: IL FATTORE CAOS (SOLO IN DIFESA) ---
    # Se siamo Blu (secondo giocatore), aggiungiamo un rumore casuale
    # per confondere il bot avversario e rompere la sua strategia deterministica.
    # Se siamo Rosso, noise = 0 per mantenere la precisione assoluta.
    noise = 0.0
    if root_player == "Blue":
        noise = random.uniform(0.0, 0.9)

    # Punteggio finale sommato
    final_score = material_score + mobility_score + border_score + noise

    # Salviamo in cache per questo turno
    EVAL_CACHE[cache_key] = final_score
    return final_score


def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player, start_time):
    """
    Algoritmo Minimax con potatura Alpha-Beta e controllo temporale.
    """
    # Controllo salvavita: se superiamo il tempo limite, usciamo subito
    if time.perf_counter() - start_time >= TIME_LIMIT:
        raise TimeoutError

    legal_moves = game.actions(state)

    if depth == 0 or game.is_terminal(state) or not legal_moves:
        return evaluate_state(game, state, root_player), None

    # MOVE ORDERING: mettiamo le catture per prime per ottimizzare i tagli Alpha-Beta
    legal_moves.sort(key=lambda m: m[2], reverse=True)

    best_move = None

    if maximizing_player:
        max_eval = -math.inf
        for move in legal_moves:
            child_state = game.result(state, move)
            eval_value, _ = alphabeta(game, child_state, depth - 1, alpha, beta, False, root_player, start_time)

            if eval_value > max_eval:
                max_eval = eval_value
                best_move = move

            alpha = max(alpha, max_eval)
            if alpha >= beta:
                break  # Taglio Beta

        return max_eval, best_move

    else:
        min_eval = math.inf
        for move in legal_moves:
            child_state = game.result(state, move)
            eval_value, _ = alphabeta(game, child_state, depth - 1, alpha, beta, True, root_player, start_time)

            if eval_value < min_eval:
                min_eval = eval_value
                best_move = move

            beta = min(beta, min_eval)
            if alpha >= beta:
                break  # Taglio Alfa

        return min_eval, best_move


def playerStrategy(game, state, timeout=3):
    """
    Strategia principale: implementa l'Iterative Deepening con gestione della memoria.
    """
    start_time = time.perf_counter()
    legal_moves = game.actions(state)

    if not legal_moves:
        return None

    # Pulizia della cache all'inizio di ogni turno per evitare dati obsoleti o troppa RAM
    global EVAL_CACHE
    EVAL_CACHE.clear()

    # Mossa di fallback (casuale) in caso di problemi immediati
    best_overall_move = random.choice(legal_moves)

    # Approfondimento iterativo: esplora depth 1, poi 2, poi 3... finché c'è tempo
    try:
        for current_depth in range(1, 20):
            _, current_best_move = alphabeta(
                game,
                state,
                current_depth,
                -math.inf,
                math.inf,
                True,
                state.to_move,
                start_time
            )

            # Se la profondità è stata completata senza errori, aggiorniamo la mossa sicura
            if current_best_move is not None:
                best_overall_move = current_best_move

    except TimeoutError:
        # Quando scatta il timeout (2.9s), usciamo silenziosamente
        # restituendo la mossa migliore trovata alla profondità precedente
        pass

    return best_overall_move