import { useCallback, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  askDataQuestion,
  deleteDataSession,
  loadGoogleSheet,
  uploadDataFile,
} from "../services/dataQueryApi";
import type {
  DataFileUploadResponse,
  DataQueryResponseType,
  GoogleSheetLoadResponse,
} from "../types/chat";

interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  content: string;
  code?: string | null;
}

export function DataQueryPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [columns, setColumns] = useState<string[]>([]);
  const [preview, setPreview] = useState<Record<string, unknown>[]>([]);
  const [dtypes, setDtypes] = useState<Record<string, string>>({});
  const [rowCount, setRowCount] = useState(0);
  const [colCount, setColCount] = useState(0);

  const [sheetUrl, setSheetUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loading = uploading || loadingSheet || asking;

  const scrollToBottom = useCallback(() => {
    setTimeout(
      () => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }),
      100,
    );
  }, []);

  const applySessionData = useCallback(
    (
      sid: string,
      name: string,
      cols: string[],
      prev: Record<string, unknown>[],
      dt: Record<string, string>,
      rows: number,
      colCnt: number,
    ) => {
      setSessionId(sid);
      setFileName(name);
      setColumns(cols);
      setPreview(prev);
      setDtypes(dt);
      setRowCount(rows);
      setColCount(colCnt);
      setShowPreview(true);
      setChat([
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `**${name}** loaded successfully — ${rows.toLocaleString()} rows × ${colCnt} columns. Ask me anything about this data!`,
        },
      ]);
    },
    [],
  );

  // --- File Upload ---
  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setError(null);
      setUploading(true);
      try {
        const resp: DataFileUploadResponse = await uploadDataFile(file);
        applySessionData(
          resp.session_id,
          resp.file_name,
          resp.columns,
          resp.preview,
          resp.dtypes,
          resp.row_count,
          resp.column_count,
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed.");
      } finally {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [applySessionData],
  );

  // --- Google Sheet ---
  const handleLoadSheet = useCallback(async () => {
    if (!sheetUrl.trim()) return;
    setError(null);
    setLoadingSheet(true);
    try {
      const resp: GoogleSheetLoadResponse = await loadGoogleSheet({
        sheet_url: sheetUrl.trim(),
      });
      applySessionData(
        resp.session_id,
        resp.sheet_title,
        resp.columns,
        resp.preview,
        resp.dtypes,
        resp.row_count,
        resp.column_count,
      );
      setSheetUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sheet.");
    } finally {
      setLoadingSheet(false);
    }
  }, [sheetUrl, applySessionData]);

  // --- Ask Question ---
  const handleAsk = useCallback(async () => {
    if (!question.trim() || !sessionId) return;
    const q = question.trim();
    setError(null);
    setQuestion("");
    setAsking(true);

    const userEntry: ChatEntry = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
    };
    setChat((prev) => [...prev, userEntry]);
    scrollToBottom();

    try {
      const resp: DataQueryResponseType = await askDataQuestion(sessionId, q);
      const assistantEntry: ChatEntry = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: resp.answer,
        code: resp.code,
      };
      setChat((prev) => [...prev, assistantEntry]);
      scrollToBottom();
    } catch (err) {
      const text = err instanceof Error ? err.message : "Query failed.";
      setError(text);
      setChat((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Query failed: ${text}`,
        },
      ]);
      scrollToBottom();
    } finally {
      setAsking(false);
    }
  }, [question, sessionId, scrollToBottom]);

  // --- Clear Session ---
  const handleClear = useCallback(async () => {
    if (sessionId) {
      try {
        await deleteDataSession(sessionId);
      } catch {
        // ignore
      }
    }
    setSessionId(null);
    setFileName("");
    setColumns([]);
    setPreview([]);
    setDtypes({});
    setRowCount(0);
    setColCount(0);
    setChat([]);
    setShowPreview(false);
    setError(null);
  }, [sessionId]);

  return (
    <div className="flex h-full flex-col">
      {/* Header area — data source selection */}
      {!sessionId && (
        <div className="mx-auto w-full max-w-3xl px-4 pt-8">
          <h2 className="mb-2 text-center font-heading text-2xl font-bold text-gray-800">
            CSV / Sheets Query Agent
          </h2>
          <p className="mb-8 text-center text-sm text-gray-500">
            Upload a CSV/Excel file or paste a Google Sheets URL to start
            querying your data with AI.
          </p>

          {/* Upload */}
          <div className="mb-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700">
              Upload File
            </h3>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={handleFileUpload}
                disabled={loading}
                className="block w-full text-sm text-gray-500 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
              />
              {uploading && (
                <span className="text-sm text-gray-400">Uploading…</span>
              )}
            </div>
            <p className="mt-2 text-xs text-gray-400">
              Supported: .csv, .xlsx, .xls (max 15 MB)
            </p>
          </div>

          {/* Google Sheet */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700">
              Google Sheets URL
            </h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={sheetUrl}
                onChange={(e) => setSheetUrl(e.target.value)}
                placeholder="https://docs.google.com/spreadsheets/d/..."
                disabled={loading}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 focus:outline-none"
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleLoadSheet();
                }}
              />
              <button
                onClick={() => void handleLoadSheet()}
                disabled={loading || !sheetUrl.trim()}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
              >
                {loadingSheet ? "Loading…" : "Load Sheet"}
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-400">
              The sheet must be shared as &quot;Anyone with the link can
              view&quot;.
            </p>
          </div>
        </div>
      )}

      {/* Active session */}
      {sessionId && (
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Session bar */}
          <div className="flex items-center justify-between border-b border-gray-200 bg-white/80 px-5 py-3 backdrop-blur">
            <div className="flex items-center gap-3">
              <span className="rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">
                {fileName}
              </span>
              <span className="text-xs text-gray-400">
                {rowCount.toLocaleString()} rows × {colCount} cols
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowPreview(!showPreview)}
                className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition hover:bg-gray-50"
              >
                {showPreview ? "Hide Preview" : "Show Preview"}
              </button>
              <button
                onClick={() => void handleClear()}
                className="rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 transition hover:bg-red-50"
              >
                Clear Session
              </button>
            </div>
          </div>

          {/* Data preview table */}
          {showPreview && preview.length > 0 && (
            <div className="max-h-56 shrink-0 overflow-auto border-b border-gray-200 bg-gray-50">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-gray-100">
                  <tr>
                    {columns.map((col) => (
                      <th
                        key={col}
                        className="whitespace-nowrap px-3 py-2 font-semibold text-gray-700"
                      >
                        {col}
                        <span className="ml-1 font-normal text-gray-400">
                          ({dtypes[col]})
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.slice(0, 20).map((row, i) => (
                    <tr
                      key={i}
                      className="border-t border-gray-100 hover:bg-white"
                    >
                      {columns.map((col) => (
                        <td
                          key={col}
                          className="max-w-50 truncate whitespace-nowrap px-3 py-1.5 text-gray-600"
                        >
                          {String(row[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4">
            <div className="mx-auto max-w-3xl space-y-4">
              {chat.map((entry) => (
                <div
                  key={entry.id}
                  className={`flex ${entry.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      entry.role === "user"
                        ? "bg-indigo-600 text-white"
                        : "bg-white text-gray-800 shadow-sm border border-gray-100"
                    }`}
                  >
                    {entry.role === "assistant" ? (
                      <div className="prose prose-sm max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {entry.content}
                        </ReactMarkdown>
                        {entry.code && (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-xs text-gray-400">
                              Show code
                            </summary>
                            <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-2 text-xs text-gray-600">
                              <code>{entry.code}</code>
                            </pre>
                          </details>
                        )}
                      </div>
                    ) : (
                      <p>{entry.content}</p>
                    )}
                  </div>
                </div>
              ))}
              {asking && (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-gray-100 bg-white px-4 py-3 text-sm text-gray-400 shadow-sm">
                    Analyzing…
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 bg-white px-4 py-3">
            <div className="mx-auto flex max-w-3xl gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder='Ask a question, e.g. "What is the highest sales value?"'
                disabled={asking}
                className="flex-1 rounded-xl border border-gray-300 px-4 py-2.5 text-sm placeholder:text-gray-400 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 focus:outline-none"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleAsk();
                  }
                }}
              />
              <button
                onClick={() => void handleAsk()}
                disabled={asking || !question.trim()}
                className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
              >
                {asking ? "…" : "Ask"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error bar */}
      {error && (
        <div className="border-t border-red-400/40 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-red-500 underline"
          >
            dismiss
          </button>
        </div>
      )}
    </div>
  );
}
