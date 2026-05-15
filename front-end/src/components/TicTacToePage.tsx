import { useCallback, useState } from "react";

import { createNewGame, makeMove } from "../services/tictactoeApi";
import type { TicTacToeGameState } from "../types/chat";

type Difficulty = "easy" | "medium" | "hard";

const CELL_STYLES: Record<string, string> = {
  X: "text-blue-600",
  O: "text-rose-500",
  "": "",
};

const WINNING_COMBOS = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8],
  [0, 3, 6],
  [1, 4, 7],
  [2, 5, 8],
  [0, 4, 8],
  [2, 4, 6],
];

function getWinningCells(board: string[]): Set<number> {
  for (const [a, b, c] of WINNING_COMBOS) {
    if (board[a] && board[a] === board[b] && board[a] === board[c]) {
      return new Set([a, b, c]);
    }
  }
  return new Set();
}

export function TicTacToePage() {
  const [game, setGame] = useState<TicTacToeGameState | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty>("hard");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scores, setScores] = useState({ wins: 0, losses: 0, draws: 0 });

  const startGame = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const state = await createNewGame(difficulty);
      setGame(state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start game");
    } finally {
      setLoading(false);
    }
  }, [difficulty]);

  const handleCellClick = useCallback(
    async (position: number) => {
      if (!game || game.is_over || loading) return;
      if (game.board[position] !== "") return;
      if (game.current_turn !== "X") return;

      // Optimistic update: show human's X immediately
      const optimisticBoard = [...game.board];
      optimisticBoard[position] = "X";
      setGame((prev) =>
        prev ? { ...prev, board: optimisticBoard, current_turn: "O" } : prev,
      );

      setLoading(true);
      setError(null);
      try {
        const state = await makeMove(game.game_id, position);
        setGame(state);

        if (state.error) {
          setError(state.error);
        }

        // Update scores
        if (state.is_over) {
          setScores((prev) => ({
            wins: prev.wins + (state.winner === "X" ? 1 : 0),
            losses: prev.losses + (state.winner === "O" ? 1 : 0),
            draws: prev.draws + (state.is_draw ? 1 : 0),
          }));
        }
      } catch (err) {
        // Revert optimistic update on error
        setGame((prev) =>
          prev ? { ...prev, board: game.board, current_turn: "X" } : prev,
        );
        setError(err instanceof Error ? err.message : "Move failed");
      } finally {
        setLoading(false);
      }
    },
    [game, loading],
  );

  const resetGame = useCallback(() => {
    setGame(null);
    setError(null);
  }, []);

  const winningCells = game ? getWinningCells(game.board) : new Set<number>();

  // ── Landing / difficulty selection ──
  if (!game) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-8 p-4">
        <div className="text-center">
          <h2 className="mb-2 text-4xl font-bold text-gray-800">
            🎮 Tic Tac Toe
          </h2>
          <p className="text-lg text-gray-500">Play against an AI agent</p>
        </div>

        {/* Scoreboard */}
        {(scores.wins > 0 || scores.losses > 0 || scores.draws > 0) && (
          <div className="flex gap-6 rounded-xl bg-gray-50 px-8 py-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600">{scores.wins}</p>
              <p className="text-xs font-medium text-gray-500">Wins</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-400">{scores.draws}</p>
              <p className="text-xs font-medium text-gray-500">Draws</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-rose-500">
                {scores.losses}
              </p>
              <p className="text-xs font-medium text-gray-500">Losses</p>
            </div>
          </div>
        )}

        {/* Difficulty picker */}
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm font-medium text-gray-600">Select Difficulty</p>
          <div className="flex gap-2">
            {(["easy", "medium", "hard"] as const).map((d) => (
              <button
                key={d}
                onClick={() => setDifficulty(d)}
                className={`rounded-lg px-5 py-2.5 text-sm font-medium capitalize transition ${
                  difficulty === d
                    ? d === "easy"
                      ? "bg-green-600 text-white"
                      : d === "medium"
                        ? "bg-amber-500 text-white"
                        : "bg-rose-600 text-white"
                    : "border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-gray-400">
            {difficulty === "easy"
              ? "Agent plays random moves"
              : difficulty === "medium"
                ? "Agent mixes strategy with exploration"
                : "Agent uses AI to play optimally"}
          </p>
        </div>

        <button
          onClick={startGame}
          disabled={loading}
          className="rounded-xl bg-linear-to-r from-blue-600 to-violet-600 px-8 py-3 text-lg font-semibold text-white shadow-lg transition hover:shadow-xl disabled:opacity-50"
        >
          {loading ? "Starting…" : "Start Game"}
        </button>

        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    );
  }

  // ── Game board ──
  const statusText = game.is_over
    ? game.winner === "X"
      ? "🎉 You win!"
      : game.winner === "O"
        ? "😈 Agent wins!"
        : "🤝 It's a draw!"
    : loading
      ? "Agent is thinking…"
      : "Your turn (X)";

  const statusColor = game.is_over
    ? game.winner === "X"
      ? "text-blue-600"
      : game.winner === "O"
        ? "text-rose-500"
        : "text-amber-500"
    : "text-gray-700";

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 p-4">
      {/* Status bar */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-1.5">
          <span className="text-sm font-bold text-blue-600">X</span>
          <span className="text-xs text-gray-500">You</span>
        </div>
        <span className="text-xs text-gray-400">vs</span>
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 px-3 py-1.5">
          <span className="text-sm font-bold text-rose-500">O</span>
          <span className="text-xs text-gray-500">Agent</span>
        </div>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs capitalize text-gray-500">
          {game.difficulty}
        </span>
      </div>

      {/* Status message */}
      <p className={`text-lg font-semibold ${statusColor}`}>{statusText}</p>

      {/* Board */}
      <div className="grid grid-cols-3 gap-2">
        {game.board.map((cell, idx) => {
          const isWinCell = winningCells.has(idx);
          const canClick =
            !game.is_over &&
            !loading &&
            cell === "" &&
            game.current_turn === "X";

          return (
            <button
              key={idx}
              onClick={() => handleCellClick(idx)}
              disabled={!canClick}
              className={`flex h-24 w-24 items-center justify-center rounded-xl border-2 text-4xl font-bold transition-all sm:h-28 sm:w-28 sm:text-5xl ${
                isWinCell
                  ? "border-yellow-400 bg-yellow-50 shadow-lg shadow-yellow-200"
                  : cell
                    ? "border-gray-200 bg-gray-50"
                    : canClick
                      ? "border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50 hover:shadow-md"
                      : "border-gray-100 bg-gray-50"
              } ${CELL_STYLES[cell]} disabled:cursor-default`}
            >
              {cell ||
                (canClick ? (
                  <span className="text-xl text-gray-200">·</span>
                ) : (
                  ""
                ))}
            </button>
          );
        })}
      </div>

      {/* Agent reasoning */}
      {game.agent_reasoning && (
        <div className="max-w-sm rounded-lg bg-gray-50 px-4 py-2.5 text-center">
          <p className="text-xs font-medium text-gray-400">Agent's reasoning</p>
          <p className="mt-0.5 text-sm text-gray-600">{game.agent_reasoning}</p>
        </div>
      )}

      {/* Error */}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Actions */}
      <div className="flex gap-3">
        {game.is_over && (
          <button
            onClick={startGame}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            Play Again
          </button>
        )}
        <button
          onClick={resetGame}
          className="rounded-lg border border-gray-200 px-6 py-2.5 text-sm font-medium text-gray-600 transition hover:bg-gray-50"
        >
          {game.is_over ? "Change Difficulty" : "Quit"}
        </button>
      </div>

      {/* Scoreboard */}
      <div className="flex gap-6 rounded-xl bg-gray-50 px-8 py-3">
        <div className="text-center">
          <p className="text-xl font-bold text-blue-600">{scores.wins}</p>
          <p className="text-[10px] font-medium text-gray-500">Wins</p>
        </div>
        <div className="text-center">
          <p className="text-xl font-bold text-gray-400">{scores.draws}</p>
          <p className="text-[10px] font-medium text-gray-500">Draws</p>
        </div>
        <div className="text-center">
          <p className="text-xl font-bold text-rose-500">{scores.losses}</p>
          <p className="text-[10px] font-medium text-gray-500">Losses</p>
        </div>
      </div>

      {/* Move history */}
      {game.move_history.length > 0 && (
        <details className="w-full max-w-sm">
          <summary className="cursor-pointer text-center text-xs text-gray-400 hover:text-gray-600">
            Move history ({game.move_history.length} moves)
          </summary>
          <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border border-gray-100 bg-white p-3">
            {game.move_history.map((m, i) => (
              <div
                key={i}
                className="flex items-center gap-2 border-b border-gray-50 py-1 last:border-0"
              >
                <span
                  className={`text-xs font-bold ${m.player === "X" ? "text-blue-600" : "text-rose-500"}`}
                >
                  {m.player}
                </span>
                <span className="text-xs text-gray-500">
                  → position {m.position}
                </span>
                {m.reasoning && (
                  <span className="ml-auto truncate text-xs italic text-gray-400">
                    {m.reasoning}
                  </span>
                )}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
