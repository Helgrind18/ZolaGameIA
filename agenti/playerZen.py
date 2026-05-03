import math
import time
import random

SAFETY_MARGIN = 0.08
MAX_DEPTH = 20
WIN_SCORE = 100_000

# Filosofia semplice e coerente
PIECE_WEIGHT = 1000
MOBILITY_WEIGHT = 5
BORDER_MULTIPLIER = 10

# 1. MEMOIZZAZIONE: Cache globale per velocizzare l'albero
EVAL_CACHE = {}


class SearchTimeout(Exception):
    pass


def _check_timeout(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise SearchTimeout


def evaluate_state(game, state, root_player):
    # Controllo Cache: se abbiamo già valutato questa scacchiera, usiamo il dato
    board_hash = str(state.board)
    cache_key = (board_hash, root_player)
    if cache_key in EVAL_CACHE:
        return EVAL_CACHE[cache_key]

    winner = game.winner(state)
    opponent = game.opponent(root_player)

    if winner == root_player:
        return WIN_SCORE
    if winner == opponent:
        return -WIN_SCORE
    if winner is not None:
        return 0

    my_pieces = state.count(root_player)
    opp_pieces = state.count(opponent)
    material_score = PIECE_WEIGHT * (my_pieces - opp_pieces)

    my_moves = game._actions_for_player(state, root_player)
    opp_moves = game._actions_for_player(state, opponent)

    border_score = 0
    levels = game.get_all_distance_levels()
    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is None:
                continue
            pos_value = levels[r][c] * BORDER_MULTIPLIER
            if piece == root_player:
                border_score += pos_value
            else:
                border_score -= pos_value

    # 2. BIVIO STRATEGICO
    if root_player == "Red":
        mobility_score = MOBILITY_WEIGHT * (len(my_moves) - len(opp_moves))
        final_score = material_score + mobility_score + border_score
    else:
        # Il Blu gioca per soffocare il Rosso (Peso 15 contro le mosse avversarie)
        mobility_score = (MOBILITY_WEIGHT * len(my_moves)) - (15 * len(opp_moves))
        final_score = material_score + mobility_score + border_score

    # Salviamo in cache
    EVAL_CACHE[cache_key] = final_score
    return final_score


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
    best_moves = []  # Raccoglitore per mosse a pari merito

    if maximizing_player:
        value = -math.inf
        for move in legal_moves:
            _check_timeout(deadline)
            child_state = game.result(state, move)
            child_value, _ = alphabeta(
                game, child_state, depth - 1, alpha, beta, False, root_player, deadline
            )

            # 3. RANDOMIZZAZIONE TIE-BREAKER
            if child_value > value:
                value = child_value
                best_moves = [move]  # Nuova mossa migliore assoluta
            elif child_value == value:
                best_moves.append(move)  # Mossa a pari merito

            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value, random.choice(best_moves)

    value = math.inf
    for move in legal_moves:
        _check_timeout(deadline)
        child_state = game.result(state, move)
        child_value, _ = alphabeta(
            game, child_state, depth - 1, alpha, beta, True, root_player, deadline
        )

        if child_value < value:
            value = child_value
            best_moves = [move]
        elif child_value == value:
            best_moves.append(move)

        beta = min(beta, value)
        if alpha >= beta:
            break

    return value, random.choice(best_moves)


def playerStrategy(game, state, timeout=3):
    global EVAL_CACHE
    EVAL_CACHE.clear()  # Svuota la cache ad ogni turno per evitare picchi di RAM

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
                game,
                state,
                depth,
                -math.inf,
                math.inf,
                True,
                root_player,
                deadline,
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