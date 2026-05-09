"""
playerHelgrindV2.py
Motore Zola ottimizzato per torneo 8x8.

Diverso da playerHelgrind: dentro la ricerca non usa game.result()/game.actions(),
ma una rappresentazione compatta a tupla di 64 celle. Questo evita molte copie di
oggetti Board e permette di cercare più nodi nello stesso timeout.
"""

import time
from collections import defaultdict

RED, BLUE, EMPTY = 1, 2, 0
WIN_SCORE = 10_000_000
INF = 10**18
MAX_DEPTH = 96
SAFETY_MARGIN = 0.08

# Pesi empirici: più mobilità/posizione rispetto al vecchio Helgrind.
W_MATERIAL = 9000
W_CAPTURE_MOBILITY = 250
W_MOBILITY = 50
W_OUTER_LEVEL = 120
W_CENTER_DANGER = 120
W_THREATENED = 800
W_TURN = 30

DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

TT = {}
EVAL_CACHE = {}
KILLERS = defaultdict(list)
HISTORY = defaultdict(int)
LEVEL_CACHE = {}
RAYS_CACHE = {}

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

def _to_str_player(player):
    return "Red" if player == RED else "Blue"

def _board_tuple(state):
    vals = []
    for row in state.board:
        for cell in row:
            if cell == "Red": vals.append(RED)
            elif cell == "Blue": vals.append(BLUE)
            else: vals.append(EMPTY)
    return tuple(vals)

def _levels(game, n):
    if n in LEVEL_CACHE:
        return LEVEL_CACHE[n]
    if hasattr(game, "distance_levels"):
        mat = game.distance_levels
    elif hasattr(game, "get_all_distance_levels"):
        mat = game.get_all_distance_levels()
    else:
        vals = {}
        uniq = set()
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
    rays = []
    neigh = []
    for idx in range(n*n):
        r, c = divmod(idx, n)
        rrays = []
        nneigh = []
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n:
                nneigh.append(nr*n + nc)
            else:
                nneigh.append(None)
            line = []
            while 0 <= nr < n and 0 <= nc < n:
                line.append(nr*n + nc)
                nr += dr; nc += dc
            rrays.append(tuple(line))
        rays.append(tuple(rrays))
        neigh.append(tuple(nneigh))
    RAYS_CACHE[n] = (tuple(neigh), tuple(rays))
    return RAYS_CACHE[n]

def _actions(board, player, n, levels):
    enemy = _opp(player)
    neigh, rays = _rays(n)
    moves = []
    for fr, piece in enumerate(board):
        if piece != player:
            continue
        lf = levels[fr]
        # mosse non catturanti: adiacenti vuote verso esterno
        for to in neigh[fr]:
            if to is not None and board[to] == EMPTY and levels[to] > lf:
                moves.append((fr, to, False))
        # catture: prima pedina lungo ogni raggio, se nemica e non più esterna
        for line in rays[fr]:
            for to in line:
                cell = board[to]
                if cell == EMPTY:
                    continue
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
    red = board.count(RED)
    blue = board.count(BLUE)
    if blue == 0: return RED
    if red == 0: return BLUE
    # situazione teorica: nessuno può muovere
    if not _has_moves(board, RED, n, levels) and not _has_moves(board, BLUE, n, levels):
        if red > blue: return RED
        if blue > red: return BLUE
        return _opp(player_to_move)
    return None

def _is_capture(m):
    return m[2]

def _move_points(move, levels):
    fr, to, cap = move
    if cap:
        return 100000 + 550*levels[fr] - 75*levels[to] + (fr*11 + to*7)
    return 800*(levels[to]-levels[fr]) + 30*levels[to] + (fr*11 + to*7)

def _order(moves, levels, tt_move=None, ply=0):
    if not moves: return moves
    def key(m):
        s = _move_points(m, levels)
        if tt_move is not None and m == tt_move: s += 10_000_000
        if m in KILLERS.get(ply, ()): s += 450_000
        s += HISTORY.get(m, 0)
        return s
    return sorted(moves, key=key, reverse=True)

def _targets(caps):
    return {m[1] for m in caps if m[2]}

def _evaluate(board, to_move, root, n, levels):
    key = (root, to_move, board)
    v = EVAL_CACHE.get(key)
    if v is not None:
        return v
    opponent = _opp(root)
    w = _winner(board, to_move, n, levels)
    if w == root: return WIN_SCORE
    if w == opponent: return -WIN_SCORE

    my_p = board.count(root)
    op_p = board.count(opponent)
    total = my_p + op_p
    material_weight = W_MATERIAL + max(0, 20-total)*420
    score = material_weight * (my_p - op_p)

    my_moves = _actions(board, root, n, levels)
    op_moves = _actions(board, opponent, n, levels)
    my_caps = [m for m in my_moves if m[2]]
    op_caps = [m for m in op_moves if m[2]]
    score += W_MOBILITY * (len(my_moves) - len(op_moves))
    score += W_CAPTURE_MOBILITY * (len(my_caps) - len(op_caps))

    my_targets = _targets(my_caps)
    op_targets = _targets(op_caps)
    my_thr = op_thr = 0
    outer = 0
    center = 0
    for i, piece in enumerate(board):
        if piece == EMPTY: continue
        lvl = levels[i]
        pos = lvl * lvl
        central = max(0, 4-lvl)
        if piece == root:
            outer += pos
            center -= central*central
            if i in op_targets: my_thr += 1
        else:
            outer -= pos
            center += central*central
            if i in my_targets: op_thr += 1
    score += W_OUTER_LEVEL * outer + W_CENTER_DANGER * center
    score += W_THREATENED * (op_thr - my_thr)
    score += W_TURN if to_move == root else -W_TURN

    if len(EVAL_CACHE) < 250_000:
        EVAL_CACHE[key] = score
    return score

def _alphabeta(board, to_move, depth, alpha, beta, root, n, levels, deadline, ply=0):
    _check(deadline)
    opponent = _opp(root)
    w = _winner(board, to_move, n, levels)
    if w == root: return WIN_SCORE + depth, None
    if w == opponent: return -WIN_SCORE - depth, None
    if depth <= 0:
        return _evaluate(board, to_move, root, n, levels), None

    moves = _actions(board, to_move, n, levels)
    if not moves:
        return _alphabeta(board, _opp(to_move), depth-1, alpha, beta, root, n, levels, deadline, ply+1)

    key = (root, to_move, board)
    alpha0, beta0 = alpha, beta
    entry = TT.get(key)
    tt_move = None
    if entry is not None:
        e_depth, e_score, e_flag, e_move = entry
        tt_move = e_move
        if e_depth >= depth:
            if e_flag == 'EXACT': return e_score, e_move
            if e_flag == 'LOWER': alpha = max(alpha, e_score)
            elif e_flag == 'UPPER': beta = min(beta, e_score)
            if alpha >= beta: return e_score, e_move

    ordered = _order(moves, levels, tt_move, ply)
    best = ordered[0]
    maximizing = (to_move == root)
    if maximizing:
        val = -INF
        for m in ordered:
            child = _result(board, m, to_move)
            sc, _ = _alphabeta(child, _opp(to_move), depth-1, alpha, beta, root, n, levels, deadline, ply+1)
            if sc > val:
                val, best = sc, m
            alpha = max(alpha, val)
            if alpha >= beta:
                if not m[2]:
                    ks = KILLERS[ply]
                    if m not in ks:
                        ks.insert(0, m); del ks[2:]
                    HISTORY[m] += depth*depth
                break
    else:
        val = INF
        for m in ordered:
            child = _result(board, m, to_move)
            sc, _ = _alphabeta(child, _opp(to_move), depth-1, alpha, beta, root, n, levels, deadline, ply+1)
            if sc < val:
                val, best = sc, m
            beta = min(beta, val)
            if alpha >= beta:
                if not m[2]:
                    ks = KILLERS[ply]
                    if m not in ks:
                        ks.insert(0, m); del ks[2:]
                    HISTORY[m] += depth*depth
                break

    flag = 'EXACT'
    if val <= alpha0: flag = 'UPPER'
    elif val >= beta0: flag = 'LOWER'
    if len(TT) < 300_000:
        TT[key] = (depth, val, flag, best)
    return val, best

def _to_external(move, n):
    fr, to, cap = move
    return ((fr//n, fr % n), (to//n, to % n), bool(cap))

def playerStrategy(game, state, timeout=3):
    legal_external = game.actions(state)
    if not legal_external:
        return None
    if len(legal_external) == 1:
        return legal_external[0]

    n = state.size
    levels = _levels(game, n)
    board = _board_tuple(state)
    root = _to_int_player(state.to_move)
    to_move = root

    TT.clear(); EVAL_CACHE.clear(); KILLERS.clear(); HISTORY.clear()

    deadline = _now() + max(0.02, float(timeout) - SAFETY_MARGIN)
    moves = _actions(board, root, n, levels)
    if not moves:
        return None
    ordered = _order(moves, levels)
    best = ordered[0]
    best_score = -INF

    # Vittoria immediata.
    for m in ordered[:16]:
        child = _result(board, m, root)
        if _winner(child, _opp(root), n, levels) == root:
            ext = _to_external(m, n)
            return ext if ext in legal_external else legal_external[0]

    for depth in range(1, MAX_DEPTH+1):
        try:
            sc, cand = _alphabeta(board, to_move, depth, -INF, INF, root, n, levels, deadline, 0)
            if cand in moves:
                best, best_score = cand, sc
            if best_score > WIN_SCORE//2:
                break
        except SearchTimeout:
            break
        except Exception:
            break

    ext = _to_external(best, n)
    if ext in legal_external:
        return ext
    # Fallback ultra-difensivo: mai mossa illegale.
    return legal_external[0]
