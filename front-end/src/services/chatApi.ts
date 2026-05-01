import type {
  AuthResponse,
  ChatHistoryResponse,
  ChatRequest,
  ChatResponse,
  GoogleAuthRequest,
  LoginRequest,
  SignupRequest,
  Thread,
  ThreadCreate,
  ThreadListResponse,
  ThreadUpdate,
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

// --- Auth ---

export async function signup(payload: SignupRequest): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<AuthResponse>(response);
}

export async function login(payload: LoginRequest): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<AuthResponse>(response);
}

export async function googleLogin(
  payload: GoogleAuthRequest,
): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<AuthResponse>(response);
}

// --- Threads ---

export async function getThreads(): Promise<ThreadListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/threads`, {
    method: "GET",
    headers: { ...getAuthHeaders() },
  });
  return handleResponse<ThreadListResponse>(response);
}

export async function createThread(payload?: ThreadCreate): Promise<Thread> {
  const response = await fetch(`${API_BASE_URL}/api/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(payload ?? {}),
  });
  return handleResponse<Thread>(response);
}

export async function updateThread(
  threadId: string,
  payload: ThreadUpdate,
): Promise<Thread> {
  const response = await fetch(`${API_BASE_URL}/api/threads/${threadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(payload),
  });
  return handleResponse<Thread>(response);
}

export async function deleteThread(threadId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/threads/${threadId}`, {
    method: "DELETE",
    headers: { ...getAuthHeaders() },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? "Failed to delete thread.");
  }
}

// --- Chat ---

export async function sendMessage(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<ChatResponse>(response);
}

export async function getChatHistory(
  threadId: string,
): Promise<ChatHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat/history/${threadId}`, {
    method: "GET",
    headers: {
      ...getAuthHeaders(),
    },
  });
  return handleResponse<ChatHistoryResponse>(response);
}
