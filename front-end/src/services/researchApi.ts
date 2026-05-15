/**
 * SSE streaming client for the Research Digest Agent.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

export interface ResearchEventHandlers {
  onStatus?: (data: { step: string; message: string }) => void;
  onQueries?: (data: { queries: string[] }) => void;
  onPapers?: (data: unknown[]) => void;
  onPaperAnalysis?: (data: unknown) => void;
  onDigest?: (data: { content: string }) => void;
  onError?: (data: { message: string }) => void;
  onDone?: (data: { papers_found?: number; papers_analyzed?: number }) => void;
}

/**
 * Start the research agent and stream events.
 * Returns an AbortController that can cancel the stream.
 */
export function streamResearch(
  topic: string,
  handlers: ResearchEventHandlers,
): AbortController {
  const controller = new AbortController();

  const token = localStorage.getItem("access_token");
  const url = `${API_BASE_URL}/api/research/stream?topic=${encodeURIComponent(topic)}`;

  fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        handlers.onError?.({
          message: body.detail ?? `Request failed (${response.status})`,
        });
        handlers.onDone?.({});
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        handlers.onError?.({ message: "Streaming not supported." });
        handlers.onDone?.({});
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from the buffer
        const lines = buffer.split("\n");
        buffer = "";

        let currentEvent = "";
        let currentData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6);
          } else if (line === "" && currentEvent && currentData) {
            // End of event — dispatch it
            try {
              const parsed = JSON.parse(currentData);
              switch (currentEvent) {
                case "status":
                  handlers.onStatus?.(parsed);
                  break;
                case "queries":
                  handlers.onQueries?.(parsed);
                  break;
                case "papers":
                  handlers.onPapers?.(parsed);
                  break;
                case "paper_analysis":
                  handlers.onPaperAnalysis?.(parsed);
                  break;
                case "digest":
                  handlers.onDigest?.(parsed);
                  break;
                case "error":
                  handlers.onError?.(parsed);
                  break;
                case "done":
                  handlers.onDone?.(parsed);
                  break;
              }
            } catch {
              // ignore malformed events
            }
            currentEvent = "";
            currentData = "";
          } else if (line !== "") {
            // Incomplete event — put back in buffer
            buffer += line + "\n";
          }
        }

        // If there's a partial event still being assembled, keep it in the buffer
        if (currentEvent || currentData) {
          if (currentEvent) buffer += `event: ${currentEvent}\n`;
          if (currentData) buffer += `data: ${currentData}\n`;
        }
      }

      // If stream ended without a done event, fire one
      handlers.onDone?.({});
    })
    .catch((err) => {
      if ((err as Error).name !== "AbortError") {
        handlers.onError?.({
          message: (err as Error).message || "Stream failed.",
        });
        handlers.onDone?.({});
      }
    });

  return controller;
}
