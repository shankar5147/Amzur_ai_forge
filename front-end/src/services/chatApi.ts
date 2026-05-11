import type {
  Attachment,
  AttachmentPreview,
  AuthResponse,
  ChatHistoryResponse,
  ImageGenerationRequest,
  ImageGenerationResponse,
  ChatRequest,
  ChatResponse,
  GoogleAuthRequest,
  LoginRequest,
  SignupRequest,
  Thread,
  ThreadCreate,
  ThreadListResponse,
  ThreadUpdate,
  UploadAttachmentsResponse,
} from "../types/chat";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

export function getAttachmentUrl(filePath: string): string {
  return `${API_BASE_URL}/uploads/${filePath}`;
}

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

export async function generateImage(
  payload: ImageGenerationRequest,
): Promise<ImageGenerationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/images/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<ImageGenerationResponse>(response);
}

export async function listThreadAttachments(
  threadId: string,
): Promise<UploadAttachmentsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/attachments/thread/${threadId}`,
    {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
    },
  );
  return handleResponse<UploadAttachmentsResponse>(response);
}

export async function getAttachmentPreview(
  attachmentId: string,
): Promise<AttachmentPreview> {
  const response = await fetch(
    `${API_BASE_URL}/api/attachments/${attachmentId}/preview`,
    {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
    },
  );
  return handleResponse<AttachmentPreview>(response);
}

export async function uploadAttachment(
  threadId: string,
  file: File,
  onProgress?: (value: number) => void,
): Promise<Attachment> {
  const token = localStorage.getItem("access_token");

  return new Promise<Attachment>((resolve, reject) => {
    const formData = new FormData();
    formData.append("thread_id", threadId);
    formData.append("files", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/attachments/upload`);
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during upload."));
    };

    xhr.onload = () => {
      let parsed: UploadAttachmentsResponse | { detail?: string } = {};
      try {
        parsed = JSON.parse(xhr.responseText || "{}");
      } catch {
        parsed = {};
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        const payload = parsed as UploadAttachmentsResponse;
        const attachment = payload.attachments[0];
        if (!attachment) {
          reject(
            new Error(
              "Upload completed but no attachment metadata was returned.",
            ),
          );
          return;
        }
        resolve(attachment);
        return;
      }

      reject(
        new Error((parsed as { detail?: string }).detail ?? "Upload failed."),
      );
    };

    xhr.send(formData);
  });
}

/**
 * Upload multiple files in a single batch request
 * Provides per-file progress tracking
 */
export async function uploadAttachmentsBatch(
  threadId: string,
  files: File[],
  onProgressUpdate?: (fileIndex: number, progress: number) => void,
): Promise<Attachment[]> {
  const token = localStorage.getItem("access_token");

  return new Promise<Attachment[]>((resolve, reject) => {
    const formData = new FormData();
    formData.append("thread_id", threadId);

    files.forEach((file) => {
      formData.append("files", file);
    });

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/attachments/upload`);
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgressUpdate) {
        const overallProgress = Math.round((event.loaded / event.total) * 100);
        // Distribute progress across all files
        files.forEach((_, index) => {
          onProgressUpdate(index, overallProgress);
        });
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during upload."));
    };

    xhr.onload = () => {
      let parsed: UploadAttachmentsResponse | { detail?: string } = {};
      try {
        parsed = JSON.parse(xhr.responseText || "{}");
      } catch {
        parsed = {};
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        const payload = parsed as UploadAttachmentsResponse;
        if (!payload.attachments || payload.attachments.length === 0) {
          reject(
            new Error("Upload completed but no attachments were returned."),
          );
          return;
        }
        resolve(payload.attachments);
        return;
      }

      reject(
        new Error((parsed as { detail?: string }).detail ?? "Upload failed."),
      );
    };

    xhr.send(formData);
  });
}
