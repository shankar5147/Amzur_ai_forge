import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ChatComposer } from "../components/ChatComposer";

describe("ChatComposer", () => {
  const defaultProps = {
    value: "",
    disabled: false,
    onChange: vi.fn(),
    onSubmit: vi.fn(),
  };

  it("renders input and send button", () => {
    render(<ChatComposer {...defaultProps} />);
    expect(screen.getByPlaceholderText("Ask anything...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });

  it("calls onChange when typing", () => {
    const onChange = vi.fn();
    render(<ChatComposer {...defaultProps} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Ask anything..."), {
      target: { value: "Hello" },
    });
    expect(onChange).toHaveBeenCalledWith("Hello");
  });

  it("calls onSubmit when form is submitted", () => {
    const onSubmit = vi.fn();
    render(<ChatComposer {...defaultProps} value="Hi" onSubmit={onSubmit} />);

    fireEvent.submit(
      screen.getByRole("button", { name: /send/i }).closest("form")!,
    );
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("disables input when disabled prop is true", () => {
    render(<ChatComposer {...defaultProps} disabled={true} />);
    expect(screen.getByPlaceholderText("Ask anything...")).toBeDisabled();
  });

  it("disables send button when value is empty", () => {
    render(<ChatComposer {...defaultProps} value="" />);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("disables send button when disabled", () => {
    render(<ChatComposer {...defaultProps} value="text" disabled={true} />);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("enables send button when value is non-empty and not disabled", () => {
    render(<ChatComposer {...defaultProps} value="message" />);
    expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled();
  });
});
