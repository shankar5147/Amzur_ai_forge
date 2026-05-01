import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage } from "../types/chat";

interface ChatMessageListProps {
  messages: ChatMessage[];
  loading: boolean;
}

export function ChatMessageList({ messages, loading }: ChatMessageListProps) {
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
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm sm:text-base ${
                isUser
                  ? "bg-(--ink) text-(--paper)"
                  : "bg-(--mist) text-(--ink)"
              }`}
            >
              {isUser ? (
                message.content
              ) : (
                <div className="prose prose-sm max-w-none prose-headings:mt-3 prose-headings:mb-1 prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-code:rounded prose-code:bg-black/5 prose-code:px-1 prose-code:py-0.5 prose-pre:rounded-lg prose-pre:bg-gray-900 prose-pre:text-gray-100">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
