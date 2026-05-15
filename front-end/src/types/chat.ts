export type MessageRole = "user" | "assistant";

export interface Attachment {
  id: string;
  thread_id: string;
  message_id: string | null;
  file_name: string;
  mime_type: string;
  file_path: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  created_at?: string;
  attachments?: Attachment[];
}

export interface ChatRequest {
  message?: string | null;
  thread_id?: string | null;
  attachment_ids?: string[];
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
  attachments: Attachment[];
}

export interface ChatHistoryResponse {
  messages: MessageOut[];
}

export interface GeneratedImage {
  id: string;
  user_id: string;
  thread_id: string;
  prompt: string;
  image_url: string;
  created_at: string;
}

export interface ImageGenerationRequest {
  prompt: string;
  thread_id?: string | null;
  message?: string | null;
}

export interface ImageGenerationResponse {
  thread_id: string;
  user_message: MessageOut;
  assistant_message: MessageOut;
  image: GeneratedImage;
}

export interface UploadAttachmentsResponse {
  attachments: Attachment[];
}

export interface AttachmentPreview {
  attachment_id: string;
  file_name: string;
  mime_type: string;
  preview_type: "table" | "document" | "text" | "unsupported";
  columns: string[];
  rows: string[][];
  content: string | null;
  truncated: boolean;
}

export interface PendingAttachment {
  local_id: string;
  file_name: string;
  mime_type: string;
  file_size: number; // File size in bytes
  progress: number;
  status: "uploading" | "uploaded" | "error";
  error?: string;
  preview_url?: string;
  attachment_id?: string;
  local_preview?: string; // Local preview data URL for images/videos
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

// --- Database Query Types ---

export interface DatabaseConnection {
  id: string;
  name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  ssl_enabled: boolean;
  is_active: boolean;
  schema_info: string | null;
  created_at: string;
  updated_at: string;
}

export interface DatabaseConnectionCreate {
  name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  ssl_enabled: boolean;
}

export interface DatabaseConnectionListResponse {
  connections: DatabaseConnection[];
}

export interface DatabaseQueryRequest {
  connection_id: string;
  natural_language_query: string;
}

export interface DatabaseQueryResponse {
  query_id: string;
  generated_sql: string;
  result: Record<string, unknown>[] | null;
  error: string | null;
  execution_time_ms: number | null;
}

export interface DatabaseQueryHistory {
  id: string;
  connection_id: string;
  natural_language_query: string;
  generated_sql: string;
  result: string | null;
  error: string | null;
  execution_time_ms: number | null;
  created_at: string;
}

// --- Data Query (CSV / Excel / Google Sheets) Types ---

export interface DataFileUploadResponse {
  session_id: string;
  file_name: string;
  row_count: number;
  column_count: number;
  columns: string[];
  preview: Record<string, unknown>[];
  dtypes: Record<string, string>;
}

export interface GoogleSheetLoadRequest {
  sheet_url: string;
}

export interface GoogleSheetLoadResponse {
  session_id: string;
  sheet_title: string;
  row_count: number;
  column_count: number;
  columns: string[];
  preview: Record<string, unknown>[];
  dtypes: Record<string, string>;
}

export interface DataQueryRequest {
  session_id: string;
  question: string;
}

export interface DataQueryResponseType {
  session_id: string;
  question: string;
  answer: string;
  code: string | null;
}

export interface DataSessionInfo {
  session_id: string;
  file_name: string;
  row_count: number;
  column_count: number;
  columns: string[];
  dtypes: Record<string, string>;
}

export interface DataSessionListResponse {
  sessions: DataSessionInfo[];
}

// --- Research Digest Agent Types ---

export interface ResearchPaper {
  paper_id: string;
  title: string;
  authors: string[];
  abstract: string;
  published: string;
  updated: string;
  pdf_url: string;
  arxiv_url: string;
  categories: string[];
  relevance_score: number;
}

export interface PaperAnalysis {
  paper_id: string;
  title: string;
  authors: string[];
  published: string;
  arxiv_url: string;
  pdf_url: string;
  summary: string;
  key_findings: string[];
  methodology: string;
  relevance: "high" | "medium" | "low";
  limitations: string;
}

export interface ResearchStatusEvent {
  step: string;
  message: string;
}

export interface ResearchDoneEvent {
  papers_found?: number;
  papers_analyzed?: number;
}
