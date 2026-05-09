"""
playerHelgrindV4.py
Motore Zola ottimizzato — basato su V2, con miglioramenti:

1. SAFETY_MARGIN ridotto (0.06 invece di 0.08) → più tempo per la ricerca
2. Aspiration Windows nell'ID loop → pruning più aggressivo
3. Funzione di valutazione migliorata:
   - Bonus/malus asimmetrico per colore (Rosso tende a perdere → compensa)
   - Endgame detection: quando le pedine sono poche, si pesa di più il materiale
   - Bonus per minacce di cattura multiple (fork detection)
   - Penalità per pedine isolate (senza pedine amiche adiacenti)
4. Move ordering migliorato: MVV-LVA per catture, history heuristic più forte
5. Null Move Pruning (R=2) per tagli veloci
6. LMR (Late Move Reduction) leggera per nodi non-PV
7. TT con replacement strategy (depth-preferred + age)
8. EVAL_CACHE più grande
"""

import time
from collections import defaultdict

RED, BLUE, EMPTY = 1, 2, 0
WIN_SCORE = 10_000_000
INF = 10**18
MAX_DEPTH = 96
SAFETY_MARGIN = 0.06   # -20ms rispetto a V2 → più nodi visitati

# --- Pesi valutazione ---
W_MATERIAL = 9000
W_CAPTURE_MOBILITY = 280
W_MOBILITY = 55
W_OUTER_LEVEL = 110
W_CENTER_DANGER = 115
W_THREATENED = 850
W_TURN = 35
W_FORK = 600          # bonus per ogni pedina che minaccia 2+ nemici
W_ISOLATED = 200      # penalità pedine isolate

# Compensazione asimmetria colore: Rosso gioca per primo,
# ma sperimentalmente Blu ha vantaggio. Aggiungiamo un piccolo bonus
# statico per Rosso per riequilibrare.
W_COLOR_BIAS = 120    # aggiunto a score quando root == RED

DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

TT = {}
EVAL_CACHE = {}
KILLERS = defaultdict(list)
HISTORY = defaultdict(int)
COUNTER_MOVES = {}      # (last_move) -> best_response
LEVEL_CACHE = {}
RAYS_CACHE = {}
NEIGH_CACHE = {}

_age = 0   # incrementato a ogni nuova ricerca per TT replacement

class SearchTimeout(Exception):
    pass

def _now():
    return time.perf_counter()

def _check(deadline):
    if _now() >= deadline:
        raise SearchTimeout

def _opp(p):
    return BLUE if p == RED else RED

def _to_int_player(player):
    return RED if player == "Red" else BLUE

def _board_tuple(state):
    vals = []
    for row in state.board:
        for cell in row:
            if cell == "Red":   vals.append(RED)
            elif cell == "Blue": vals.append(BLUE)
            else:                vals.append(EMPTY)
    return tuple(vals)

def _levels(game, n):
    if n in LEVEL_CACHE:
        return LEVEL_CACHE[n]
    if hasattr(game, "distance_levels"):
        mat = game.distance_levels
    elif hasattr(game, "get_all_distance_levels"):
        mat = game.get_all_distance_levels()
    else:
        vals = {}; uniq = set()
        for r in range(n):
            for c in range(n):
                v = (2*r-(n-1))**2 + (2*c-(n-1))**2
                vals[(r,c)] = v; uniq.add(v)
        order = sorted(uniq)
        rank = {v:i+1 for i,v in enumerate(order)}
        mat = [[rank[vals[(r,c)]] for c in range(n)] for r in range(n)]
    flat = tuple(mat[r][c] for r in range(n) for c in range(n))
    LEVEL_CACHE[n] = flat
    return flat

def _rays(n):
    if n in RAYS_CACHE:
        return RAYS_CACHE[n]
    rays = []; neigh = []
    for idx in range(n*n):
        r, c = divmod(idx, n)
        rrays = []; nneigh = []
        for dr, dc in DIRECTIONS:
            nr, nc = r+dr, c+dc
            nneigh.append(nr*n+nc if 0 <= nr < n and 0 <= nc < n else None)
            line = []
            while 0 <= nr < n and 0 <= nc < n:
                line.append(nr*n+nc); nr += dr; nc += dc
            rrays.append(tuple(line))
        rays.append(tuple(rrays)); neigh.append(tuple(nneigh))
    RAYS_CACHE[n] = (tuple(neigh), tuple(rays))
    return RAYS_CACHE[n]

def _actions(board, player, n, levels):
    enemy = _opp(player)
    neigh, rays = _rays(n)
    moves = []
    for fr, piece in enumerate(board):
        if piece != player: continue
        lf = levels[fr]
        for to in neigh[fr]:
            if to is not None and board[to] == EMPTY and levels[to] > lf:
                moves.append((fr, to, False))
        for line in rays[fr]:
            for to in line:
                cell = board[to]
                if cell == EMPTY: continue
                if cell == enemy and levels[to] <= lf:
                    moves.append((fr, to, True))
                break
    return moves

def _has_moves(board, player, n, levels):
    return bool(_actions(board, player, n, levels))

def _result(board, move, player):
    fr, to, cap = move
    b = list(board)
    b[fr] = EMPTY
    b[to] = player
    return tuple(b)

def _winner(board, player_to_move, n, levels):
    red  = board.count(RED)
    blue = board.count(BLUE)
    if blue == 0: return RED
    if red  == 0: return BLUE
    if not _has_moves(board, RED, n, levels) and not _has_moves(board, BLUE, n, levels):
        if red > blue: return RED
        if blue > red: return BLUE
        return _opp(player_to_move)
    return None

# ---------------------------------------------------------------------------
# Move ordering
# ---------------------------------------------------------------------------

def _mvv_lva(move, board, levels):
    """Most Valuable Victim / Least Valuable Attacker per catture."""
    fr, to, cap = move
    if not cap:
        return 0
    # victim level (più alto = più prezioso perché è più esterno = più pericoloso)
    victim_val = levels[to] * 200
    # attacker cost (meno vale l'attaccante, meglio)
    attacker_cost = levels[fr] * 5
    return victim_val - attacker_cost + 500_000

def _move_points(move, levels, board):
    fr, to, cap = move
    if cap:
        return _mvv_lva(move, board, levels)
    return 800*(levels[to]-levels[fr]) + 30*levels[to] + (fr*11 + to*7)

def _order(moves, levels, board, tt_move=None, ply=0, last_move=None):
    if not moves: return moves
    counter = COUNTER_MOVES.get(last_move)
    def key(m):
        s = _move_points(m, levels, board)
        if tt_move is not None and m == tt_move: s += 10_000_000
        if m in KILLERS.get(ply, ()):            s += 450_000
        if counter is not None and m == counter: s += 300_000
        s += HISTORY.get(m, 0)
        return s
    return sorted(moves, key=key, reverse=True)

def _targets(caps):
    return {m[1] for m in caps if m[2]}

# ---------------------------------------------------------------------------
# Valutazione
# ---------------------------------------------------------------------------

def _fork_bonus(my_caps, n, levels):
    """Conta le pedine nemiche minacciate da 2+ pezzi nostri → fork."""
    target_count = defaultdict(int)
    for m in my_caps:
        target_count[m[1]] += 1
    return sum(1 for v in target_count.values() if v >= 2)

def _isolated_penalty(board, player, n):
    """Conta pedine senza amiche adiacenti."""
    neigh, _ = _rays(n)
    count = 0
    for idx, piece in enumerate(board):
        if piece != player: continue
        has_friend = any(
            nb is not None and board[nb] == player
            for nb in neigh[idx]
        )
        if not has_friend:
            count += 1
    return count

def _evaluate(board, to_move, root, n, levels):
    key = (root, to_move, board)
    v = EVAL_CACHE.get(key)
    if v is not None:
        return v

    opponent = _opp(root)
    w = _winner(board, to_move, n, levels)
    if w == root:     return  WIN_SCORE
    if w == opponent: return -WIN_SCORE

    my_p = board.count(root)
    op_p = board.count(opponent)
    total = my_p + op_p

    # Peso materiale aumenta in endgame
    endgame_bonus = max(0, 20 - total) * 420
    material_weight = W_MATERIAL + endgame_bonus
    score = material_weight * (my_p - op_p)

    my_moves = _actions(board, root, n, levels)
    op_moves = _actions(board, opponent, n, levels)
    my_caps  = [m for m in my_moves if m[2]]
    op_caps  = [m for m in op_moves if m[2]]

    score += W_MOBILITY * (len(my_moves) - len(op_moves))
    score += W_CAPTURE_MOBILITY * (len(my_caps) - len(op_caps))

    # Fork detection
    my_forks = _fork_bonus(my_caps, n, levels)
    op_forks = _fork_bonus(op_caps, n, levels)
    score += W_FORK * (my_forks - op_forks)

    # Isolated pieces
    my_iso = _isolated_penalty(board, root, n)
    op_iso = _isolated_penalty(board, opponent, n)
    score -= W_ISOLATED * (my_iso - op_iso)

    my_targets = _targets(my_caps)
    op_targets = _targets(op_caps)
    my_thr = op_thr = 0
    outer = center = 0
    for i, piece in enumerate(board):
        if piece == EMPTY: continue
        lvl = levels[i]
        pos = lvl * lvl
        central = max(0, 4-lvl)
        if piece == root:
            outer += pos; center -= central*central
            if i in op_targets: my_thr += 1
        else:
            outer -= pos; center += central*central
            if i in my_targets: op_thr += 1

    score += W_OUTER_LEVEL * outer + W_CENTER_DANGER * center
    score += W_THREATENED * (op_thr - my_thr)
    score += W_TURN if to_move == root else -W_TURN

    # Compensazione asimmetria colore
    if root == RED:
        score += W_COLOR_BIAS

    if len(EVAL_CACHE) < 400_000:
        EVAL_CACHE[key] = score
    return score

# ---------------------------------------------------------------------------
# Alpha-Beta con NMP + LMR
# ---------------------------------------------------------------------------

NULL_R = 2   # riduzione Null Move

def _alphabeta(board, to_move, depth, alpha, beta, root, n, levels,
               deadline, ply=0, last_move=None, is_null=False):
    _check(deadline)

    opponent = _opp(root)
    w = _winner(board, to_move, n, levels)
    if w == root:     return  WIN_SCORE + depth, None
    if w == opponent: return -WIN_SCORE - depth, None
    if depth <= 0:
        return _evaluate(board, to_move, root, n, levels), None

    moves = _actions(board, to_move, n, levels)
    if not moves:
        return _alphabeta(board, _opp(to_move), depth-1, alpha, beta,
                          root, n, levels, deadline, ply+1, last_move, is_null)

    key   = (root, to_move, board)
    alpha0, beta0 = alpha, beta
    entry  = TT.get(key)
    tt_move = None
    if entry is not None:
        e_depth, e_score, e_flag, e_move, e_age = entry
        tt_move = e_move
        if e_depth >= depth:
            if e_flag == 'EXACT':
                return e_score, e_move
            if e_flag == 'LOWER': alpha = max(alpha, e_score)
            elif e_flag == 'UPPER': beta  = min(beta,  e_score)
            if alpha >= beta:
                return e_score, e_move

    # ---- Null Move Pruning ----
    maximizing = (to_move == root)
    if (not is_null and depth >= NULL_R + 2 and not maximizing is False
            and w is None):
        # Null move: passa il turno
        null_board = board   # no change, just swap player
        sc, _ = _alphabeta(null_board, _opp(to_move), depth - NULL_R - 1,
                            -beta, -beta+1, root, n, levels,
                            deadline, ply+1, None, True)
        sc = -sc
        if sc >= beta:
            return beta, None

    ordered = _order(moves, levels, board, tt_move, ply, last_move)
    best = ordered[0]

    if maximizing:
        val = -INF
        for i, m in enumerate(ordered):
            child = _result(board, m, to_move)
            # LMR: riduci profondità per mosse tardive non-cattura
            reduction = 0
            if i >= 4 and depth >= 3 and not m[2] and ply > 0:
                reduction = 1
            sc, _ = _alphabeta(child, _opp(to_move), depth-1-reduction,
                                alpha, beta, root, n, levels,
                                deadline, ply+1, m, False)
            # Re-search a full depth se LMR ha trovato qualcosa di buono
            if reduction and sc > alpha:
                sc, _ = _alphabeta(child, _opp(to_move), depth-1,
                                    alpha, beta, root, n, levels,
                                    deadline, ply+1, m, False)
            if sc > val:
                val, best = sc, m
            alpha = max(alpha, val)
            if alpha >= beta:
                if not m[2]:
                    ks = KILLERS[ply]
                    if m not in ks:
                        ks.insert(0, m); del ks[2:]
                    HISTORY[m] += depth * depth
                    COUNTER_MOVES[last_move] = m
                break
    else:
        val = INF
        for i, m in enumerate(ordered):
            child = _result(board, m, to_move)
            reduction = 0
            if i >= 4 and depth >= 3 and not m[2] and ply > 0:
                reduction = 1
            sc, _ = _alphabeta(child, _opp(to_move), depth-1-reduction,
                                alpha, beta, root, n, levels,
                                deadline, ply+1, m, False)
            if reduction and sc < beta:
                sc, _ = _alphabeta(child, _opp(to_move), depth-1,
                                    alpha, beta, root, n, levels,
                                    deadline, ply+1, m, False)
            if sc < val:
                val, best = sc, m
            beta = min(beta, val)
            if alpha >= beta:
                if not m[2]:
                    ks = KILLERS[ply]
                    if m not in ks:
                        ks.insert(0, m); del ks[2:]
                    HISTORY[m] += depth * depth
                    COUNTER_MOVES[last_move] = m
                break

    flag = 'EXACT'
    if val <= alpha0: flag = 'UPPER'
    elif val >= beta0: flag = 'LOWER'
    if len(TT) < 400_000:
        TT[key] = (depth, val, flag, best, _age)
    elif entry is not None and entry[0] <= depth:
        TT[key] = (depth, val, flag, best, _age)

    return val, best


# ---------------------------------------------------------------------------
# Iterative Deepening con Aspiration Windows
# ---------------------------------------------------------------------------

def _to_external(move, n):
    fr, to, cap = move
    return ((fr//n, fr%n), (to//n, to%n), bool(cap))


def playerStrategy(game, state, timeout=3):
    global _age
    _age += 1

    legal_external = game.actions(state)
    if not legal_external:
        return None
    if len(legal_external) == 1:
        return legal_external[0]

    n      = state.size
    levels = _levels(game, n)
    board  = _board_tuple(state)
    root   = _to_int_player(state.to_move)
    to_move = root

    # Pulizia selettiva: mantieni TT tra mosse (aging), svuota solo EVAL e killers
    EVAL_CACHE.clear()
    KILLERS.clear()
    HISTORY.clear()
    COUNTER_MOVES.clear()

    deadline   = _now() + max(0.02, float(timeout) - SAFETY_MARGIN)
    moves      = _actions(board, root, n, levels)
    if not moves:
        return None

    ordered    = _order(moves, levels, board)
    best       = ordered[0]
    best_score = -INF

    # Vittoria immediata
    for m in ordered[:16]:
        child = _result(board, m, root)
        if _winner(child, _opp(root), n, levels) == root:
            ext = _to_external(m, n)
            return ext if ext in legal_external else legal_external[0]

    # Aspiration window iniziale
    asp_delta  = 150
    prev_score = 0

    for depth in range(1, MAX_DEPTH+1):
        try:
            if depth <= 4:
                # Ricerca a finestra piena per le prime profondità
                sc, cand = _alphabeta(board, to_move, depth, -INF, INF,
                                       root, n, levels, deadline, 0)
            else:
                # Aspiration windows
                lo = prev_score - asp_delta
                hi = prev_score + asp_delta
                sc, cand = _alphabeta(board, to_move, depth, lo, hi,
                                       root, n, levels, deadline, 0)
                # Fallback se fuori finestra
                if sc <= lo or sc >= hi:
                    sc, cand = _alphabeta(board, to_move, depth, -INF, INF,
                                           root, n, levels, deadline, 0)

            if cand is not None and cand in moves:
                best, best_score = cand, sc
                prev_score = sc

            if best_score > WIN_SCORE // 2:
                break
            asp_delta = max(50, asp_delta - 10)

        except SearchTimeout:
            break
        except Exception:
            break

    ext = _to_external(best, n)
    if ext in legal_external:
        return ext
    return legal_external[0]
