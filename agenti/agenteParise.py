import math
import time
EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

# Inizializza la tabella globale
transposition_table = {}


#funzione di valutazione
def evaluate_state(game, state, root_player):
    """
    Strategia Passivo-Aggressiva (Controllo Periferico e Soffocamento).
    Premia i pezzi sui bordi (cecchini), la mobilità negata all'avversario e le minacce calcolate.
    """
    winner = game.winner(state)
    if winner == root_player:
        return 100_000
    if winner == game.opponent(root_player):
        return -100_000
    if winner is not None:
        return 0

    opponent = game.opponent(root_player)

    # 1. MATERIALE (La base: non perdere pezzi)
    root_count = state.count(root_player)
    opp_count = state.count(opponent)

    # 2. MOBILITÀ e MINACCE (Estrazione mosse)
    root_actions = game._actions_for_player(state, root_player)
    opp_actions = game._actions_for_player(state, opponent)

    root_mobility = len(root_actions)
    opp_mobility = len(opp_actions)

    root_captures = sum(1 for m in root_actions if m[2] is True)
    opp_captures = sum(1 for m in opp_actions if m[2] is True)

    # 3. POSIZIONAMENTO PERIFERICO (Il 40% della tua strategia)
    # Calcoliamo quanto i pezzi sono "parcheggiati in sicurezza" lontano dal centro
    root_position_score = 0
    opp_position_score = 0

    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is not None:
                # get_distance_level restituisce 1 per il centro, numeri più alti per i bordi.
                # Usiamo direttamente questo numero come moltiplicatore!
                # Un pezzo al livello 4 (bordo estremo) vale 4 volte il bonus posizionale.
                level = game.get_distance_level(r, c)

                if piece == root_player:
                    root_position_score += level
                else:
                    opp_position_score += level

    # --- PESI DELL'EURISTICA (Bilanciati sulla tua ricerca) ---
    SCORE_MATERIALE = 500  # Base inalterabile (la sopravvivenza)

    # Il 40% (Posizione/Controllo): Premia pesantemente chi si schiera sui bordi
    SCORE_POSIZIONE = 20

    # Il 25% (Difesa/Pass): Aumentato drasticamente. Se l'avversario ha 0 mosse, subisce un malus enorme.
    SCORE_MOBILITA = 30

    # Il 35% (Aggressività Calcolata): Mantenuto letale, ma inferiore alla sopravvivenza posizionale
    SCORE_MINACCIA = 25

    # Calcolo finale
    score = (root_count - opp_count) * SCORE_MATERIALE
    score += (root_mobility - opp_mobility) * SCORE_MOBILITA
    score += (root_captures - opp_captures) * SCORE_MINACCIA
    score += (root_position_score - opp_position_score) * SCORE_POSIZIONE

    return score

def order_moves(moves):
    #ordino le mosse per massimizzare i tagli dell'Alpha-beta
    return sorted(moves, key=lambda m:m[2], reverse=True)

def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player, start_time, time_limit):
    if (time.perf_counter() - start_time) > time_limit:
        raise TimeoutError()

    alpha_original=alpha

    #check iniziale se è presente nel dizionario mi salto il calcolo
    key=hashing(state)
    if key in transposition_table:
        diz_value = transposition_table[key]
        #utilizzo il dato se è stato calcolato a una profondità adeguata
        if diz_value['depth'] >= depth:
            if diz_value['flag'] == EXACT:
                return diz_value['value'], diz_value['move']
            elif diz_value['flag'] == LOWERBOUND:
                alpha = max(alpha, diz_value['value'])
            elif diz_value['flag'] == UPPERBOUND:
                beta = min(beta, diz_value['value'])
            if alpha >= beta:
                return diz_value['value'], diz_value['move']

    legal_moves = game.actions(state)
    if depth == 0 or game.is_terminal(state) or not legal_moves :
        return evaluate_state(game, state, root_player), None

    ordered_moves = order_moves(legal_moves) # (Ricordati di correggere il typo in order_moves)
    best_move = ordered_moves[0] if ordered_moves else None

    if maximizing_player:
        value = -math.inf
        for move in ordered_moves:
            child_state = game.result(state, move)
            try:
                child_value, _= alphabeta(game, child_state, depth-1, alpha, beta, False, root_player, start_time, time_limit)
            except TimeoutError:
                if best_move is None: best_move = move
                raise

            if child_value > value:
                value = child_value
                best_move = move

            alpha = max(alpha, value)
            if beta <= alpha:
                break

    else:
        value = math.inf
        for move in ordered_moves:
            child_state = game.result(state, move)
            try:
                child_value, _ = alphabeta(
                    game, child_state, depth - 1, alpha, beta, True, root_player, start_time, time_limit
                )
            except TimeoutError:
                if best_move is None: best_move = move
                raise

            if child_value < value:
                value = child_value
                best_move = move

            beta = min(beta, value)
            if alpha >= beta:
                break
    if value <= alpha_original:
        flag = UPPERBOUND
    elif value >= beta:
        flag = LOWERBOUND
    else:
        flag = EXACT

    transposition_table[key] = {
        'value': value,
        'depth': depth,
        'flag': flag,
        'move': best_move
    }
    return value, best_move

def playerStrategy(game, state, timeout=3):
    global transposition_table
    transposition_table = {}
    start_time = time.perf_counter()

    # CORRETTO: timeout (es. 3) meno 0.2
    time_limit = timeout - 0.2

    legal_moves = game.actions(state)
    if not legal_moves:
        return None

    # CORRETTO: Non mettere [0] subito alla chiamata della funzione
    ordered_moves = order_moves(legal_moves)
    best_move = ordered_moves[0]

    root_player = state.to_move
    try:
        for i in range(1, 100):
            _, best_move_at_depth = alphabeta(game, state, i, -math.inf, math.inf, True, root_player, start_time, time_limit)
            if best_move_at_depth is not None:
                best_move = best_move_at_depth

            if time.perf_counter() - start_time > time_limit:
                break
    except TimeoutError:
        pass

    return best_move

def hashing(state):
    return (state.to_move, tuple(tuple(row) for row in state.board))