import type {
  DataFileUploadResponse,
  DataQueryResponseType,
  DataSessionListResponse,
  GoogleSheetLoadRequest,
  GoogleSheetLoadResponse,
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

// --- File Upload ---

export async function uploadDataFile(
  file: File,
): Promise<DataFileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/data-query/upload`, {
    method: "POST",
    headers: { ...getAuthHeaders() },
    body: formData,
  });
  return handleResponse<DataFileUploadResponse>(response);
}

// --- Google Sheets ---

export async function loadGoogleSheet(
  payload: GoogleSheetLoadRequest,
): Promise<GoogleSheetLoadResponse> {
  const response = await fetch(`${API_BASE_URL}/api/data-query/google-sheet`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  return handleResponse<GoogleSheetLoadResponse>(response);
}

// --- Ask Question ---

export async function askDataQuestion(
  sessionId: string,
  question: string,
): Promise<DataQueryResponseType> {
  const response = await fetch(`${API_BASE_URL}/api/data-query/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ session_id: sessionId, question }),
  });
  return handleResponse<DataQueryResponseType>(response);
}

// --- Sessions ---

export async function listDataSessions(): Promise<DataSessionListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/data-query/sessions`, {
    method: "GET",
    headers: { ...getAuthHeaders() },
  });
  return handleResponse<DataSessionListResponse>(response);
}

export async function deleteDataSession(sessionId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/data-query/sessions/${sessionId}`,
    {
      method: "DELETE",
      headers: { ...getAuthHeaders() },
    },
  );
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? "Failed to delete session.");
  }
}
