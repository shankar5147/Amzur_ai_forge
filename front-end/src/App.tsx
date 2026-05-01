import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { ChatComposer } from "./components/ChatComposer";
import { ChatMessageList } from "./components/ChatMessageList";
import { LoginPage } from "./components/LoginPage";
import { ThreadSidebar } from "./components/ThreadSidebar";
import { useAuth } from "./context/AuthContext";
import {
  deleteThread,
  getChatHistory,
  getThreads,
  sendMessage,
  updateThread,
} from "./services/chatApi";
import type { ChatMessage, Thread } from "./types/chat";

function createMessage(
  role: ChatMessage["role"],
  content: string,
): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
  };
}

function ChatPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

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
    setActiveThreadId(null);
    setMessages([
      createMessage(
        "assistant",
        `Hello${user?.full_name ? `, ${user.full_name}` : ""}! How can I help you today?`,
      ),
    ]);
  }, [user]);

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

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setError(null);
    setInput("");

    const userMessage = createMessage("user", trimmed);
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const result = await sendMessage({
        message: trimmed,
        thread_id: activeThreadId,
      });
      setMessages((prev) => [
        ...prev,
        createMessage("assistant", result.response),
      ]);

      // If this was a new thread, update thread list and set active
      if (!activeThreadId) {
        setActiveThreadId(result.thread_id);
        const resp = await getThreads();
        setThreads(resp.threads);
      }
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
      setLoading(false);
    }
  };

  return (
    <div className="relative flex h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_20%,#ffdbc8_0%,transparent_35%),radial-gradient(circle_at_80%_10%,#cde9ff_0%,transparent_33%),radial-gradient(circle_at_60%_85%,#fbe8ba_0%,transparent_38%)]" />

      {sidebarOpen && (
        <ThreadSidebar
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={handleSelectThread}
          onNewThread={handleNewThread}
          onDeleteThread={handleDeleteThread}
          onRenameThread={handleRenameThread}
        />
      )}

      <main className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-black/10 bg-white/75 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="rounded-lg border border-black/10 p-2 text-sm text-(--muted) transition hover:bg-black/5"
            >
              ☰
            </button>
            <div>
              <h1 className="font-heading text-xl text-(--ink) sm:text-2xl">
                AI Forge Chat
              </h1>
              <p className="text-xs text-(--muted)">
                {user?.full_name} &middot; {user?.email}
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              logout();
              navigate("/login");
            }}
            className="rounded-lg border border-black/10 px-4 py-2 text-sm text-(--muted) transition hover:bg-black/5"
          >
            Logout
          </button>
        </header>

        <section className="flex flex-1 flex-col overflow-hidden">
          <ChatMessageList messages={messages} loading={loading} />
          <ChatComposer
            value={input}
            disabled={loading}
            onChange={setInput}
            onSubmit={handleSend}
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
