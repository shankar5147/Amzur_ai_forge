import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { AuthProvider, useAuth } from "../context/AuthContext";
import type { UserInfo } from "../types/chat";

const mockUser: UserInfo = {
  id: "user-1",
  email: "test@amzur.com",
  full_name: "Test User",
  avatar_url: null,
};

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("starts with null user and loading true initially", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });
    // After mount effect runs, loading should be false
    expect(result.current.loading).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("restores auth from localStorage on mount", () => {
    localStorage.setItem("access_token", "stored-token");
    localStorage.setItem("user_info", JSON.stringify(mockUser));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    expect(result.current.user).toEqual(mockUser);
    expect(result.current.token).toBe("stored-token");
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.loading).toBe(false);
  });

  it("setAuth stores token and user", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    act(() => {
      result.current.setAuth("new-token", mockUser);
    });

    expect(result.current.token).toBe("new-token");
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isAuthenticated).toBe(true);
    expect(localStorage.getItem("access_token")).toBe("new-token");
    expect(localStorage.getItem("user_info")).toBe(JSON.stringify(mockUser));
  });

  it("logout clears state and localStorage", () => {
    localStorage.setItem("access_token", "token");
    localStorage.setItem("user_info", JSON.stringify(mockUser));

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    act(() => {
      result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("user_info")).toBeNull();
  });

  it("throws error when useAuth is used outside AuthProvider", () => {
    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used inside AuthProvider");
  });
});
