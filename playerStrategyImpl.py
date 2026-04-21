#Idea generale:
# scegliere una mossa valida
# farlo entro il tempo limite
# cercare sempre un po' più in profondità finchè c'è tempo
# esplorare prima le mosse più promettenti
# non restiture mai una mossa illegale

import math
import random
import time


# Tempo di sicurezza per evitare il timeout del main program.
SAFETY_MARGIN = 0.08 # Questo perchè il programma non aspetta fino all'ultimo millisecondo. Si ferma un po' prima per evitare di sforare
# Profondita' massima tentata dall'iterative deepening.
# Se il tempo scade prima, la ricerca si ferma alla migliore profondita' completata.
MAX_DEPTH = 20 # È la profondità massima teorica che l'iterative deepening proverà a raggiungere. Non vuol dire che arriverà davvero a 20 ma prova da 1 a 20 se c'è tempo, anche se in pratica quasi sempre si fermerà prima

# Pesi dell'euristica.
WIN_SCORE = 1_000_000 # Se ha già vinto, il punteggio è altissimo
PIECE_WEIGHT = 120 # Conta la differenza di pedine. Se si hanno più pedine dell'avversario è bene.
MOBILITY_WEIGHT = 12 # Conta quante mosse si hanno a disposizione. Più mobilità = più possibilità
CAPTURE_WEIGHT = 25 # Premia gli stati in cui si hanno più catture disponibili
VULNERABILITY_WEIGHT = 30 # Penalizza i pezzi esposti
CENTER_WEIGHT = 8 # Dà valore al controllo del centro.


# Questa classe serve solo internamente. Quando il tempo sta finendo, invece di continuare la ricerca, il codice lancia questa eccezione e interrompe tutto in modo pulito. È molto meglio che lasciare la ricerca andare avanti troppo

class SearchTimeout(Exception):
    """Eccezione interna per interrompere la ricerca quando il tempo sta per scadere."""

# Controlla se il tempo è scaduto
def _check_timeout(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise SearchTimeout

# Conta quante mosse, tra quelle disponibili, sono catture
def _capture_count(moves):
    return sum(1 for move in moves if move[2])

# Questa funzione crea un insieme delle caselle di arrivo delle catture
def _captured_cells(moves):
    return {move[1] for move in moves if move[2]}

# Questa funzione misura quanto i pezzi del giocatore sono vicini al centro.
# Questo serve per le catture ed il controllo del gioco
def _center_score(game, state, player):
    """Più il pezzo è vicino al centro, più alto è il punteggio."""
    max_level = max(max(row) for row in game.distance_levels)
    total = 0
    for r in range(state.size):
        for c in range(state.size):
            if state.board[r][c] == player:
                total += (max_level + 1 - game.get_distance_level(r, c))
    return total

# Questa è la funzioen che valuta uno stato
def evaluate_state(game, state, root_player):
    """Valuta lo stato dal punto di vista di root_player."""
    # Controllo vittoria / sconfitta
    winner = game.winner(state)
    if winner == root_player:
        return WIN_SCORE # Vittoria = punteggio enorme positivo
    if winner == game.opponent(root_player):
        return -WIN_SCORE # Sconfitta = punteggio enorme negativo
    if winner is not None:
        return 0 # Gestione di un caso raro

    # Calcolo delle feature
    opponent = game.opponent(root_player)
    # Numero di pedine dei due giocatori
    root_count = state.count(root_player)
    opp_count = state.count(opponent)
    # Lista delle mosse possibili per ciascun giocatore
    root_actions = game._actions_for_player(state, root_player)
    opp_actions = game._actions_for_player(state, opponent)
    # Quante mosse può fare ciascuno
    root_mobility = len(root_actions)
    opp_mobility = len(opp_actions)
    # Quante catture sono disponibili
    root_captures = _capture_count(root_actions)
    opp_captures = _capture_count(opp_actions)
    # Quanti pezzi risultano esposti a possibili catture
    root_vulnerable = len(_captured_cells(opp_actions))
    opp_vulnerable = len(_captured_cells(root_actions))
    # Quanto i pezzi sono centrali
    root_center = _center_score(game, state, root_player)
    opp_center = _center_score(game, state, opponent)

    # Questa formula combina tutto:
    # Lo stato è migliore se:
        #   ha più pezzi
        #   ha più mosse
        #   ha più catture
        #   ha meno pezzi esposti → infatti la vulenrabilità ha un segno negativo perchè avere più pezzi vulnerabili è male, quindi il punteggio deve scendere
        #   controlli meglio il centro

    return (
        PIECE_WEIGHT * (root_count - opp_count)
        + MOBILITY_WEIGHT * (root_mobility - opp_mobility)
        + CAPTURE_WEIGHT * (root_captures - opp_captures)
        - VULNERABILITY_WEIGHT * (root_vulnerable - opp_vulnerable)
        + CENTER_WEIGHT * (root_center - opp_center)
    )

# Questa funzione serve a dare una priorità alle mosse. L'idea è prima esplodo le mosse più promettenti, aiuta tantissimo alpha - beta perchè può tagliare più rami
def _move_order_key(game, state, move, root_player):
    """Ordina le mosse con una stima leggera, senza calcoli inutili."""
    # Legge la cella di partenza, arrivo, se è di cattura ed il livello rispetto al centro prima e dopo
    (fr, fc), (tr, tc), is_capture = move
    from_level = game.get_distance_level(fr, fc)
    to_level = game.get_distance_level(tr, tc)

    # Priorita': catture, catture più centrali, mosse che spostano pezzi meno esposti.
    capture_bonus = 1000 if is_capture else 0

    if is_capture:
        # Per le catture preferiamo arrivare più verso il centro.
        center_gain = from_level - to_level
    else:
        # Per le mosse normali siamo costretti ad allontanarci dal centro;
        # preferiamo quelle che si allontanano il meno possibile.
        center_gain = -(to_level - from_level)

    # Un piccolo bonus se il pezzo di partenza è vicino al centro:
    # spesso sono i pezzi più attivi e più pericolosi.
    source_activity = -from_level

    # Tie-break stabile e leggero.
    lexicographic = (-fr, -fc, -tr, -tc)

    # Dal punto di vista del giocatore di turno la priorita' maggiore deve andare alle
    # mosse con chiave più grande.
    return (capture_bonus + 10 * center_gain + source_activity, lexicographic)


def order_moves(game, state, legal_moves, root_player, maximizing_player):
    ordered = sorted(
        legal_moves,
        key=lambda move: _move_order_key(game, state, move, root_player),
        reverse=maximizing_player,
    )
    return ordered


def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player, deadline):
    _check_timeout(deadline)    # Controlla il tempo

    legal_moves = game.actions(state)
    if depth == 0 or game.is_terminal(state) or not legal_moves:
        return evaluate_state(game, state, root_player), None

    legal_moves = order_moves(game, state, legal_moves, root_player, maximizing_player)
    best_move = legal_moves[0]

    if maximizing_player:
        value = -math.inf
        for move in legal_moves:    # Prova ogni mossa
            _check_timeout(deadline)
            child_state = game.result(state, move)  # genera lo stato figlio e richiama l'algoritmo ricorsivamente
            child_value, _ = alphabeta(
                game,
                child_state,
                depth - 1,
                alpha,
                beta,
                False,
                root_player,
                deadline,
            )

            if child_value > value: # verifica se la mossa trovata ricorsivamente sia migliore, in caso aggiorna
                value = child_value
                best_move = move

            alpha = max(alpha, value)
            if alpha >= beta:
                break    # Condizione di potatura 

        return value, best_move

    value = math.inf
    for move in legal_moves:
        _check_timeout(deadline)
        child_state = game.result(state, move)
        child_value, _ = alphabeta(
            game,
            child_state,
            depth - 1,
            alpha,
            beta,
            True,
            root_player,
            deadline,
        )

        if child_value < value:
            value = child_value
            best_move = move

        beta = min(beta, value)
        if alpha >= beta:
            break

    return value, best_move


def playerStrategy(game, state, timeout=3):
    """
    Strategia:
    - iterative deepening
    - alpha-beta pruning
    - ordinamento leggero delle mosse
    - controllo finale di legalita'
    """
    legal_moves = game.actions(state)
    if not legal_moves:
        return None

    # Partiamo da una mossa legale semplice, cosi' abbiamo sempre un fallback sicuro.
    ordered_legal_moves = order_moves(game, state, legal_moves, state.to_move, True)
    best_move = ordered_legal_moves[0]

    # Se c'e' una sola mossa legale, evitiamo ricerca inutile.
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

    # Controllo finale di legalita': mai restituire una mossa non valida.
    if best_move not in legal_moves:
        return random.choice(legal_moves)

    return best_move