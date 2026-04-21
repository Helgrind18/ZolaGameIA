import math
import random

# Profondità fissa a 2 per evitare i timeout sulla scacchiera 8x8
SEARCH_DEPTH = 2


def evaluate_state(game, state, root_player):
    """Valuta lo stato fondendo il vantaggio materiale con la strategia 'Sindrome da Bordo'."""
    winner = game.winner(state)
    if winner == root_player:
        return 10_000
    if winner == game.opponent(root_player):
        return -10_000
    if winner is not None:
        return 0

    opponent = game.opponent(root_player)
    score = 0

    # 1. VANTAGGIO MATERIALE (Fondamentale)
    # È essenziale non sacrificare pezzi inutilmente.
    root_count = state.count(root_player)
    opponent_count = state.count(opponent)
    score += 100 * (root_count - opponent_count)

    # 2. STRATEGIA "SINDROME DA BORDO" (Posizionale)
    for r in range(state.size):
        for c in range(state.size):
            p = state.board[r][c]
            if p is None:
                continue

            lvl = game.get_distance_level(r, c)

            if p == opponent:
                # Vogliamo spingere l'avversario verso l'esterno.
                # Se l'avversario è ai bordi (livello 7+), gli togliamo mobilità non catturante.
                if lvl >= 7:
                    score += 35
            elif p == root_player:
                # Per noi stessi, dobbiamo ASSOLUTAMENTE evitare di rimanere bloccati ai bordi.
                if lvl >= 7:
                    score -= 40
                # Vogliamo stare nei livelli intermedi per mantenere opzioni di movimento.
                elif 3 <= lvl <= 5:
                    score += 20

    # 3. RESTRIZIONE DI MOBILITÀ
    # Per questa strategia, togliere opzioni legali all'avversario è fondamentale.
    root_mobility = len(game._actions_for_player(state, root_player))
    opponent_mobility = len(game._actions_for_player(state, opponent))

    # Diamo un peso maggiore alla mobilità rispetto al Buco Nero,
    # perché l'obiettivo di questa tattica è proprio soffocare le mosse nemiche.
    score += 5 * (root_mobility - opponent_mobility)

    return score


def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player):
    legal_moves = game.actions(state)
    if depth == 0 or game.is_terminal(state) or not legal_moves:
        return evaluate_state(game, state, root_player), None

    best_moves = []

    if maximizing_player:
        value = -math.inf
        for move in legal_moves:
            child_state = game.result(state, move)
            child_value, _ = alphabeta(
                game,
                child_state,
                depth - 1,
                alpha,
                beta,
                False,
                root_player,
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

    value = math.inf
    for move in legal_moves:
        child_state = game.result(state, move)
        child_value, _ = alphabeta(
            game,
            child_state,
            depth - 1,
            alpha,
            beta,
            True,
            root_player,
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
    legal_moves = game.actions(state)
    if not legal_moves:
        return None

    _, best_move = alphabeta(
        game,
        state,
        SEARCH_DEPTH,
        -math.inf,
        math.inf,
        True,
        state.to_move,
    )
    return best_move