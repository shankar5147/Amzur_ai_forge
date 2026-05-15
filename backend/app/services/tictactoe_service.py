"""
Tic Tac Toe agent service.

Uses an LLM to play as the opponent ('O') against the human player ('X').
Falls back to a minimax-based optimal strategy if the LLM response is invalid.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Board representation: list of 9 cells, each "" (empty), "X" (human), or "O" (agent)
EMPTY = ""
HUMAN = "X"
AGENT = "O"

WINNING_COMBOS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
    (0, 4, 8), (2, 4, 6),              # diagonals
]


# ---------------------------------------------------------------------------
# Game logic helpers
# ---------------------------------------------------------------------------

def check_winner(board: list[str]) -> str | None:
    """Return 'X', 'O', or None."""
    for a, b, c in WINNING_COMBOS:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def is_draw(board: list[str]) -> bool:
    return all(cell != EMPTY for cell in board) and check_winner(board) is None


def available_moves(board: list[str]) -> list[int]:
    return [i for i, cell in enumerate(board) if cell == EMPTY]


def board_to_display(board: list[str]) -> str:
    """Pretty-print board for the LLM prompt."""
    symbols = [cell if cell else str(i) for i, cell in enumerate(board)]
    return (
        f" {symbols[0]} | {symbols[1]} | {symbols[2]} \n"
        f"---+---+---\n"
        f" {symbols[3]} | {symbols[4]} | {symbols[5]} \n"
        f"---+---+---\n"
        f" {symbols[6]} | {symbols[7]} | {symbols[8]} "
    )


# ---------------------------------------------------------------------------
# Minimax fallback — guarantees optimal play
# ---------------------------------------------------------------------------

def _minimax(board: list[str], is_maximizing: bool) -> int:
    """Return score: +10 for O win, -10 for X win, 0 for draw."""
    winner = check_winner(board)
    if winner == AGENT:
        return 10
    if winner == HUMAN:
        return -10
    if not available_moves(board):
        return 0

    if is_maximizing:
        best = -100
        for move in available_moves(board):
            board[move] = AGENT
            best = max(best, _minimax(board, False))
            board[move] = EMPTY
        return best
    else:
        best = 100
        for move in available_moves(board):
            board[move] = HUMAN
            best = min(best, _minimax(board, True))
            board[move] = EMPTY
        return best


def minimax_move(board: list[str]) -> int:
    """Pick the optimal move for the agent (O) using minimax."""
    best_score = -100
    best_move = available_moves(board)[0]
    for move in available_moves(board):
        board[move] = AGENT
        score = _minimax(board, False)
        board[move] = EMPTY
        if score > best_score:
            best_score = score
            best_move = move
    return best_move


# ---------------------------------------------------------------------------
# LLM-based agent move
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        openai_api_key=settings.litellm_virtual_key or "unused",
        openai_api_base=settings.litellm_proxy_url,
        model=settings.litellm_model,
        temperature=0.3,
        max_tokens=200,
        default_headers={
            "x-litellm-user": settings.litellm_user_id,
            "x-litellm-department": settings.litellm_department,
            "x-litellm-environment": settings.litellm_environment,
        },
    )


SYSTEM_PROMPT = (
    "You are a Tic Tac Toe AI agent playing as 'O' against a human who is 'X'.\n"
    "The board positions are numbered 0-8:\n"
    " 0 | 1 | 2\n"
    "---+---+---\n"
    " 3 | 4 | 5\n"
    "---+---+---\n"
    " 6 | 7 | 8\n\n"
    "Given the current board state, choose the best move to WIN or DRAW.\n"
    "Think strategically: block the opponent if they're about to win, "
    "take the center or corners when advantageous.\n\n"
    "Respond with ONLY a JSON object:\n"
    '{"move": <position_number>, "reasoning": "<brief explanation>"}\n\n'
    "RULES:\n"
    "- You MUST pick an empty position.\n"
    "- Return ONLY valid JSON, nothing else."
)


async def get_agent_move(board: list[str]) -> dict[str, Any]:
    """
    Ask the LLM to pick a move. Falls back to minimax if the LLM gives
    an invalid move.
    """
    moves = available_moves(board)
    if not moves:
        return {"move": -1, "reasoning": "No moves available."}

    llm = _get_llm()
    display = board_to_display(board)
    user_msg = (
        f"Current board:\n{display}\n\n"
        f"Available positions: {moves}\n"
        f"Your move (O):"
    )

    try:
        resp = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        raw = resp.content.strip()

        # Strip markdown fences
        if "```" in raw:
            parts = raw.split("```")
            if len(parts) >= 3:
                inner = parts[1]
                if inner.startswith(("json", "JSON")):
                    inner = inner.split("\n", 1)[1] if "\n" in inner else inner
                raw = inner.strip()

        result = json.loads(raw)
        move = int(result.get("move", -1))
        reasoning = str(result.get("reasoning", ""))

        if move in moves:
            return {"move": move, "reasoning": reasoning}

        logger.warning("LLM chose invalid move %d, falling back to minimax", move)
    except Exception as exc:
        logger.warning("LLM move failed (%s), falling back to minimax", exc)

    # Fallback: minimax
    fallback = minimax_move(list(board))  # copy to avoid mutation
    return {"move": fallback, "reasoning": "Calculated optimal move."}


# ---------------------------------------------------------------------------
# Game state management (in-memory sessions)
# ---------------------------------------------------------------------------

class TicTacToeGame:
    """Represents one game session."""

    def __init__(self, game_id: str, difficulty: str = "hard") -> None:
        self.game_id = game_id
        self.board: list[str] = [EMPTY] * 9
        self.difficulty = difficulty
        self.current_turn = HUMAN  # Human goes first
        self.winner: str | None = None
        self.is_draw_state = False
        self.is_over = False
        self.move_history: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "board": self.board,
            "current_turn": self.current_turn,
            "winner": self.winner,
            "is_draw": self.is_draw_state,
            "is_over": self.is_over,
            "move_history": self.move_history,
            "difficulty": self.difficulty,
        }


# Simple in-memory store
_games: dict[str, TicTacToeGame] = {}


def create_game(game_id: str, difficulty: str = "hard") -> TicTacToeGame:
    game = TicTacToeGame(game_id, difficulty)
    _games[game_id] = game
    return game


def get_game(game_id: str) -> TicTacToeGame | None:
    return _games.get(game_id)


def delete_game(game_id: str) -> None:
    _games.pop(game_id, None)


async def play_human_move(game: TicTacToeGame, position: int) -> dict[str, Any]:
    """
    Process human's move, then get agent's response.
    Returns the full updated game state including agent's move info.
    """
    if game.is_over:
        return {**game.to_dict(), "error": "Game is already over."}

    if game.current_turn != HUMAN:
        return {**game.to_dict(), "error": "It's not your turn."}

    if position < 0 or position > 8 or game.board[position] != EMPTY:
        return {**game.to_dict(), "error": f"Invalid move: position {position} is not available."}

    # Human move
    game.board[position] = HUMAN
    game.move_history.append({"player": HUMAN, "position": position})

    # Check if human won
    winner = check_winner(game.board)
    if winner:
        game.winner = winner
        game.is_over = True
        return {**game.to_dict(), "agent_reasoning": None}

    # Check draw
    if is_draw(game.board):
        game.is_draw_state = True
        game.is_over = True
        return {**game.to_dict(), "agent_reasoning": None}

    # Agent's turn
    game.current_turn = AGENT

    if game.difficulty == "easy":
        moves = available_moves(game.board)
        agent_pos = random.choice(moves)
        reasoning = "Random move."
    elif game.difficulty == "medium":
        # 50% chance of optimal, 50% random
        if random.random() < 0.5:
            agent_pos = minimax_move(list(game.board))
            reasoning = "Calculated move."
        else:
            moves = available_moves(game.board)
            agent_pos = random.choice(moves)
            reasoning = "Exploratory move."
    else:
        # Hard: use LLM with minimax fallback
        result = await get_agent_move(game.board)
        agent_pos = result["move"]
        reasoning = result["reasoning"]

    game.board[agent_pos] = AGENT
    game.move_history.append({"player": AGENT, "position": agent_pos, "reasoning": reasoning})

    # Check if agent won
    winner = check_winner(game.board)
    if winner:
        game.winner = winner
        game.is_over = True

    # Check draw
    if is_draw(game.board):
        game.is_draw_state = True
        game.is_over = True

    game.current_turn = HUMAN
    return {**game.to_dict(), "agent_reasoning": reasoning}
