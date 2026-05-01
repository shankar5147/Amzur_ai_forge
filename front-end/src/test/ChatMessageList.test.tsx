import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ChatMessageList } from "../components/ChatMessageList";
import type { ChatMessage } from "../types/chat";

describe("ChatMessageList", () => {
  const messages: ChatMessage[] = [
    { id: "1", role: "user", content: "Hello there" },
    { id: "2", role: "assistant", content: "Hi! How can I help?" },
  ];

  it("renders all messages", () => {
    render(<ChatMessageList messages={messages} loading={false} />);
    expect(screen.getByText("Hello there")).toBeInTheDocument();
    expect(screen.getByText("Hi! How can I help?")).toBeInTheDocument();
  });

  it("shows loading indicator when loading is true", () => {
    render(<ChatMessageList messages={[]} loading={true} />);
    expect(screen.getByText("Thinking...")).toBeInTheDocument();
  });

  it("does not show loading indicator when loading is false", () => {
    render(<ChatMessageList messages={[]} loading={false} />);
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
  });

  it("renders user messages as plain text", () => {
    render(
      <ChatMessageList
        messages={[{ id: "1", role: "user", content: "Plain text" }]}
        loading={false}
      />,
    );
    expect(screen.getByText("Plain text")).toBeInTheDocument();
  });

  it("renders assistant messages with markdown", () => {
    render(
      <ChatMessageList
        messages={[{ id: "1", role: "assistant", content: "**Bold text**" }]}
        loading={false}
      />,
    );
    const bold = screen.getByText("Bold text");
    expect(bold.tagName).toBe("STRONG");
  });

  it("renders empty list without errors", () => {
    const { container } = render(
      <ChatMessageList messages={[]} loading={false} />,
    );
    expect(container).toBeInTheDocument();
  });
});
