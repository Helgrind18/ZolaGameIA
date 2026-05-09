"""
playerHelgrind.py
Agente per Zola 8x8.

Idea: alpha-beta iterativo entro il limite di 3 secondi, con:
- gestione corretta del PASS quando il giocatore non ha mosse;
- transposition table per non rivalutare gli stessi stati;
- ordinamento delle mosse: vittorie/catture/posizione;
- valutazione euristica su materiale, minacce, mobilità e sicurezza sui livelli esterni.

La funzione richiesta dal torneo è playerStrategy(game, state, timeout=3).
Restituisce sempre una mossa presa da game.actions(state), quindi rimane compatibile
anche se la rappresentazione interna delle mosse cambia leggermente nel materiale base.
"""

import math
import time
from collections import defaultdict

# -----------------------------
# Parametri di sicurezza/ricerca
# -----------------------------
SAFETY_MARGIN = 0.15          # non arrivare mai a 3.000s
MAX_DEPTH = 64                # in pratica ci si ferma per tempo
WIN_SCORE = 10_000_000
INF = 10**18

# -----------------------------
# Pesi euristici
# -----------------------------
W_MATERIAL = 12000            # il materiale domina tutto
W_CAPTURE_MOBILITY = 210      # minacce immediate di cattura
W_MOBILITY = 24               # mosse complessive
W_OUTER_LEVEL = 75            # livelli esterni: più sicuri e più offensivi
W_CENTER_DANGER = 95          # penalità per pezzi troppo centrali
W_THREATENED = 520            # pezzi immediatamente catturabili
W_TURN = 18                   # piccolo bonus se tocca a noi in stati equilibrati

# cache per una singola chiamata a playerStrategy
TT = {}
EVAL_CACHE = {}
KILLERS = defaultdict(list)
HISTORY = defaultdict(int)
LEVEL_CACHE = {}


class SearchTimeout(Exception):
    pass


def _now():
    return time.perf_counter()


def _check(deadline):
    if _now() >= deadline:
        raise SearchTimeout


def _opponent(game, player):
    if hasattr(game, "opponent"):
        return game.opponent(player)
    return "Blue" if player == "Red" else "Red"


def _count(state, player):
    if hasattr(state, "count"):
        return state.count(player)
    total = 0
    for row in state.board:
        for cell in row:
            if cell == player:
                total += 1
    return total


def _state_copy_with_player(state, player):
    if hasattr(state, "copy"):
        s = state.copy()
    else:
        # fallback difensivo; nel progetto caricato esiste copy()
        s = state
    s.to_move = player
    return s


def _actions_for(game, state, player):
    """Mosse legali di un giocatore, senza dipendere troppo dal nome del metodo privato."""
    if hasattr(game, "_actions_for_player"):
        return game._actions_for_player(state, player)
    s = _state_copy_with_player(state, player)
    return game.actions(s)


def _board_key(state):
    """Chiave compatta e hashabile dello stato."""
    # Nel progetto le celle sono "Red", "Blue", None. Le stringhe in tuple sono ok e sicure.
    return (state.to_move, tuple(tuple(row) for row in state.board))


def _levels(game, size):
    if hasattr(game, "get_all_distance_levels"):
        return game.get_all_distance_levels()
    if size in LEVEL_CACHE:
        return LEVEL_CACHE[size]

    # Calcolo identico alla definizione geometrica: livello 1 vicino al centro.
    vals = {}
    uniq = set()
    for r in range(size):
        for c in range(size):
            v = (2 * r - (size - 1)) ** 2 + (2 * c - (size - 1)) ** 2
            vals[(r, c)] = v
            uniq.add(v)
    ordered = sorted(uniq)
    rank = {v: i + 1 for i, v in enumerate(ordered)}
    mat = [[rank[vals[(r, c)]] for c in range(size)] for r in range(size)]
    LEVEL_CACHE[size] = mat
    return mat


def _is_capture(move):
    """Compatibile con la rappresentazione del progetto: ((fr,fc),(tr,tc),True/False)."""
    try:
        return bool(move[2])
    except Exception:
        # Se la terza parte è una tupla catturata/vuota, bool funziona comunque.
        try:
            return bool(move[-1])
        except Exception:
            return False


def _move_points(game, state, move, root_player):
    """Punteggio veloce solo per ordinare le mosse, non per valutare la posizione."""
    try:
        (fr, fc), (tr, tc), _ = move
    except Exception:
        return 0

    levels = _levels(game, state.size)
    score = 0

    if _is_capture(move):
        # Le catture sono decisive. Catturare verso livelli bassi è spesso tatticamente forte,
        # ma da livelli esterni mantiene più sicurezza al pezzo attaccante.
        score += 100000
        score += 550 * levels[fr][fc]
        score -= 75 * levels[tr][tc]
    else:
        # Nelle mosse non catturanti il regolamento obbliga ad andare verso l'esterno:
        # più guadagno di livello = di solito più sicurezza.
        score += 800 * (levels[tr][tc] - levels[fr][fc])
        score += 30 * levels[tr][tc]

    # Piccolo ordinamento stabile per rendere il bot deterministico.
    score += (fr * 11 + fc * 7 + tr * 5 + tc)
    return score


def _order_moves(game, state, moves, root_player, tt_move=None, ply=0):
    if not moves:
        return moves

    def key(m):
        score = _move_points(game, state, m, root_player)
        if tt_move is not None and m == tt_move:
            score += 10_000_000
        if m in KILLERS.get(ply, []):
            score += 450_000
        score += HISTORY.get(m, 0)
        return score

    return sorted(moves, key=key, reverse=True)


def _threatened_squares(capture_moves):
    targets = set()
    for m in capture_moves:
        if _is_capture(m):
            try:
                targets.add(m[1])
            except Exception:
                pass
    return targets


def evaluate(game, state, root_player):
    key = (root_player, _board_key(state))
    cached = EVAL_CACHE.get(key)
    if cached is not None:
        return cached

    opponent = _opponent(game, root_player)

    winner = game.winner(state) if hasattr(game, "winner") else None
    if winner == root_player:
        return WIN_SCORE
    if winner == opponent:
        return -WIN_SCORE

    my_pieces = _count(state, root_player)
    opp_pieces = _count(state, opponent)
    total_pieces = my_pieces + opp_pieces

    # In finale ogni pezzo pesa ancora di più: un singolo errore decide la partita.
    material_weight = W_MATERIAL + max(0, 20 - total_pieces) * 420
    material = material_weight * (my_pieces - opp_pieces)

    my_moves = _actions_for(game, state, root_player)
    opp_moves = _actions_for(game, state, opponent)
    my_caps = [m for m in my_moves if _is_capture(m)]
    opp_caps = [m for m in opp_moves if _is_capture(m)]

    mobility = W_MOBILITY * (len(my_moves) - len(opp_moves))
    capture_mobility = W_CAPTURE_MOBILITY * (len(my_caps) - len(opp_caps))

    # Minacce: se un nostro pezzo è destinazione di una cattura avversaria, è un grosso rischio.
    my_threatened = 0
    opp_threatened = 0
    opp_targets = _threatened_squares(opp_caps)
    my_targets = _threatened_squares(my_caps)

    levels = _levels(game, state.size)
    outer = 0
    center_danger = 0

    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is None:
                continue
            lvl = levels[r][c]

            # Quadratico leggero: il bordo/corner vale più di un semplice +1 livello.
            pos = lvl * lvl
            central_penalty = max(0, 4 - lvl)  # livelli 1-3 sono più esposti

            if piece == root_player:
                outer += pos
                center_danger -= central_penalty * central_penalty
                if (r, c) in opp_targets:
                    my_threatened += 1
            else:
                outer -= pos
                center_danger += central_penalty * central_penalty
                if (r, c) in my_targets:
                    opp_threatened += 1

    position = W_OUTER_LEVEL * outer + W_CENTER_DANGER * center_danger
    threats = W_THREATENED * (opp_threatened - my_threatened)

    # Piccolo bonus di tempo/iniziativa: nelle posizioni pari preferisco avere il tratto.
    tempo = W_TURN if state.to_move == root_player else -W_TURN

    score = material + capture_mobility + mobility + position + threats + tempo
    EVAL_CACHE[key] = score
    return score


def alphabeta(game, state, depth, alpha, beta, root_player, deadline, ply=0):
    _check(deadline)

    opponent = _opponent(game, root_player)
    winner = game.winner(state) if hasattr(game, "winner") else None
    if winner == root_player:
        return WIN_SCORE + depth, None
    if winner == opponent:
        return -WIN_SCORE - depth, None

    if depth <= 0:
        return evaluate(game, state, root_player), None

    moves = game.actions(state)

    # Regola del PDF: se non hai mosse, non perdi; salti il turno.
    # Questo è il punto che molti bot sbagliano.
    if not moves:
        try:
            passed = game.pass_turn(state)
            return alphabeta(game, passed, depth - 1, alpha, beta, root_player, deadline, ply + 1)
        except Exception:
            return evaluate(game, state, root_player), None

    key = _board_key(state)
    alpha_orig, beta_orig = alpha, beta
    entry = TT.get(key)
    tt_move = None

    if entry is not None:
        e_depth, e_score, e_flag, e_move = entry
        tt_move = e_move
        if e_depth >= depth:
            if e_flag == "EXACT":
                return e_score, e_move
            if e_flag == "LOWER":
                alpha = max(alpha, e_score)
            elif e_flag == "UPPER":
                beta = min(beta, e_score)
            if alpha >= beta:
                return e_score, e_move

    maximizing = (state.to_move == root_player)
    ordered = _order_moves(game, state, moves, root_player, tt_move=tt_move, ply=ply)
    best_move = ordered[0]

    if maximizing:
        value = -INF
        for move in ordered:
            child = game.result(state, move)
            child_score, _ = alphabeta(game, child, depth - 1, alpha, beta, root_player, deadline, ply + 1)
            if child_score > value:
                value = child_score
                best_move = move
            alpha = max(alpha, value)
            if alpha >= beta:
                if not _is_capture(move):
                    killers = KILLERS[ply]
                    if move not in killers:
                        killers.insert(0, move)
                        del killers[2:]
                    HISTORY[move] += depth * depth
                break
    else:
        value = INF
        for move in ordered:
            child = game.result(state, move)
            child_score, _ = alphabeta(game, child, depth - 1, alpha, beta, root_player, deadline, ply + 1)
            if child_score < value:
                value = child_score
                best_move = move
            beta = min(beta, value)
            if alpha >= beta:
                if not _is_capture(move):
                    killers = KILLERS[ply]
                    if move not in killers:
                        killers.insert(0, move)
                        del killers[2:]
                    HISTORY[move] += depth * depth
                break

    if value <= alpha_orig:
        flag = "UPPER"
    elif value >= beta_orig:
        flag = "LOWER"
    else:
        flag = "EXACT"

    # Limite molto semplice per evitare crescita eccessiva.
    if len(TT) < 250_000:
        TT[key] = (depth, value, flag, best_move)

    return value, best_move


def playerStrategy(game, state, timeout=3):
    """Funzione richiesta dalla competizione."""
    legal_moves = game.actions(state)
    if not legal_moves:
        return None
    if len(legal_moves) == 1:
        return legal_moves[0]

    # Cache per turno: evita memoria infinita e risultati vecchi.
    TT.clear()
    EVAL_CACHE.clear()
    KILLERS.clear()
    HISTORY.clear()

    root_player = state.to_move
    deadline = _now() + max(0.05, float(timeout) - SAFETY_MARGIN)

    # Fallback intelligente immediato: non rischiamo mai una mossa non valida.
    ordered = _order_moves(game, state, legal_moves, root_player)
    best_move = ordered[0]
    best_score = -INF

    # Se una mossa vince subito, non pensare oltre.
    for move in ordered[:12]:
        try:
            child = game.result(state, move)
            if hasattr(game, "winner") and game.winner(child) == root_player:
                return move
        except Exception:
            pass

    # Iterative deepening: conserva sempre l'ultima profondità completata.
    for depth in range(1, MAX_DEPTH + 1):
        try:
            score, candidate = alphabeta(
                game, state, depth, -INF, INF, root_player, deadline, 0
            )
            if candidate in legal_moves:
                best_move = candidate
                best_score = score

            # Se troviamo una vittoria forzata, fermiamoci: aumentare profondità non serve.
            if best_score > WIN_SCORE // 2:
                break
        except SearchTimeout:
            break
        except Exception:
            # In competizione è meglio restituire una mossa legale che far scegliere random al main.
            break

    if best_move in legal_moves:
        return best_move
    return ordered[0]