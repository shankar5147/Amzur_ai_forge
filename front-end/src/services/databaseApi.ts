import type {
  DatabaseConnection,
  DatabaseConnectionCreate,
  DatabaseConnectionListResponse,
  DatabaseQueryHistory,
  DatabaseQueryRequest,
  DatabaseQueryResponse,
} from "../types/chat";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? "Request failed.");
  }
  return (await response.json()) as T;
}

// --- Database Connections ---

export async function createDatabaseConnection(
  payload: DatabaseConnectionCreate,
): Promise<DatabaseConnection> {
  const response = await fetch(`${API_BASE_URL}/api/database/connections`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  return handleResponse<DatabaseConnection>(response);
}

export async function listDatabaseConnections(): Promise<DatabaseConnectionListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/database/connections`, {
    method: "GET",
    headers: { ...getAuthHeaders() },
  });
  return handleResponse<DatabaseConnectionListResponse>(response);
}

export async function deleteDatabaseConnection(
  connectionId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/database/connections/${connectionId}`,
    {
      method: "DELETE",
      headers: { ...getAuthHeaders() },
    },
  );
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? "Failed to delete connection.");
  }
}

export async function testDatabaseConnection(
  connectionId: string,
): Promise<{ status: string }> {
  const response = await fetch(
    `${API_BASE_URL}/api/database/connections/${connectionId}/test`,
    {
      method: "POST",
      headers: { ...getAuthHeaders() },
    },
  );
  return handleResponse<{ status: string }>(response);
}

// --- Database Queries ---

export async function executeDatabaseQuery(
  payload: DatabaseQueryRequest,
): Promise<DatabaseQueryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/database/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  return handleResponse<DatabaseQueryResponse>(response);
}

export async function executeDirectQuery(
  naturalLanguageQuery: string,
): Promise<DatabaseQueryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/database/direct-query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ natural_language_query: naturalLanguageQuery }),
  });
  return handleResponse<DatabaseQueryResponse>(response);
}

export async function getDatabaseQueryHistory(
  connectionId: string,
): Promise<DatabaseQueryHistory[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/database/queries/${connectionId}`,
    {
      method: "GET",
      headers: { ...getAuthHeaders() },
    },
  );
  return handleResponse<DatabaseQueryHistory[]>(response);
}
