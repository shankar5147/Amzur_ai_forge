import { useState } from "react";
import type { Thread } from "../types/chat";

interface ThreadSidebarProps {
  threads: Thread[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onDeleteThread: (threadId: string) => void;
  onRenameThread: (threadId: string, name: string) => void;
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onRenameThread,
}: ThreadSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const startRename = (thread: Thread) => {
    setEditingId(thread.id);
    setEditName(thread.name);
  };

  const submitRename = (threadId: string) => {
    if (editName.trim()) {
      onRenameThread(threadId, editName.trim());
    }
    setEditingId(null);
  };

  return (
    <aside className="flex h-full w-64 flex-col border-r border-black/10 bg-white/60 backdrop-blur">
      <div className="flex items-center justify-between border-b border-black/10 px-4 py-3">
        <h2 className="font-heading text-sm font-medium text-(--ink)">Chats</h2>
        <button
          onClick={onNewThread}
          className="rounded-lg bg-(--clay) px-3 py-1.5 text-xs font-medium text-white transition hover:bg-(--clay)/90"
        >
          + New
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-2">
        {threads.length === 0 && (
          <p className="px-2 py-4 text-center text-xs text-(--muted)">
            No conversations yet
          </p>
        )}
        {threads.map((thread) => (
          <div
            key={thread.id}
            className={`group mb-1 flex items-center rounded-lg px-3 py-2 text-sm transition cursor-pointer ${
              activeThreadId === thread.id
                ? "bg-(--clay)/10 text-(--clay)"
                : "text-(--ink) hover:bg-black/5"
            }`}
            onClick={() => onSelectThread(thread.id)}
          >
            {editingId === thread.id ? (
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onBlur={() => submitRename(thread.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitRename(thread.id);
                  if (e.key === "Escape") setEditingId(null);
                }}
                autoFocus
                className="flex-1 rounded border border-black/15 bg-white px-2 py-0.5 text-xs outline-none"
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <span className="flex-1 truncate">{thread.name}</span>
            )}

            {editingId !== thread.id && (
              <div className="ml-2 hidden gap-1 group-hover:flex">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startRename(thread);
                  }}
                  className="rounded p-0.5 text-xs text-(--muted) hover:text-(--ink)"
                  title="Rename"
                >
                  ✏️
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteThread(thread.id);
                  }}
                  className="rounded p-0.5 text-xs text-(--muted) hover:text-red-600"
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
            )}
          </div>
        ))}
      </nav>
    </aside>
  );
}
