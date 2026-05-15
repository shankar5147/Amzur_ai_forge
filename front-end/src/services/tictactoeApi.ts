import type { TicTacToeGameState } from "../types/chat";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function createNewGame(
  difficulty: string = "hard",
): Promise<TicTacToeGameState> {
  const resp = await fetch(`${API_BASE_URL}/api/tictactoe/new`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ difficulty }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

export async function makeMove(
  gameId: string,
  position: number,
): Promise<TicTacToeGameState> {
  const resp = await fetch(`${API_BASE_URL}/api/tictactoe/${gameId}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ position }),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

export async function getGameState(
  gameId: string,
): Promise<TicTacToeGameState> {
  const resp = await fetch(`${API_BASE_URL}/api/tictactoe/${gameId}`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

export async function abandonGame(gameId: string): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/tictactoe/${gameId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!resp.ok) throw new Error(await resp.text());
}
