import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { getAttachmentPreview, getAttachmentUrl } from "../services/chatApi";
import type { AttachmentPreview, ChatMessage } from "../types/chat";

interface ChatMessageListProps {
  messages: ChatMessage[];
  loading: boolean;
}

export function ChatMessageList({ messages, loading }: ChatMessageListProps) {
  const [previewMap, setPreviewMap] = useState<
    Record<string, AttachmentPreview>
  >({});

  const previewCandidates = useMemo(
    () =>
      messages
        .flatMap((message) => message.attachments ?? [])
        .filter(
          (attachment) =>
            !!attachment.id &&
            !attachment.file_path.startsWith("blob:") &&
            !attachment.mime_type.startsWith("image/") &&
            !attachment.mime_type.startsWith("video/"),
        ),
    [messages],
  );

  useEffect(() => {
    const missing = previewCandidates.filter((item) => !previewMap[item.id]);
    if (missing.length === 0) {
      return;
    }

    let cancelled = false;

    async function loadPreviews() {
      const settled = await Promise.allSettled(
        missing.map(async (attachment) => ({
          id: attachment.id,
          preview: await getAttachmentPreview(attachment.id),
        })),
      );

      if (cancelled) {
        return;
      }

      const next: Record<string, AttachmentPreview> = {};
      for (const result of settled) {
        if (result.status === "fulfilled") {
          next[result.value.id] = result.value.preview;
        }
      }

      if (Object.keys(next).length > 0) {
        setPreviewMap((prev) => ({ ...prev, ...next }));
      }
    }

    loadPreviews();
    return () => {
      cancelled = true;
    };
  }, [previewCandidates, previewMap]);

  const renderAttachment = (
    attachment: NonNullable<ChatMessage["attachments"]>[number],
  ) => {
    const url = attachment.file_path.startsWith("blob:")
      ? attachment.file_path
      : attachment.file_path
        ? getAttachmentUrl(attachment.file_path)
        : "";

    if (attachment.mime_type.startsWith("image/")) {
      if (!url) {
        return (
          <div className="rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-xs">
            {attachment.file_name}
          </div>
        );
      }
      return (
        <img
          src={url}
          alt={attachment.file_name}
          className="max-h-56 w-auto rounded-lg"
        />
      );
    }

    if (attachment.mime_type.startsWith("video/")) {
      if (!url) {
        return (
          <div className="rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-xs">
            {attachment.file_name}
          </div>
        );
      }
      return (
        <video controls className="max-h-56 w-full rounded-lg">
          <source src={url} type={attachment.mime_type} />
          Your browser does not support this video format.
        </video>
      );
    }

    if (!url) {
      return (
        <div className="block rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-xs text-(--ink) sm:text-sm">
          {attachment.file_name}
        </div>
      );
    }

    const preview = attachment.id ? previewMap[attachment.id] : undefined;
    if (preview?.preview_type === "table") {
      return (
        <div className="overflow-hidden rounded-lg border border-black/10 bg-white/90">
          <div className="border-b border-black/10 px-3 py-2 text-xs font-semibold text-(--ink) sm:text-sm">
            {attachment.file_name}
          </div>
          <div className="max-h-72 overflow-auto">
            <table className="min-w-full text-xs sm:text-sm">
              {!!preview.columns.length && (
                <thead className="bg-black/5 text-left">
                  <tr>
                    {preview.columns.map((column, index) => (
                      <th
                        key={`${attachment.id}-col-${index}`}
                        className="px-2 py-1.5 font-semibold"
                      >
                        {column || `Column ${index + 1}`}
                      </th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody>
                {preview.rows.map((row, rowIndex) => (
                  <tr
                    key={`${attachment.id}-row-${rowIndex}`}
                    className="border-t border-black/5"
                  >
                    {row.map((cell, cellIndex) => (
                      <td
                        key={`${attachment.id}-cell-${rowIndex}-${cellIndex}`}
                        className="px-2 py-1.5 align-top"
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.truncated && (
            <div className="border-t border-black/10 px-3 py-1.5 text-[11px] text-(--muted)">
              Preview limited to first rows.
            </div>
          )}
        </div>
      );
    }

    if (
      preview &&
      (preview.preview_type === "document" || preview.preview_type === "text")
    ) {
      return (
        <div className="overflow-hidden rounded-lg border border-black/10 bg-white/90">
          <div className="border-b border-black/10 px-3 py-2 text-xs font-semibold text-(--ink) sm:text-sm">
            {attachment.file_name}
          </div>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap px-3 py-2 text-xs text-(--ink) sm:text-sm">
            {preview.content || "No preview content available."}
          </pre>
          {preview.truncated && (
            <div className="border-t border-black/10 px-3 py-1.5 text-[11px] text-(--muted)">
              Preview truncated for performance.
            </div>
          )}
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="block border-t border-black/10 px-3 py-1.5 text-xs text-(--ink) underline-offset-2 hover:underline"
          >
            Open full file
          </a>
        </div>
      );
    }

    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="block rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-xs text-(--ink) underline-offset-2 hover:underline sm:text-sm"
      >
        {attachment.file_name}
      </a>
    );
  };

  return (
    <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5 sm:px-8">
      {messages.map((message) => {
        const isUser = message.role === "user";

        return (
          <div
            key={message.id}
            className={`flex ${isUser ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm sm:text-base ${
                isUser
                  ? "max-w-[70%] bg-(--ink) text-(--paper)"
                  : "max-w-[90%] bg-(--mist) text-(--ink)"
              }`}
            >
              {!!message.attachments?.length && (
                <div className="mb-2 space-y-2">
                  {message.attachments.map((attachment) => (
                    <div key={attachment.id}>
                      {renderAttachment(attachment)}
                    </div>
                  ))}
                </div>
              )}
              {isUser ? (
                message.content
              ) : (
                <div className="prose prose-sm max-w-none prose-headings:mt-3 prose-headings:mb-1 prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-code:rounded prose-code:bg-black/5 prose-code:px-1 prose-code:py-0.5 prose-pre:rounded-lg prose-pre:bg-gray-900 prose-pre:text-gray-100">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeRaw, rehypeKatex]}
                    components={{
                      table: ({ children, ...props }) => (
                        <div className="not-prose my-3 max-h-96 overflow-auto rounded-lg border border-black/10">
                          <table
                            className="min-w-full text-left text-sm"
                            {...props}
                          >
                            {children}
                          </table>
                        </div>
                      ),
                      thead: ({ children, ...props }) => (
                        <thead
                          className="sticky top-0 bg-gray-50 text-xs font-semibold uppercase text-gray-500"
                          {...props}
                        >
                          {children}
                        </thead>
                      ),
                      th: ({ children, ...props }) => (
                        <th className="whitespace-nowrap px-4 py-2" {...props}>
                          {children}
                        </th>
                      ),
                      td: ({ children, ...props }) => (
                        <td
                          className="whitespace-nowrap px-4 py-2 text-gray-700"
                          {...props}
                        >
                          {children}
                        </td>
                      ),
                      tr: ({ children, ...props }) => (
                        <tr
                          className="border-t border-gray-100 hover:bg-gray-50/50"
                          {...props}
                        >
                          {children}
                        </tr>
                      ),
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {loading && (
        <div className="flex justify-start">
          <div className="rounded-2xl bg-(--mist) px-4 py-3 text-sm text-(--muted) sm:text-base">
            Thinking...
          </div>
        </div>
      )}
    </div>
  );
}
