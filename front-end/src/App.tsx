import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { ChatComposer } from "./components/ChatComposer";
import { ChatMessageList } from "./components/ChatMessageList";
import { LoginPage } from "./components/LoginPage";
import { ThreadSidebar } from "./components/ThreadSidebar";
import { useAuth } from "./context/AuthContext";
import {
  createThread,
  deleteThread,
  generateImage,
  getChatHistory,
  getThreads,
  sendMessage,
  uploadAttachment,
  uploadAttachmentsBatch,
  updateThread,
} from "./services/chatApi";
import { executeDirectQuery } from "./services/databaseApi";
import type {
  ChatMessage,
  DatabaseQueryResponse,
  PendingAttachment,
  Thread,
} from "./types/chat";

const IMAGE_INTENT_REGEX =
  /\b(generate|create|draw|design|render|make)\b.{0,60}\b(image|picture|photo|logo|art|illustration)\b/i;
const IMAGE_EDIT_INTENT_REGEX =
  /\b(change|modify|update|alter|make it|turn it|color|recolor|replace|add|remove)\b/i;

function isImageIntent(text: string): boolean {
  return IMAGE_INTENT_REGEX.test(text.trim());
}

function isImageEditIntent(text: string): boolean {
  return IMAGE_EDIT_INTENT_REGEX.test(text.trim());
}

function hasImageInConversation(messages: ChatMessage[]): boolean {
  return messages.some((message) =>
    message.attachments?.some((attachment) =>
      attachment.mime_type.toLowerCase().startsWith("image/"),
    ),
  );
}

function createMessage(
  role: ChatMessage["role"],
  content: string,
  attachments: ChatMessage["attachments"] = [],
): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    attachments,
  };
}

function ChatPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<
    PendingAttachment[]
  >([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [imageLoading, setImageLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [dbMode, setDbMode] = useState(false);
  const [dbLoading, setDbLoading] = useState(false);
  const loading = chatLoading || imageLoading || dbLoading;

  const clearPendingAttachments = useCallback(() => {
    setPendingAttachments((prev) => {
      for (const item of prev) {
        if (item.preview_url?.startsWith("blob:")) {
          URL.revokeObjectURL(item.preview_url);
        }
      }
      return [];
    });
  }, []);

  // Load threads on mount
  useEffect(() => {
    async function loadThreads() {
      try {
        const resp = await getThreads();
        setThreads(resp.threads);
        if (resp.threads.length > 0) {
          setActiveThreadId(resp.threads[0].id);
        }
      } catch {
        // ignore
      }
    }
    loadThreads();
  }, []);

  // Load messages when active thread changes
  useEffect(() => {
    if (!activeThreadId) {
      setMessages([
        createMessage(
          "assistant",
          `Hello${user?.full_name ? `, ${user.full_name}` : ""}! Start a new conversation or select one from the sidebar.`,
        ),
      ]);
      return;
    }

    async function loadMessages() {
      try {
        const history = await getChatHistory(activeThreadId!);
        if (history.messages.length > 0) {
          setMessages(
            history.messages.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              attachments: m.attachments,
            })),
          );
        } else {
          setMessages([
            createMessage("assistant", "How can I help you today?"),
          ]);
        }
      } catch {
        setMessages([
          createMessage("assistant", "Hello! How can I help you today?"),
        ]);
      }
    }
    loadMessages();
  }, [activeThreadId, user]);

  const handleNewThread = useCallback(() => {
    clearPendingAttachments();
    setActiveThreadId(null);
    setMessages([
      createMessage(
        "assistant",
        `Hello${user?.full_name ? `, ${user.full_name}` : ""}! How can I help you today?`,
      ),
    ]);
  }, [clearPendingAttachments, user]);

  const handleSelectThread = useCallback((threadId: string) => {
    setActiveThreadId(threadId);
  }, []);

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      try {
        await deleteThread(threadId);
        setThreads((prev) => prev.filter((t) => t.id !== threadId));
        if (activeThreadId === threadId) {
          setActiveThreadId(null);
        }
      } catch {
        // ignore
      }
    },
    [activeThreadId],
  );

  const handleRenameThread = useCallback(
    async (threadId: string, name: string) => {
      try {
        const updated = await updateThread(threadId, { name });
        setThreads((prev) =>
          prev.map((t) =>
            t.id === threadId ? { ...t, name: updated.name } : t,
          ),
        );
      } catch {
        // ignore
      }
    },
    [],
  );

  const handleGenerateImage = useCallback(
    async (promptInput?: string) => {
      const promptText = (promptInput ?? input).trim();
      const messageText = null;

      if (!promptText || loading) {
        return;
      }

      setError(null);
      setInput("");
      setImageLoading(true);

      try {
        const result = await generateImage({
          prompt: promptText,
          message: messageText,
          thread_id: activeThreadId,
        });
        clearPendingAttachments();

        setMessages((prev) => [
          ...prev,
          {
            id: result.user_message.id,
            role: result.user_message.role,
            content: result.user_message.content,
            attachments: result.user_message.attachments,
          },
          {
            id: result.assistant_message.id,
            role: result.assistant_message.role,
            content: result.assistant_message.content,
            attachments: result.assistant_message.attachments,
          },
        ]);

        if (!activeThreadId) {
          setActiveThreadId(result.thread_id);
        }

        const refreshedThreads = await getThreads();
        setThreads(refreshedThreads.threads);
      } catch (err) {
        const text =
          err instanceof Error ? err.message : "Image generation failed.";
        setError(text);
        setMessages((prev) => [
          ...prev,
          createMessage(
            "assistant",
            "I could not generate that image right now.",
          ),
        ]);
      } finally {
        setImageLoading(false);
      }
    },
    [activeThreadId, clearPendingAttachments, input, loading],
  );

  const handleDbQuery = useCallback(
    async (queryText?: string) => {
      const trimmed = (queryText ?? input).trim();
      if (!trimmed || loading) return;

      setError(null);
      setInput("");
      setDbLoading(true);

      const userMsg = createMessage("user", trimmed);
      setMessages((prev) => [...prev, userMsg]);

      try {
        const result: DatabaseQueryResponse = await executeDirectQuery(trimmed);

        // Build a markdown table from the results
        let content = "";
        if (
          result.result &&
          Array.isArray(result.result) &&
          result.result.length > 0
        ) {
          const cols = Object.keys(result.result[0]);
          content += `| ${cols.join(" | ")} |\n`;
          content += `| ${cols.map(() => "---").join(" | ")} |\n`;
          for (const row of result.result) {
            content += `| ${cols.map((c) => String((row as Record<string, unknown>)[c] ?? "")).join(" | ")} |\n`;
          }
          content += `\n*${result.result.length} row${result.result.length !== 1 ? "s" : ""} · ${result.execution_time_ms ?? 0}ms*`;
        } else {
          content = "No results returned.";
        }

        content += `\n\n<details><summary>Show SQL</summary>\n\n\`\`\`sql\n${result.generated_sql}\n\`\`\`\n\n</details>`;

        setMessages((prev) => [...prev, createMessage("assistant", content)]);
      } catch (err) {
        const text = err instanceof Error ? err.message : "Query failed.";
        setError(text);
        setMessages((prev) => [
          ...prev,
          createMessage("assistant", `Query failed: ${text}`),
        ]);
      } finally {
        setDbLoading(false);
      }
    },
    [input, loading],
  );

  const handleSend = async () => {
    const trimmed = input.trim();

    // In DB mode, route to the direct query handler
    if (dbMode) {
      await handleDbQuery();
      return;
    }

    const uploadedAttachmentIds = pendingAttachments
      .filter((item) => item.status === "uploaded" && item.attachment_id)
      .map((item) => item.attachment_id!);
    const imageContextAvailable = hasImageInConversation(messages);
    const shouldGenerateImage =
      isImageIntent(trimmed) ||
      (isImageEditIntent(trimmed) && imageContextAvailable);

    if ((!trimmed && uploadedAttachmentIds.length === 0) || loading) return;

    if (trimmed && uploadedAttachmentIds.length === 0 && shouldGenerateImage) {
      await handleGenerateImage(trimmed);
      return;
    }

    setError(null);
    setInput("");

    const optimisticAttachments = pendingAttachments
      .filter((item) => item.status === "uploaded")
      .map((item) => ({
        id: item.attachment_id ?? item.local_id,
        thread_id: activeThreadId ?? "",
        message_id: null,
        file_name: item.file_name,
        mime_type: item.mime_type,
        file_path: item.preview_url ?? "",
        created_at: new Date().toISOString(),
      }));

    const userMessage = createMessage("user", trimmed, optimisticAttachments);
    setMessages((prev) => [...prev, userMessage]);
    setChatLoading(true);

    try {
      const result = await sendMessage({
        message: trimmed || null,
        thread_id: activeThreadId,
        attachment_ids: uploadedAttachmentIds,
      });
      clearPendingAttachments();
      setMessages((prev) => [
        ...prev,
        createMessage("assistant", result.response),
      ]);

      if (!activeThreadId) {
        setActiveThreadId(result.thread_id);
      }

      // Always refresh threads so backend auto-generated names appear immediately.
      const refreshedThreads = await getThreads();
      setThreads(refreshedThreads.threads);
    } catch (err) {
      const text = err instanceof Error ? err.message : "Unexpected error";
      setError(text);
      setMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          "I could not complete that request right now.",
        ),
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const ensureThreadForUpload = useCallback(async (): Promise<string> => {
    if (activeThreadId) {
      return activeThreadId;
    }

    const created = await createThread({ name: "New Chat" });
    setActiveThreadId(created.id);
    setThreads((prev) => [created, ...prev]);
    return created.id;
  }, [activeThreadId]);

  const handleFilesAdded = useCallback(
    async (files: File[]) => {
      if (!files.length) return;

      setError(null);
      let threadIdForUpload: string;

      try {
        threadIdForUpload = await ensureThreadForUpload();
      } catch (err) {
        const text =
          err instanceof Error
            ? err.message
            : "Failed to create thread for upload.";
        setError(text);
        return;
      }

      // Validate total upload size on frontend
      const totalSize = files.reduce((sum, file) => sum + file.size, 0);
      const MAX_TOTAL_SIZE = 100 * 1024 * 1024; // 100MB - should match backend
      if (totalSize > MAX_TOTAL_SIZE) {
        const sizeMB = (totalSize / (1024 * 1024)).toFixed(1);
        const maxMB = (MAX_TOTAL_SIZE / (1024 * 1024)).toFixed(1);
        setError(
          `Total upload size (${sizeMB} MB) exceeds maximum (${maxMB} MB). Please upload fewer or smaller files.`,
        );
        return;
      }

      // Create pending attachment entries for all files
      const localIds = files.map(() => crypto.randomUUID());
      const pendingItems: PendingAttachment[] = files.map((file, index) => ({
        local_id: localIds[index],
        file_name: file.name,
        mime_type: file.type,
        file_size: file.size,
        progress: 1,
        status: "uploading",
        preview_url:
          file.type.startsWith("image/") || file.type.startsWith("video/")
            ? URL.createObjectURL(file)
            : undefined,
      }));

      setPendingAttachments((prev) => [...prev, ...pendingItems]);

      try {
        const uploaded = await uploadAttachmentsBatch(
          threadIdForUpload,
          files,
          (fileIndex, progress) => {
            setPendingAttachments((prev) =>
              prev.map((item) =>
                item.local_id === localIds[fileIndex]
                  ? { ...item, progress }
                  : item,
              ),
            );
          },
        );

        // Mark all files as successfully uploaded
        uploaded.forEach((attachment, index) => {
          setPendingAttachments((prev) =>
            prev.map((item) =>
              item.local_id === localIds[index]
                ? {
                    ...item,
                    status: "uploaded",
                    progress: 100,
                    mime_type: attachment.mime_type,
                    attachment_id: attachment.id,
                  }
                : item,
            ),
          );
        });
      } catch (err) {
        const text = err instanceof Error ? err.message : "Upload failed.";
        setError(text);

        // Mark all files as failed with the same error
        localIds.forEach((localId) => {
          setPendingAttachments((prev) =>
            prev.map((item) =>
              item.local_id === localId
                ? {
                    ...item,
                    status: "error",
                    error: text,
                    progress: 100,
                  }
                : item,
            ),
          );
        });
      }
    },
    [ensureThreadForUpload],
  );

  const handleRemoveAttachment = useCallback((localId: string) => {
    setPendingAttachments((prev) => {
      const match = prev.find((item) => item.local_id === localId);
      if (match?.preview_url?.startsWith("blob:")) {
        URL.revokeObjectURL(match.preview_url);
      }
      return prev.filter((item) => item.local_id !== localId);
    });
  }, []);

  return (
    <div className="relative flex h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_20%,#ffdbc8_0%,transparent_35%),radial-gradient(circle_at_80%_10%,#cde9ff_0%,transparent_33%),radial-gradient(circle_at_60%_85%,#fbe8ba_0%,transparent_38%)]" />

      {sidebarOpen && (
        <ThreadSidebar
          threads={dbMode ? [] : threads}
          activeThreadId={activeThreadId}
          dbMode={dbMode}
          onSelectThread={handleSelectThread}
          onNewThread={handleNewThread}
          onDeleteThread={handleDeleteThread}
          onRenameThread={handleRenameThread}
        />
      )}

      <main className="flex flex-1 flex-col">
        <header className="flex shrink-0 items-center justify-between border-b border-black/10 bg-white/75 px-5 py-3 backdrop-blur">
          <div className="flex min-w-0 items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="shrink-0 rounded-lg border border-black/10 p-2 text-sm text-(--muted) transition hover:bg-black/5"
            >
              ☰
            </button>
            <div className="min-w-0">
              <h1 className="truncate font-heading text-xl text-(--ink) sm:text-2xl">
                {dbMode ? "DB Query Assistant" : "AI Forge Chat"}
              </h1>
              <p className="truncate text-xs text-(--muted)">
                {user?.full_name} &middot; {user?.email}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              onClick={() => {
                setDbMode(!dbMode);
                setMessages([
                  createMessage(
                    "assistant",
                    dbMode
                      ? "Switched to Chat mode. How can I help you?"
                      : "Switched to DB Query mode. Ask me anything about your database in plain English!",
                  ),
                ]);
              }}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                dbMode
                  ? "bg-emerald-600 text-white hover:bg-emerald-700"
                  : "border border-black/10 text-(--muted) hover:bg-black/5"
              }`}
            >
              {dbMode ? "🗄 DB Mode" : "💬 Chat Mode"}
            </button>
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="rounded-lg border border-black/10 px-4 py-2 text-sm text-(--muted) transition hover:bg-black/5"
            >
              Logout
            </button>
          </div>
        </header>

        <section className="flex flex-1 flex-col overflow-hidden">
          <ChatMessageList messages={messages} loading={loading} />
          <ChatComposer
            value={input}
            disabled={loading}
            canSend={
              !!input.trim() ||
              pendingAttachments.some((item) => item.status === "uploaded")
            }
            canGenerateImage={!!input.trim()}
            generatingImage={imageLoading}
            attachments={pendingAttachments}
            onChange={setInput}
            onFilesAdded={handleFilesAdded}
            onRemoveAttachment={handleRemoveAttachment}
            onSubmit={handleSend}
            onGenerateImage={() => void handleGenerateImage()}
          />
        </section>

        {error && (
          <p className="border-t border-red-400/40 bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </main>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  return isAuthenticated ? <Navigate to="/chat" replace /> : children;
}

function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}

export default App;
