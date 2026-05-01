import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ThreadSidebar } from "../components/ThreadSidebar";
import type { Thread } from "../types/chat";

const threads: Thread[] = [
  {
    id: "t1",
    name: "Thread One",
    created_at: "2024-01-01",
    updated_at: "2024-01-01",
  },
  {
    id: "t2",
    name: "Thread Two",
    created_at: "2024-01-02",
    updated_at: "2024-01-02",
  },
];

describe("ThreadSidebar", () => {
  const defaultProps = {
    threads,
    activeThreadId: "t1",
    onSelectThread: vi.fn(),
    onNewThread: vi.fn(),
    onDeleteThread: vi.fn(),
    onRenameThread: vi.fn(),
  };

  it("renders thread names", () => {
    render(<ThreadSidebar {...defaultProps} />);
    expect(screen.getByText("Thread One")).toBeInTheDocument();
    expect(screen.getByText("Thread Two")).toBeInTheDocument();
  });

  it("shows empty message when no threads", () => {
    render(<ThreadSidebar {...defaultProps} threads={[]} />);
    expect(screen.getByText("No conversations yet")).toBeInTheDocument();
  });

  it("calls onNewThread when + New button is clicked", () => {
    const onNewThread = vi.fn();
    render(<ThreadSidebar {...defaultProps} onNewThread={onNewThread} />);
    fireEvent.click(screen.getByText("+ New"));
    expect(onNewThread).toHaveBeenCalledOnce();
  });

  it("calls onSelectThread when thread is clicked", () => {
    const onSelectThread = vi.fn();
    render(<ThreadSidebar {...defaultProps} onSelectThread={onSelectThread} />);
    fireEvent.click(screen.getByText("Thread Two"));
    expect(onSelectThread).toHaveBeenCalledWith("t2");
  });

  it("highlights active thread", () => {
    const { container } = render(
      <ThreadSidebar {...defaultProps} activeThreadId="t1" />,
    );
    const activeEl = screen
      .getByText("Thread One")
      .closest("div[class*='group']");
    expect(activeEl?.className).toContain("clay");
  });

  it("renders header with Chats title", () => {
    render(<ThreadSidebar {...defaultProps} />);
    expect(screen.getByText("Chats")).toBeInTheDocument();
  });
});
