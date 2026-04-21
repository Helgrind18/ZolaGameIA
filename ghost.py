import math
import time

SAFETY_MARGIN = 0.08
MAX_DEPTH = 20

# --- FILOSOFIA "FANTASMA" ---
# Non sacrifichiamo MAI materiale.
PIECE_WEIGHT = 10000


class SearchTimeout(Exception):
    pass


def _check_timeout(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise SearchTimeout


def evaluate_state(game, state, root_player):
    """Euristica Fantasma: Sopravvivenza, Invisibilità e Paralisi dell'Avversario."""
    winner = game.winner(state)
    opponent = game.opponent(root_player)

    if winner == root_player:
        return 100_000_000
    if winner == opponent:
        return -100_000_000
    if winner is not None:
        return 0

    # 1. MATERIALE (Priorità Assoluta)
    my_pieces = state.count(root_player)
    opp_pieces = state.count(opponent)
    material_score = PIECE_WEIGHT * (my_pieces - opp_pieces)

    my_moves = game._actions_for_player(state, root_player)
    opp_moves = game._actions_for_player(state, opponent)

    # 2. SOFFOCAMENTO (Starvation)
    # Penalizziamo ferocemente ogni singola mossa che l'avversario ha a disposizione.
    # Vogliamo spingerlo ad avere 0 mosse per fargli saltare il turno.
    mobility_score = (5 * len(my_moves)) - (30 * len(opp_moves))

    # 3. L'INVISIBILITÀ (Risoluzione dell'Effetto Orizzonte)
    # Contiamo quante mosse di CATTURA ha l'avversario.
    # Se alla fine della nostra ricerca ci troviamo nel loro mirino, fuggiamo!
    my_captures = sum(1 for m in my_moves if m[2])
    opp_captures = sum(1 for m in opp_moves if m[2])

    # Valore altissimo per evitare di lasciare pezzi esposti
    threat_score = (100 * my_captures) - (400 * opp_captures)

    # 4. GESTIONE DEI BORDI "JUDO"
    # Loro vogliono andare sui bordi. Lasciamoglielo fare, ma noi restiamo a distanza di sicurezza.
    pos_score = 0
    levels = game.get_all_distance_levels()

    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is None:
                continue

            lvl = levels[r][c]

            if piece == root_player:
                # Noi stiamo nella "Golden Zone" (Livelli 3, 4, 5).
                # Abbastanza lontani dal buco nero, ma senza incastrarci sui bordi.
                if 3 <= lvl <= 5:
                    pos_score += 40
                elif lvl >= 7:
                    pos_score -= 50  # Penalità se ci incastriamo noi ai bordi
            else:
                # Diamo un piccolo bonus al nostro stato se il nemico si auto-esilia sui bordi.
                if lvl >= 7:
                    pos_score += 20

    return material_score + mobility_score + threat_score + pos_score


def _move_order_key(move):
    # Ottimizzazione del motore: ordina le catture per prime
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