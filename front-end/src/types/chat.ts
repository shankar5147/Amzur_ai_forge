export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  created_at?: string;
}

export interface ChatRequest {
  message: string;
  thread_id?: string | null;
}

export interface ChatResponse {
  response: string;
  thread_id: string;
}

export interface MessageOut {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface ChatHistoryResponse {
  messages: MessageOut[];
}

// Thread types
export interface Thread {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ThreadListResponse {
  threads: Thread[];
}

export interface ThreadCreate {
  name?: string;
}

export interface ThreadUpdate {
  name: string;
}

// Auth types
export interface SignupRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface GoogleAuthRequest {
  credential: string;
}

export interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}
