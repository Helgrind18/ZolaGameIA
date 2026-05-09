import math
import time
import json
import os

SAFETY_MARGIN = 0.08
MAX_DEPTH = 20
WIN_SCORE = 100_000

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

WEIGHTS_FILE = os.path.join(SCRIPT_DIR, "weights_rl.json")
LEARNING_RATE = 1e-7


class SearchTimeout(Exception):
    pass


def _check_timeout(deadline: float) -> None:
    if time.perf_counter() >= deadline:
        raise SearchTimeout


# --- GESTIONE DEI PESI ---
def load_weights():
    if os.path.exists(WEIGHTS_FILE):
        try:
            with open(WEIGHTS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass  
    return {"piece": 1000.0, "mobility": 5.0, "border": 10.0}


def save_weights(weights):
    """Salva i pesi aggiornati nel file JSON."""
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=4)


# --- ESTRAZIONE FEATURES E VALUTAZIONE ---
def get_features(game, state, root_player):
    """Calcola le caratteristiche (features) numeriche della board."""
    opponent = game.opponent(root_player)

    # Feature 1: Materiale (pezzi)
    my_pieces = state.count(root_player)
    opp_pieces = state.count(opponent)
    piece_feat = my_pieces - opp_pieces

    # Feature 2: Mobilità
    my_moves = game._actions_for_player(state, root_player)
    opp_moves = game._actions_for_player(state, opponent)
    mobility_feat = len(my_moves) - len(opp_moves)

    # Feature 3: Controllo del bordo/centro
    border_feat = 0
    levels = game.get_all_distance_levels()

    for r in range(state.size):
        for c in range(state.size):
            piece = state.board[r][c]
            if piece is None:
                continue
            pos_value = levels[r][c]
            if piece == root_player:
                border_feat += pos_value
            else:
                border_feat -= pos_value

    return {"piece": piece_feat, "mobility": mobility_feat, "border": border_feat}


def evaluate_state(game, state, root_player, weights):
    """Valuta lo stato usando i pesi dinamici."""
    winner = game.winner(state)
    opponent = game.opponent(root_player)

    if winner == root_player:
        return WIN_SCORE
    if winner == opponent:
        return -WIN_SCORE
    if winner is not None:
        return 0

    features = get_features(game, state, root_player)

    # Valore = (Peso1 * Feature1) + (Peso2 * Feature2) + (Peso3 * Feature3)
    score = (weights["piece"] * features["piece"]) + \
            (weights["mobility"] * features["mobility"]) + \
            (weights["border"] * features["border"])

    return score


# --- ORDINAMENTO MOSSE ---
def _move_order_key(move):
    (fr, fc), (tr, tc), is_capture = move
    return (1 if is_capture else 0, -fr, -fc, -tr, -tc)


def order_moves(legal_moves):
    return sorted(legal_moves, key=_move_order_key, reverse=True)


# --- RICERCA ALPHA-BETA ---
def alphabeta(game, state, depth, alpha, beta, maximizing_player, root_player, deadline, weights):
    """Aggiunto parametro 'weights' da passare a evaluate_state"""
    _check_timeout(deadline)

    legal_moves = game.actions(state)

    if depth == 0 or game.is_terminal(state) or not legal_moves:
        return evaluate_state(game, state, root_player, weights), None

    legal_moves = order_moves(legal_moves)
    best_move = legal_moves[0]

    if maximizing_player:
        value = -math.inf
        for move in legal_moves:
            _check_timeout(deadline)
            child_state = game.result(state, move)
            child_value, _ = alphabeta(
                game, child_state, depth - 1, alpha, beta, False, root_player, deadline, weights
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
            game, child_state, depth - 1, alpha, beta, True, root_player, deadline, weights
        )

        if child_value < value:
            value = child_value
            best_move = move

        beta = min(beta, value)
        if alpha >= beta:
            break

    return value, best_move


# --- LOGICA DEL GIOCATORE ---
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

    # 1. Carichiamo i pesi attuali
    weights = load_weights()
    best_value_found = 0

    for depth in range(1, MAX_DEPTH + 1):
        try:
            val, candidate = alphabeta(
                game,
                state,
                depth,
                -math.inf,
                math.inf,
                True,
                root_player,
                deadline,
                weights  # <-- Passiamo i pesi
            )
            if candidate in legal_moves:
                best_move = candidate
                best_value_found = val  # <-- Salviamo il valore migliore trovato finora
        except SearchTimeout:
            break
        except Exception:
            break

    if best_move not in legal_moves:
        best_move = ordered_legal_moves[0]

    # --- 2. AGGIORNAMENTO DEI PESI (TD-LEARNING) ---
    # Confrontiamo la valutazione "statica" della board attuale con la valutazione "profonda" trovata dall'albero

    # Evitiamo di sballare i pesi se la mossa porta a una vittoria/sconfitta immediata (punteggi enormi)
    if abs(best_value_found) < (WIN_SCORE * 0.9):
        current_features = get_features(game, state, root_player)

        # Valore predetto prima di esplorare l'albero
        predicted_value = evaluate_state(game, state, root_player, weights)

        # Errore (Delta) = Valore "vero" (secondo l'albero profondo) - Valore predetto
        error_delta = best_value_found - predicted_value

        # Aggiorniamo ogni singolo peso proporzionalmente al suo contributo (la sua feature)
        for key in weights:
            # Formula: Nuovo_Peso = Vecchio_Peso + (Learning_Rate * Errore * Feature_Corrispondente)
            weights[key] += LEARNING_RATE * error_delta * current_features[key]

        # Salviamo i nuovi pesi
        save_weights(weights)

    return best_move