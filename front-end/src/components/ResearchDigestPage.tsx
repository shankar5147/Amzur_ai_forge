import { useCallback, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { streamResearch } from "../services/researchApi";
import type { PaperAnalysis, ResearchPaper } from "../types/chat";

type AgentStep =
  | "idle"
  | "planning"
  | "searching"
  | "ranking"
  | "analyzing"
  | "synthesizing"
  | "done"
  | "error";

const STEP_LABELS: Record<string, string> = {
  planning: "Planning search strategy…",
  searching: "Searching arXiv…",
  ranking: "Ranking papers…",
  analyzing: "Analyzing papers…",
  synthesizing: "Generating digest…",
};

function RelevanceBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    high: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-gray-100 text-gray-500",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${colors[level] ?? colors.medium}`}
    >
      {level}
    </span>
  );
}

export function ResearchDigestPage() {
  const [topic, setTopic] = useState("");
  const [useMcp, setUseMcp] = useState(false);
  const [step, setStep] = useState<AgentStep>("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [queries, setQueries] = useState<string[]>([]);
  const [papers, setPapers] = useState<ResearchPaper[]>([]);
  const [analyses, setAnalyses] = useState<PaperAnalysis[]>([]);
  const [digest, setDigest] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{
    found?: number;
    analyzed?: number;
  } | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const digestRef = useRef<HTMLDivElement>(null);
  const running = step !== "idle" && step !== "done" && step !== "error";

  const handleStart = useCallback(() => {
    if (!topic.trim() || running) return;

    // Reset state
    setStep("planning");
    setStatusMsg("Starting research agent…");
    setQueries([]);
    setPapers([]);
    setAnalyses([]);
    setDigest(null);
    setError(null);
    setStats(null);

    const controller = streamResearch(
      topic.trim(),
      {
        onStatus: (data) => {
          setStep(data.step as AgentStep);
          setStatusMsg(data.message);
        },
        onQueries: (data) => {
          setQueries(data.queries);
        },
        onPapers: (data) => {
          setPapers(data as ResearchPaper[]);
        },
        onPaperAnalysis: (data) => {
          setAnalyses((prev) => [...prev, data as PaperAnalysis]);
        },
        onDigest: (data) => {
          setDigest(data.content);
          setTimeout(
            () => digestRef.current?.scrollIntoView({ behavior: "smooth" }),
            200,
          );
        },
        onError: (data) => {
          setError(data.message);
          setStep("error");
        },
        onDone: (data) => {
          setStep((prev) => (prev === "error" ? "error" : "done"));
          if (data.papers_found != null) {
            setStats({
              found: data.papers_found,
              analyzed: data.papers_analyzed,
            });
          }
        },
      },
      useMcp,
    );

    abortRef.current = controller;
  }, [topic, running, useMcp]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    setStep("idle");
    setStatusMsg("");
  }, []);

  const handleReset = useCallback(() => {
    abortRef.current?.abort();
    setTopic("");
    setStep("idle");
    setStatusMsg("");
    setQueries([]);
    setPapers([]);
    setAnalyses([]);
    setDigest(null);
    setError(null);
    setStats(null);
  }, []);

  // ── Progress bar ──
  const progressSteps: AgentStep[] = [
    "planning",
    "searching",
    "ranking",
    "analyzing",
    "synthesizing",
    "done",
  ];
  const currentIdx = progressSteps.indexOf(step);

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* ── Hero / Input ── */}
      <div className="mx-auto w-full max-w-4xl px-4 pt-8">
        <h2 className="mb-1 text-center font-heading text-2xl font-bold text-gray-800">
          AI Research Digest Agent
        </h2>
        <p className="mb-6 text-center text-sm text-gray-500">
          Enter a research topic and let the AI agent autonomously search arXiv,
          analyze papers, and generate a structured digest.
        </p>

        {/* ── Backend mode toggle ── */}
        <div className="mb-4 flex items-center justify-center gap-3">
          <span
            className={`text-xs font-medium ${!useMcp ? "text-violet-700" : "text-gray-400"}`}
          >
            Direct arXiv
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={useMcp}
            disabled={running}
            onClick={() => setUseMcp((v) => !v)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 disabled:opacity-50 ${
              useMcp ? "bg-violet-600" : "bg-gray-200"
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                useMcp ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
          <span
            className={`text-xs font-medium ${useMcp ? "text-violet-700" : "text-gray-400"}`}
          >
            MCP Server
          </span>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder='e.g. "Latest advances in AI agents" or "Multimodal RAG systems"'
            disabled={running}
            className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-sm placeholder:text-gray-400 focus:border-violet-400 focus:ring-1 focus:ring-violet-400 focus:outline-none disabled:opacity-60"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleStart();
            }}
          />
          {running ? (
            <button
              onClick={handleCancel}
              className="rounded-xl bg-red-500 px-5 py-3 text-sm font-medium text-white transition hover:bg-red-600"
            >
              Cancel
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={!topic.trim()}
              className="rounded-xl bg-violet-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-violet-700 disabled:opacity-50"
            >
              Research
            </button>
          )}
          {(step === "done" || step === "error") && (
            <button
              onClick={handleReset}
              className="rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-600 transition hover:bg-gray-50"
            >
              Reset
            </button>
          )}
        </div>

        {/* ── Progress bar ── */}
        {step !== "idle" && (
          <div className="mt-5">
            <div className="mb-2 flex justify-between text-[10px] font-medium uppercase tracking-wide text-gray-400">
              {progressSteps.map((s, i) => (
                <span
                  key={s}
                  className={
                    i <= currentIdx ? "text-violet-600" : "text-gray-300"
                  }
                >
                  {s === "done" ? "Complete" : s}
                </span>
              ))}
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
              <div
                className="h-full rounded-full bg-violet-500 transition-all duration-500"
                style={{
                  width: `${Math.max(5, ((currentIdx + 1) / progressSteps.length) * 100)}%`,
                }}
              />
            </div>
            {statusMsg && (
              <p className="mt-2 text-center text-xs text-gray-500">
                {running && (
                  <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-violet-500" />
                )}
                {statusMsg}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Search queries ── */}
      {queries.length > 0 && (
        <div className="mx-auto mt-6 w-full max-w-4xl px-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Search Queries
          </h3>
          <div className="flex flex-wrap gap-2">
            {queries.map((q, i) => (
              <span
                key={i}
                className="rounded-lg bg-violet-50 px-3 py-1 text-xs text-violet-700"
              >
                {q}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Paper cards ── */}
      {papers.length > 0 && (
        <div className="mx-auto mt-6 w-full max-w-4xl px-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">
            Papers Found ({papers.length})
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {papers.map((p) => {
              const analysis = analyses.find((a) => a.paper_id === p.paper_id);
              return (
                <div
                  key={p.paper_id}
                  className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md"
                >
                  <div className="mb-1 flex items-start justify-between gap-2">
                    <a
                      href={p.arxiv_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-semibold text-gray-800 hover:text-violet-600"
                    >
                      {p.title}
                    </a>
                    {analysis && <RelevanceBadge level={analysis.relevance} />}
                  </div>
                  <p className="mb-1.5 text-[11px] text-gray-400">
                    {p.authors.slice(0, 3).join(", ")}
                    {p.authors.length > 3 && " et al."} · {p.published}
                  </p>

                  {analysis ? (
                    <div>
                      <p className="text-xs leading-relaxed text-gray-600">
                        {analysis.summary}
                      </p>
                      {analysis.key_findings.length > 0 && (
                        <ul className="mt-2 list-inside list-disc text-xs text-gray-500">
                          {analysis.key_findings.map((f, i) => (
                            <li key={i}>{f}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : (
                    <p className="line-clamp-3 text-xs text-gray-500">
                      {p.abstract}
                    </p>
                  )}

                  <div className="mt-2 flex gap-2">
                    <a
                      href={p.arxiv_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-violet-600 hover:underline"
                    >
                      arXiv
                    </a>
                    <a
                      href={p.pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-violet-600 hover:underline"
                    >
                      PDF
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Digest ── */}
      {digest && (
        <div
          ref={digestRef}
          className="mx-auto mt-8 w-full max-w-4xl px-4 pb-12"
        >
          <div className="rounded-2xl border border-violet-200 bg-white p-6 shadow-sm">
            <div className="prose prose-sm prose-violet max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children, ...rest }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      {...rest}
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {digest}
              </ReactMarkdown>
            </div>
          </div>
          {stats && (
            <p className="mt-3 text-center text-xs text-gray-400">
              {stats.found} papers found · {stats.analyzed} analyzed
            </p>
          )}
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="mx-auto mt-6 w-full max-w-4xl px-4">
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        </div>
      )}

      {/* ── Empty state spacer ── */}
      {step === "idle" && (
        <div className="mx-auto mt-10 max-w-2xl px-4 text-center">
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              "Latest advances in AI agents",
              "Research on multimodal RAG systems",
              "Recent papers about LLM memory",
              "State of autonomous coding agents",
            ].map((example) => (
              <button
                key={example}
                onClick={() => {
                  setTopic(example);
                }}
                className="rounded-xl border border-gray-200 px-4 py-3 text-left text-sm text-gray-600 transition hover:border-violet-300 hover:bg-violet-50"
              >
                <span className="mr-1 text-violet-400">→</span> {example}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
