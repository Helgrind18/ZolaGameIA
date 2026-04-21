import math
import random

# RIPORTATO A 2: Evita il timeout dei 3 secondi sulla scacchiera 8x8
SEARCH_DEPTH = 2


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

    # 1. VANTAGGIO MATERIALE (Fondamentale)
    # L'IA deve comunque cercare di non farsi mangiare le pedine.
    root_count = state.count(root_player)
    opp_count = state.count(opponent)
    score += 100 * (root_count - opp_count)

    # 2. STRATEGIA "BUCO NERO" (Posizionale)
    for r in range(state.size):
        for c in range(state.size):
            p = state.board[r][c]
            if p is None:
                continue

            lvl = game.get_distance_level(r, c)

            if p == opponent:
                # Premiamo la situazione se l'avversario è incastrato al centro (livello 1 o 2)
                # Da qui fa molta fatica a catturare verso l'interno.
                if lvl <= 2:
                    score += 40
                # Lieve bonus se riusciamo a spingerlo sui bordi estremi (livello 8 o 9)
                elif lvl >= 8:
                    score += 15
            elif p == root_player:
                # Vogliamo che le nostre pedine mantengano il controllo degli anelli intermedi (3, 4, 5)
                # È la zona d'attacco migliore per colpire chi è al centro o ai bordi.
                if 3 <= lvl <= 5:
                    score += 25
                # Penalità se cadiamo noi stessi nel buco nero centrale
                elif lvl <= 2:
                    score -= 50

    # 3. MOBILITÀ DI BASE
    # Diamo un leggero peso a quante mosse abbiamo rispetto all'avversario per evitare lo stallo.
    root_mobility = len(game._actions_for_player(state, root_player))
    opp_mobility = len(game._actions_for_player(state, opponent))
    score += 2 * (root_mobility - opp_mobility)

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
                game, child_state, depth - 1, alpha, beta, False, root_player
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
            game, child_state, depth - 1, alpha, beta, True, root_player
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
        game, state, SEARCH_DEPTH, -math.inf, math.inf, True, state.to_move
    )
    return best_move