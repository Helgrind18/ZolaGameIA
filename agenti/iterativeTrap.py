import math
import random
import time


class TimeoutException(Exception):
    pass


def evaluate_state(game, state, root_player):
    """Valuta lo stato fondendo il vantaggio materiale con la strategia 'Buco Nero'."""
    winner = game.winner(state)
    if winner == root_player:
        return 10_000
    if winner == game.opponent(root_player):
        return -10_000
    if winner is not None:
        return 0

    opponent = game.opponent(root_player)
    score = 0

    # 1. VANTAGGIO MATERIALE
    root_count = state.count(root_player)
    opp_count = state.count(opponent)
    score += 100 * (root_count - opp_count)

    # 2. STRATEGIA "BUCO NERO"
    for r in range(state.size):
        for c in range(state.size):
            p = state.board[r][c]
            if p is None:
                continue

            lvl = game.get_distance_level(r, c)

            if p == opponent:
                if lvl <= 2:
                    score += 40
                elif lvl >= 8:
                    score += 15
            elif p == root_player:
                if 3 <= lvl <= 5:
                    score += 25
                elif lvl <= 2:
                    score -= 50

    # 3. MOBILITÀ
    root_mobility = len(game._actions_for_player(state, root_player))
    opp_mobility = len(game._actions_for_player(state, opponent))
    score += 2 * (root_mobility - opp_mobility)

    return score


def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player, start_time, time_limit):
    if time.perf_counter() - start_time > time_limit:
        raise TimeoutException()

    legal_moves = game.actions(state)
    if depth == 0 or game.is_terminal(state) or not legal_moves:
        return evaluate_state(game, state, root_player), None

    best_moves = []

    if maximizing_player:
        value = -math.inf
        for move in legal_moves:
            child_state = game.result(state, move)
            child_value, _ = alphabeta(
                game, child_state, depth - 1, alpha, beta, False, root_player, start_time, time_limit
            )

            if child_value > value:
                value = child_value
                best_moves = [move]
            elif child_value == value:
                best_moves.append(move)

            alpha = max(alpha, value)
            if alpha >= beta:
                break

        return value, random.choice(best_moves) if best_moves else None

    # Minimizing player
    value = math.inf
    for move in legal_moves:
        child_state = game.result(state, move)
        child_value, _ = alphabeta(
            game, child_state, depth - 1, alpha, beta, True, root_player, start_time, time_limit
        )

        if child_value < value:
            value = child_value
            best_moves = [move]
        elif child_value == value:
            best_moves.append(move)

        beta = min(beta, value)
        if alpha >= beta:
            break

    return value, random.choice(best_moves) if best_moves else None


def playerStrategy(game, state, timeout=3):
    """
    Strategia con Iterative Deepening.
    Sfrutta tutto il tempo a disposizione aumentando la profondità gradualmente.
    """
    legal_moves = game.actions(state)
    if not legal_moves:
        return None

    start_time = time.perf_counter()
    # Ci teniamo un margine di sicurezza di 0.15 secondi per chiudere le funzioni e ritornare il valore
    time_limit = timeout - 0.15

    best_move_overall = random.choice(legal_moves)  # Fallback di sicurezza iniziale
    current_depth = 1

    try:
        # Continua ad approfondire all'infinito finché non scatta l'eccezione del tempo
        while True:
            _, best_move_for_depth = alphabeta(
                game, state, current_depth, -math.inf, math.inf, True, state.to_move, start_time, time_limit
            )

            # Se siamo arrivati qui senza TimeoutException, significa che la ricerca per questa
            # profondità è stata completata con successo al 100%. Possiamo aggiornare la nostra mossa sicura.
            if best_move_for_depth is not None:
                best_move_overall = best_move_for_depth

            # Se la partita è determinabile già a questa profondità (es. scacco matto a profondità 3),
            # possiamo anche fermarci. Ma per semplicità, continuiamo.
            current_depth += 1

    except TimeoutException:
        # Il tempo è scaduto! L'algoritmo si è interrotto a metà di una profondità.
        # Stampiamo a che profondità siamo arrivati prima di stampare (utile per debug/statistiche)
        # print(f"Timeout raggiunto. Profondità completa salvata: {current_depth - 1}")
        pass

    return best_move_overall