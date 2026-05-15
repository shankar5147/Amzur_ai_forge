import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import {
  createDatabaseConnection,
  deleteDatabaseConnection,
  executeDatabaseQuery,
  listDatabaseConnections,
  testDatabaseConnection,
} from "../services/databaseApi";
import type {
  DatabaseConnection,
  DatabaseConnectionCreate,
  DatabaseQueryResponse,
} from "../types/chat";

// ─── Connection Form ────────────────────────────────────────────────

const DEFAULT_FORM: DatabaseConnectionCreate = {
  name: "",
  db_type: "postgresql",
  host: "localhost",
  port: 5432,
  database_name: "",
  username: "",
  password: "",
  ssl_enabled: false,
};

function ConnectionForm({
  onCreated,
  onCancel,
}: {
  onCreated: (c: DatabaseConnection) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<DatabaseConnectionCreate>({
    ...DEFAULT_FORM,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value, type } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]:
        type === "number"
          ? Number(value)
          : type === "checkbox"
            ? (e.target as HTMLInputElement).checked
            : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const conn = await createDatabaseConnection(form);
      onCreated(conn);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-black/10 bg-white p-5 shadow-sm"
    >
      <h3 className="mb-4 text-lg font-semibold text-gray-800">
        Add Database Connection
      </h3>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <input
          name="name"
          placeholder="Connection Name"
          value={form.name}
          onChange={handleChange}
          required
          className="rounded-lg border border-black/10 px-3 py-2 text-sm"
        />
        <select
          name="db_type"
          value={form.db_type}
          onChange={handleChange}
          className="rounded-lg border border-black/10 px-3 py-2 text-sm"
        >
          <option value="postgresql">PostgreSQL</option>
          <option value="mysql">MySQL</option>
          <option value="sqlite">SQLite</option>
        </select>
        <input
          name="host"
          placeholder="Host"
          value={form.host}
          onChange={handleChange}
          required
          className="rounded-lg border border-black/10 px-3 py-2 text-sm"
        />
        <input
          name="port"
          type="number"
          placeholder="Port"
          value={form.port}
          onChange={handleChange}
          required
          className="rounded-lg border border-black/10 px-3 py-2 text-sm"
        />
        <input
          name="database_name"
          placeholder="Database Name"
          value={form.database_name}
          onChange={handleChange}
          required
          className="rounded-lg border border-black/10 px-3 py-2 text-sm"
        />
        <input
          name="username"
          placeholder="Username"
          value={form.username}
          onChange={handleChange}
          required
          className="rounded-lg border border-black/10 px-3 py-2 text-sm"
        />
        <input
          name="password"
          type="password"
          placeholder="Password"
          value={form.password}
          onChange={handleChange}
          required
          className="rounded-lg border border-black/10 px-3 py-2 text-sm"
        />
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            name="ssl_enabled"
            type="checkbox"
            checked={form.ssl_enabled}
            onChange={handleChange}
          />
          SSL Enabled
        </label>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Connecting…" : "Connect"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-black/10 px-4 py-2 text-sm text-gray-600 transition hover:bg-black/5"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ─── Result Table ───────────────────────────────────────────────────

function ResultTable({ data }: { data: Record<string, unknown>[] }) {
  if (data.length === 0)
    return (
      <p className="py-4 text-center text-sm text-gray-500">
        No results returned.
      </p>
    );

  const columns = Object.keys(data[0]);

  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-black/10">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-gray-50 text-xs font-semibold uppercase text-gray-500">
          <tr>
            {columns.map((col) => (
              <th key={col} className="whitespace-nowrap px-4 py-2">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {data.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50/50">
              {columns.map((col) => (
                <td
                  key={col}
                  className="whitespace-nowrap px-4 py-2 text-gray-700"
                >
                  {row[col] == null ? (
                    <span className="text-gray-300">NULL</span>
                  ) : (
                    String(row[col])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Query Chat Item ────────────────────────────────────────────────

function QueryItem({
  question,
  response,
  showSql,
  onToggleSql,
}: {
  question: string;
  response: DatabaseQueryResponse | null;
  showSql: boolean;
  onToggleSql: () => void;
}) {
  return (
    <div className="space-y-2">
      {/* User question */}
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-md bg-blue-600 px-4 py-2.5 text-sm text-white">
          {question}
        </div>
      </div>

      {/* AI response */}
      {response ? (
        <div className="space-y-2">
          <div className="max-w-[90%] rounded-2xl rounded-bl-md bg-white px-4 py-3 shadow-sm border border-black/5">
            {response.error ? (
              <p className="text-sm text-red-600">{response.error}</p>
            ) : (
              <>
                {/* SQL toggle */}
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs text-gray-400">
                    {response.execution_time_ms != null &&
                      `${response.execution_time_ms}ms`}
                    {response.result &&
                      Array.isArray(response.result) &&
                      ` · ${response.result.length} row${response.result.length !== 1 ? "s" : ""}`}
                  </span>
                  <button
                    onClick={onToggleSql}
                    className="text-xs font-medium text-blue-600 hover:text-blue-800"
                  >
                    {showSql ? "Hide SQL" : "Show SQL"}
                  </button>
                </div>

                {/* Generated SQL */}
                {showSql && (
                  <pre className="mb-3 overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-green-400">
                    <code>{response.generated_sql}</code>
                  </pre>
                )}

                {/* Result table */}
                {response.result && Array.isArray(response.result) && (
                  <ResultTable data={response.result} />
                )}
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2 px-2 py-2 text-sm text-gray-400">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
          Generating SQL and executing query…
        </div>
      )}
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────

interface QueryEntry {
  id: string;
  question: string;
  response: DatabaseQueryResponse | null;
  showSql: boolean;
}

export function DatabaseQueryPage() {
  const { user, logout } = useAuth();

  // Connection state
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string | null>(
    null,
  );
  const [showConnectionForm, setShowConnectionForm] = useState(false);

  // Query state
  const [queryInput, setQueryInput] = useState("");
  const [queries, setQueries] = useState<QueryEntry[]>([]);
  const [queryLoading, setQueryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Test connection state
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{
    id: string;
    ok: boolean;
    msg: string;
  } | null>(null);

  const activeConnection = connections.find((c) => c.id === activeConnectionId);

  // Load connections
  useEffect(() => {
    async function load() {
      try {
        const resp = await listDatabaseConnections();
        setConnections(resp.connections);
        if (resp.connections.length > 0 && !activeConnectionId) {
          setActiveConnectionId(resp.connections[0].id);
        }
      } catch {
        // ignore
      }
    }
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleConnectionCreated = useCallback((conn: DatabaseConnection) => {
    setConnections((prev) => [conn, ...prev]);
    setActiveConnectionId(conn.id);
    setShowConnectionForm(false);
    setQueries([]);
  }, []);

  const handleDeleteConnection = useCallback(
    async (connId: string) => {
      try {
        await deleteDatabaseConnection(connId);
        setConnections((prev) => prev.filter((c) => c.id !== connId));
        if (activeConnectionId === connId) {
          setActiveConnectionId(null);
          setQueries([]);
        }
      } catch {
        // ignore
      }
    },
    [activeConnectionId],
  );

  const handleTestConnection = useCallback(async (connId: string) => {
    setTestingId(connId);
    setTestResult(null);
    try {
      await testDatabaseConnection(connId);
      setTestResult({ id: connId, ok: true, msg: "Connected!" });
    } catch (err) {
      setTestResult({
        id: connId,
        ok: false,
        msg: err instanceof Error ? err.message : "Failed",
      });
    } finally {
      setTestingId(null);
    }
  }, []);

  const handleSelectConnection = useCallback((connId: string) => {
    setActiveConnectionId(connId);
    setQueries([]);
    setTestResult(null);
  }, []);

  const handleSendQuery = useCallback(async () => {
    const trimmed = queryInput.trim();
    if (!trimmed || !activeConnectionId || queryLoading) return;

    setError(null);
    setQueryInput("");
    setQueryLoading(true);

    const entryId = crypto.randomUUID();
    const entry: QueryEntry = {
      id: entryId,
      question: trimmed,
      response: null,
      showSql: false,
    };
    setQueries((prev) => [...prev, entry]);

    try {
      const result = await executeDatabaseQuery({
        connection_id: activeConnectionId,
        natural_language_query: trimmed,
      });
      setQueries((prev) =>
        prev.map((q) => (q.id === entryId ? { ...q, response: result } : q)),
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Query failed.";
      setError(msg);
      setQueries((prev) =>
        prev.map((q) =>
          q.id === entryId
            ? {
                ...q,
                response: {
                  query_id: "",
                  generated_sql: "",
                  result: null,
                  error: msg,
                  execution_time_ms: null,
                },
              }
            : q,
        ),
      );
    } finally {
      setQueryLoading(false);
    }
  }, [activeConnectionId, queryInput, queryLoading]);

  const toggleSql = useCallback((entryId: string) => {
    setQueries((prev) =>
      prev.map((q) => (q.id === entryId ? { ...q, showSql: !q.showSql } : q)),
    );
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar: Connections */}
      <aside className="flex w-72 flex-col border-r border-black/10 bg-white/80">
        <div className="flex items-center justify-between border-b border-black/10 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-700">Connections</h2>
          <button
            onClick={() => setShowConnectionForm(!showConnectionForm)}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700"
          >
            + New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {connections.length === 0 && !showConnectionForm ? (
            <p className="px-2 py-8 text-center text-xs text-gray-400">
              No connections yet. Click "+ New" to add one.
            </p>
          ) : (
            connections.map((conn) => (
              <div
                key={conn.id}
                onClick={() => handleSelectConnection(conn.id)}
                className={`mb-1 cursor-pointer rounded-lg px-3 py-2.5 text-sm transition ${
                  activeConnectionId === conn.id
                    ? "bg-blue-50 text-blue-700 ring-1 ring-blue-200"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium truncate">{conn.name}</span>
                  <span
                    className={`h-2 w-2 rounded-full ${conn.is_active ? "bg-green-400" : "bg-gray-300"}`}
                  />
                </div>
                <p className="mt-0.5 text-xs text-gray-400 truncate">
                  {conn.db_type} · {conn.host}:{conn.port}/{conn.database_name}
                </p>
                <div className="mt-1.5 flex gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleTestConnection(conn.id);
                    }}
                    disabled={testingId === conn.id}
                    className="rounded bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600 hover:bg-gray-200"
                  >
                    {testingId === conn.id ? "Testing…" : "Test"}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConnection(conn.id);
                    }}
                    className="rounded bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-500 hover:bg-red-100"
                  >
                    Delete
                  </button>
                </div>
                {testResult && testResult.id === conn.id && (
                  <p
                    className={`mt-1 text-[10px] ${testResult.ok ? "text-green-600" : "text-red-500"}`}
                  >
                    {testResult.msg}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main area */}
      <main className="flex flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-black/10 bg-white/75 px-5 py-3 backdrop-blur">
          <div>
            <h1 className="font-heading text-xl text-gray-800 sm:text-2xl">
              Database Query Assistant
            </h1>
            <p className="text-xs text-gray-400">
              {user?.full_name} · Ask questions about your database in natural
              language
            </p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/chat"
              className="rounded-lg border border-black/10 px-4 py-2 text-sm text-gray-600 transition hover:bg-black/5"
            >
              Chat
            </a>
            <button
              onClick={() => logout()}
              className="rounded-lg border border-black/10 px-4 py-2 text-sm text-gray-600 transition hover:bg-black/5"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Connection form */}
        {showConnectionForm && (
          <div className="border-b border-black/10 bg-gray-50/50 p-4">
            <ConnectionForm
              onCreated={handleConnectionCreated}
              onCancel={() => setShowConnectionForm(false)}
            />
          </div>
        )}

        {/* Query area */}
        {activeConnection ? (
          <section className="flex flex-1 flex-col overflow-hidden">
            {/* Active connection banner */}
            <div className="border-b border-black/5 bg-blue-50/50 px-5 py-2">
              <span className="text-xs font-medium text-blue-600">
                Connected to:{" "}
              </span>
              <span className="text-xs text-blue-700">
                {activeConnection.name} ({activeConnection.db_type} ·{" "}
                {activeConnection.database_name})
              </span>
            </div>

            {/* Chat messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              {queries.length === 0 && (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <p className="text-lg text-gray-300">🔍</p>
                    <p className="mt-2 text-sm text-gray-400">
                      Ask a question about your database
                    </p>
                    <div className="mt-3 flex flex-wrap justify-center gap-2">
                      {[
                        "Show users created this month",
                        "Top 5 products by sales",
                        "Monthly revenue report",
                      ].map((example) => (
                        <button
                          key={example}
                          onClick={() => setQueryInput(example)}
                          className="rounded-full border border-blue-200 px-3 py-1 text-xs text-blue-600 transition hover:bg-blue-50"
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {queries.map((entry) => (
                <QueryItem
                  key={entry.id}
                  question={entry.question}
                  response={entry.response}
                  showSql={entry.showSql}
                  onToggleSql={() => toggleSql(entry.id)}
                />
              ))}
            </div>

            {/* Input bar */}
            <div className="border-t border-black/10 bg-white px-4 py-3">
              {error && <p className="mb-2 text-xs text-red-500">{error}</p>}
              <div className="flex gap-2">
                <input
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendQuery();
                    }
                  }}
                  placeholder="Ask a question about your database…"
                  disabled={queryLoading}
                  className="flex-1 rounded-xl border border-black/10 px-4 py-2.5 text-sm outline-none transition focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
                />
                <button
                  onClick={handleSendQuery}
                  disabled={!queryInput.trim() || queryLoading}
                  className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
                >
                  {queryLoading ? (
                    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    "Ask"
                  )}
                </button>
              </div>
            </div>
          </section>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <p className="text-5xl">🗄️</p>
              <p className="mt-3 text-gray-500">
                {connections.length > 0
                  ? "Select a connection to start querying"
                  : "Add a database connection to get started"}
              </p>
              {connections.length === 0 && (
                <button
                  onClick={() => setShowConnectionForm(true)}
                  className="mt-3 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
                >
                  + Add Connection
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
