import math
import random
import time

# --- COSTANTI DI TEMPO ---
# Ci teniamo un margine di sicurezza di 0.10 secondi per evitare che il main
# thread ci tagli fuori per il timeout dei 3 secondi.
TIME_LIMIT = 2.87


""""
def evaluate_state(game, state, root_player):
    
    #Funzione di Valutazione Euristica.
    #Stima quanto è vantaggioso uno stato per il root_player.
    
    winner = game.winner(state)
    if winner == root_player:
        return 100_000  # Vittoria: valore massimo assoluto
    if winner == game.opponent(root_player):
        return -100_000  # Sconfitta: valore minimo assoluto
    if winner is not None:
        return 0  # Caso teorico di pareggio/blocco

    opponent = game.opponent(root_player)

    # 1. MATERIALE (Il fattore più importante)
    # Valutiamo 100 punti per ogni pedina di vantaggio.
    my_pieces = state.count(root_player)
    opp_pieces = state.count(opponent)
    material_score = 100 * (my_pieces - opp_pieces)

    # 2. MOBILITÀ (Numero di mosse possibili)
    # Più opzioni abbiamo, più limitiamo l'avversario.
    my_moves = game._actions_for_player(state, root_player)
    opp_moves = game._actions_for_player(state, opponent)
    mobility_score = 5 * (len(my_moves) - len(opp_moves))

    # 3. CONTROLLO DEL CENTRO (Distanza strategica)
    # I livelli vanno da 1 (centro) a 6/7/ecc. Vogliamo premiare le pedine sui livelli bassi.
    center_score = 0
    levels = game.get_all_distance_levels()

    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is not None:
                # Se il livello è 1, (8 - 1) * 10 = 70 punti di posizionamento.
                # Se il livello è 6, (8 - 6) * 10 = 20 punti di posizionamento.
                pos_value = (8 - levels[r][c]) * 10

                if piece == root_player:
                    center_score += pos_value
                else:
                    center_score -= pos_value

    # Sommiamo i pesi per ottenere il valore finale dello stato
    return material_score + mobility_score + center_score
"""

def evaluate_state(game, state, root_player):
    """"
    Funzione di Valutazione Euristica - Versione "Cecchino".
    """
    winner = game.winner(state)
    if winner == root_player:
        return 100_000
    if winner == game.opponent(root_player):
        return -100_000
    if winner is not None:
        return 0

    opponent = game.opponent(root_player)

    # 1. MATERIALE (Il fattore più importante in assoluto)
    # Aumentato a 1000 per assicurarci che non sacrifichi MAI pezzi
    # per un vantaggio posizionale.
    my_pieces = state.count(root_player)
    opp_pieces = state.count(opponent)
    material_score = 1000 * (my_pieces - opp_pieces)

    # 2. MOBILITÀ (Numero di mosse possibili)
    my_moves = game._actions_for_player(state, root_player)
    opp_moves = game._actions_for_player(state, opponent)
    mobility_score = 5 * (len(my_moves) - len(opp_moves))

    # 3. CONTROLLO DEI BORDI (Il "Terreno Alto" di Zola)
    # Diametralmente opposto a prima: premiamo i livelli ALTI.
    # Chi sta sui bordi può attaccare chiunque verso l'interno.
    border_score = 0
    levels = game.get_all_distance_levels()

    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is not None:
                # Il livello stesso diventa il punteggio moltiplicatore (es. Livello 6 = 60 punti)
                pos_value = levels[r][c] * 10

                if piece == root_player:
                    border_score += pos_value
                else:
                    border_score -= pos_value

    return material_score + mobility_score + border_score

def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player, start_time):
    """
    Algoritmo Minimax con potatura Alpha-Beta ricorsivo.
    """
    # TEST DI CUTOFF TEMPORALE: Se stiamo esaurendo il tempo, solleviamo un'eccezione
    # per interrompere istantaneamente l'esplorazione profonda.
    if time.perf_counter() - start_time >= TIME_LIMIT:
        raise TimeoutError("Tempo esaurito per l'iterazione corrente")

    legal_moves = game.actions(state)

    # Condizione di arresto (Test di Cutoff strutturale)
    if depth == 0 or game.is_terminal(state) or not legal_moves:
        return evaluate_state(game, state, root_player), None

    # MOVE ORDERING: Ordiniamo le mosse.
    # La tupla della mossa è ((fr, fc), (tr, tc), is_capture).
    # Ordiniamo mettendo prima le mosse con is_capture == True.
    # Questo ottimizza pesantemente i tagli dell'Alfa-Beta.
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
                break  # Potatura Beta

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
                break  # Potatura Alfa

        return min_eval, best_move


def playerStrategy(game, state, timeout=3):
    """
    Punto di ingresso richiesto dalle specifiche.
    Implementa l'Iterative Deepening.
    """
    start_time = time.perf_counter()
    legal_moves = game.actions(state)

    if not legal_moves:
        return None

    # Inizializziamo con una mossa casuale o la prima disponibile come paracadute assoluto
    best_overall_move = random.choice(legal_moves)

    # APPROFONDIMENTO ITERATIVO (Iterative Deepening)
    # Aumentiamo la profondità progressivamente. Il limite 20 è arbitrario,
    # normalmente il timeout interromperà il ciclo molto prima (intorno a depth 4 o 5).
    try:
        for current_depth in range(1, 20):
            # Eseguiamo la ricerca per la profondità corrente
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

            # Se la ricerca finisce regolarmente (senza TimeoutError),
            # aggiorniamo la mossa migliore sicura.
            if current_best_move is not None:
                best_overall_move = current_best_move

            # Se troviamo una mossa che vince in assoluto, possiamo fermarci subito.
            # (opzionale, ma fa risparmiare tempo se la vittoria è inevitabile)

    except TimeoutError:
        # Quando solleviamo l'eccezione in alphabeta, veniamo catturati qui.
        # Significa che la ricerca a current_depth non ha finito in tempo,
        # quindi ignoriamo i suoi risultati parziali e restituiamo l'ultima
        # mossa sicura calcolata alla profondità (current_depth - 1).
        pass

    return best_overall_move