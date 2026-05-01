import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "../components/LoginPage";
import { AuthProvider } from "../context/AuthContext";

// Mock the chatApi module
vi.mock("../services/chatApi", () => ({
  login: vi.fn(),
  signup: vi.fn(),
  googleLogin: vi.fn(),
}));

// Mock Google OAuth
vi.mock("@react-oauth/google", () => ({
  GoogleOAuthProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  GoogleLogin: () => (
    <button data-testid="google-login-btn">Google Sign In</button>
  ),
}));

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("renders login form by default", () => {
    renderLoginPage();
    expect(screen.getByText("Sign in to continue")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  it("shows signup form when toggled", () => {
    renderLoginPage();
    fireEvent.click(screen.getByText(/sign up/i));
    expect(screen.getByText("Create your account")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/full name/i)).toBeInTheDocument();
  });

  it("renders Google login button", () => {
    renderLoginPage();
    expect(screen.getByTestId("google-login-btn")).toBeInTheDocument();
  });

  it("calls login on form submit", async () => {
    const { login } = await import("../services/chatApi");
    (login as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: "token",
      token_type: "bearer",
      user: { id: "1", email: "a@b.com", full_name: "A" },
    });

    renderLoginPage();

    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: "a@b.com" },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: "Password1!" },
    });
    fireEvent.click(
      screen.getByText("Sign In", { selector: "button[type='submit']" }),
    );

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        email: "a@b.com",
        password: "Password1!",
      });
    });
  });

  it("shows error on failed login", async () => {
    const { login } = await import("../services/chatApi");
    (login as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("Invalid credentials"),
    );

    renderLoginPage();

    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: "bad@b.com" },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(
      screen.getByText("Sign In", { selector: "button[type='submit']" }),
    );

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  it("calls signup when in signup mode", async () => {
    const { signup } = await import("../services/chatApi");
    (signup as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: "token",
      token_type: "bearer",
      user: { id: "1", email: "new@b.com", full_name: "New User" },
    });

    renderLoginPage();
    fireEvent.click(screen.getByText(/sign up/i));

    fireEvent.change(screen.getByPlaceholderText(/full name/i), {
      target: { value: "New User" },
    });
    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: "new@b.com" },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.click(
      screen.getByText("Sign Up", { selector: "button[type='submit']" }),
    );

    await waitFor(() => {
      expect(signup).toHaveBeenCalledWith({
        email: "new@b.com",
        password: "StrongPass1!",
        full_name: "New User",
      });
    });
  });

  it("renders app title", () => {
    renderLoginPage();
    expect(screen.getByText("AI Forge Chat")).toBeInTheDocument();
  });
});
