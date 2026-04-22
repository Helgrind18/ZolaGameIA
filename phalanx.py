import math
import time

SAFETY_MARGIN = 0.08
MAX_DEPTH = 20


class SearchTimeout(Exception):
    pass


def _check_timeout(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise SearchTimeout


def evaluate_state(game, state, root_player):
    """
    Euristica Falange: Mutua protezione e costrizione allo stallo.
    """
    winner = game.winner(state)
    opponent = game.opponent(root_player)

    if winner == root_player:
        return 100_000
    if winner == opponent:
        return -100_000
    if winner is not None:
        return 0

    # 1. MATERIALE
    my_pieces = state.count(root_player)
    opp_pieces = state.count(opponent)
    material_score = 1000 * (my_pieces - opp_pieces)

    # 2. MOBILITÀ E SOFFOCAMENTO
    my_moves = game._actions_for_player(state, root_player)
    opp_moves = game._actions_for_player(state, opponent)
    # Puniamo severamente le mosse dell'avversario
    mobility_score = (5 * len(my_moves)) - (15 * len(opp_moves))

    # 3. LA FALANGE (Mutua Protezione)
    # Premiamo le nostre pedine se si trovano sulle stesse righe, colonne o diagonali
    # di altre nostre pedine (si guardano le spalle a vicenda).
    phalanx_score = 0
    my_positions = []

    for r in range(state.size):
        for c in range(state.size):
            if state.board[r][c] == root_player:
                my_positions.append((r, c))

    for i in range(len(my_positions)):
        for j in range(i + 1, len(my_positions)):
            r1, c1 = my_positions[i]
            r2, c2 = my_positions[j]

            # Controlla se sono allineate (stessa riga, colonna o diagonale)
            if r1 == r2 or c1 == c2 or abs(r1 - r2) == abs(c1 - c2):
                # Più sono vicine e allineate, più la falange è solida
                distanza = max(abs(r1 - r2), abs(c1 - c2))
                # Un bonus inversamente proporzionale alla distanza
                phalanx_score += (10 - distanza) * 5

    # 4. PENALITÀ ISOLAMENTO AVVERSARIO
    # Se l'avversario è sui bordi estremi, noi stiamo raggruppati al centro/medio.
    # Evitiamo di andargli incontro.
    pos_score = 0
    levels = game.get_all_distance_levels()
    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece == root_player:
                # La Falange ama stare compatta nei livelli 3, 4, 5.
                if 3 <= levels[r][c] <= 5:
                    pos_score += 15

    return material_score + mobility_score + phalanx_score + pos_score


def _move_order_key(move):
    (fr, fc), (tr, tc), is_capture = move
    return (1 if is_capture else 0, -fr, -fc, -tr, -tc)


def order_moves(legal_moves):
    return sorted(legal_moves, key=_move_order_key, reverse=True)


def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player, deadline):
    _check_timeout(deadline)
    legal_moves = game.actions(state)

    if depth == 0 or game.is_terminal(state) or not legal_moves:
        return evaluate_state(game, state, root_player), None

    legal_moves = order_moves(legal_moves)
    best_move = legal_moves[0]

    if maximizing_player:
        value = -math.inf
        for move in legal_moves:
            _check_timeout(deadline)
            child_state = game.result(state, move)
            child_value, _ = alphabeta(
                game, child_state, depth - 1, alpha, beta, False, root_player, deadline
            )
            if child_value > value:
                value = child_value
                best_move = move
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value, best_move

    value = math.inf
    for move in legal_moves:
        _check_timeout(deadline)
        child_state = game.result(state, move)
        child_value, _ = alphabeta(
            game, child_state, depth - 1, alpha, beta, True, root_player, deadline
        )
        if child_value < value:
            value = child_value
            best_move = move
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value, best_move


def playerStrategy(game, state, timeout=3):
    legal_moves = game.actions(state)
    if not legal_moves:
        return None

    ordered_legal_moves = order_moves(legal_moves)
    best_move = ordered_legal_moves[0]

    if len(ordered_legal_moves) == 1:
        return best_move

    deadline = time.perf_counter() + max(0.01, timeout - SAFETY_MARGIN)
    root_player = state.to_move

    for depth in range(1, MAX_DEPTH + 1):
        try:
            _, candidate = alphabeta(
                game, state, depth, -math.inf, math.inf, True, root_player, deadline
            )
            if candidate in legal_moves:
                best_move = candidate
        except SearchTimeout:
            break
        except Exception:
            break

    if best_move not in legal_moves:
        return ordered_legal_moves[0]

    return best_move