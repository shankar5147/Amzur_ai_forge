"""Tic Tac Toe game API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.models.schemas import (
    TicTacToeGameState,
    TicTacToeMoveRequest,
    TicTacToeNewGameRequest,
)
from app.services.tictactoe_service import (
    create_game,
    delete_game,
    get_game,
    play_human_move,
)

router = APIRouter(prefix="/api/tictactoe", tags=["tictactoe"])


@router.post("/new", response_model=TicTacToeGameState)
async def new_game(
    body: TicTacToeNewGameRequest | None = None,
    _user=Depends(get_current_user),
) -> TicTacToeGameState:
    """Create a new Tic Tac Toe game."""
    difficulty = body.difficulty if body else "hard"
    game_id = str(uuid.uuid4())
    game = create_game(game_id, difficulty)
    return TicTacToeGameState(**game.to_dict(), agent_reasoning=None, error=None)


@router.post("/{game_id}/move", response_model=TicTacToeGameState)
async def make_move(
    game_id: str,
    body: TicTacToeMoveRequest,
    _user=Depends(get_current_user),
) -> TicTacToeGameState:
    """Human player makes a move; agent responds."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")

    result = await play_human_move(game, body.position)
    return TicTacToeGameState(**result)


@router.get("/{game_id}", response_model=TicTacToeGameState)
async def get_game_state(
    game_id: str,
    _user=Depends(get_current_user),
) -> TicTacToeGameState:
    """Get the current state of a game."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")
    return TicTacToeGameState(**game.to_dict(), agent_reasoning=None, error=None)


@router.delete("/{game_id}")
async def abandon_game(
    game_id: str,
    _user=Depends(get_current_user),
) -> dict[str, str]:
    """Delete / abandon a game."""
    delete_game(game_id)
    return {"status": "ok"}
