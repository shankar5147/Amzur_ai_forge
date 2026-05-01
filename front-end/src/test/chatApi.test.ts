import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  signup,
  login,
  googleLogin,
  getThreads,
  createThread,
  updateThread,
  deleteThread,
  sendMessage,
  getChatHistory,
} from "../services/chatApi";

const API_BASE = "http://localhost:8080";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

describe("chatApi service", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", mockFetch(200, {}));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("signup", () => {
    it("calls POST /api/auth/signup with payload", async () => {
      const mockResponse = {
        access_token: "token-123",
        token_type: "bearer",
        user: { id: "1", email: "a@b.com", full_name: "A B" },
      };
      vi.stubGlobal("fetch", mockFetch(201, mockResponse));

      const result = await signup({
        email: "a@b.com",
        password: "Pass1234!",
        full_name: "A B",
      });

      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/auth/signup`,
        expect.objectContaining({ method: "POST" }),
      );
      expect(result.access_token).toBe("token-123");
    });

    it("throws on error response", async () => {
      vi.stubGlobal(
        "fetch",
        mockFetch(409, { detail: "Email already exists" }),
      );

      await expect(
        signup({ email: "a@b.com", password: "x", full_name: "A" }),
      ).rejects.toThrow("Email already exists");
    });
  });

  describe("login", () => {
    it("calls POST /api/auth/login", async () => {
      const mockResponse = {
        access_token: "t",
        token_type: "bearer",
        user: { id: "1", email: "a@b.com", full_name: "A" },
      };
      vi.stubGlobal("fetch", mockFetch(200, mockResponse));

      const result = await login({ email: "a@b.com", password: "pass" });
      expect(result.access_token).toBe("t");
    });
  });

  describe("googleLogin", () => {
    it("calls POST /api/auth/google", async () => {
      const mockResponse = {
        access_token: "gt",
        token_type: "bearer",
        user: { id: "1", email: "g@b.com", full_name: "G" },
      };
      vi.stubGlobal("fetch", mockFetch(200, mockResponse));

      const result = await googleLogin({ credential: "google-token" });
      expect(result.access_token).toBe("gt");
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/auth/google`,
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  describe("getThreads", () => {
    it("calls GET /api/threads with auth header", async () => {
      localStorage.setItem("access_token", "my-token");
      vi.stubGlobal("fetch", mockFetch(200, { threads: [] }));

      const result = await getThreads();
      expect(result.threads).toEqual([]);
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/threads`,
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer my-token",
          }),
        }),
      );
    });
  });

  describe("createThread", () => {
    it("calls POST /api/threads", async () => {
      vi.stubGlobal(
        "fetch",
        mockFetch(201, {
          id: "t1",
          name: "New Chat",
          created_at: "",
          updated_at: "",
        }),
      );

      const result = await createThread({ name: "New Chat" });
      expect(result.name).toBe("New Chat");
    });
  });

  describe("updateThread", () => {
    it("calls PATCH /api/threads/:id", async () => {
      vi.stubGlobal(
        "fetch",
        mockFetch(200, {
          id: "t1",
          name: "Renamed",
          created_at: "",
          updated_at: "",
        }),
      );

      const result = await updateThread("t1", { name: "Renamed" });
      expect(result.name).toBe("Renamed");
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/threads/t1`,
        expect.objectContaining({ method: "PATCH" }),
      );
    });
  });

  describe("deleteThread", () => {
    it("calls DELETE /api/threads/:id", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({ ok: true, status: 204 }),
      );

      await deleteThread("t1");
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/threads/t1`,
        expect.objectContaining({ method: "DELETE" }),
      );
    });

    it("throws on error", async () => {
      vi.stubGlobal("fetch", mockFetch(404, { detail: "Not found" }));

      await expect(deleteThread("bad-id")).rejects.toThrow("Not found");
    });
  });

  describe("sendMessage", () => {
    it("calls POST /api/chat", async () => {
      vi.stubGlobal(
        "fetch",
        mockFetch(200, { response: "Hi!", thread_id: "t1" }),
      );

      const result = await sendMessage({ message: "Hello" });
      expect(result.response).toBe("Hi!");
      expect(result.thread_id).toBe("t1");
    });
  });

  describe("getChatHistory", () => {
    it("calls GET /api/chat/history/:threadId", async () => {
      vi.stubGlobal(
        "fetch",
        mockFetch(200, {
          messages: [{ id: "m1", role: "user", content: "Hi", created_at: "" }],
        }),
      );

      const result = await getChatHistory("t1");
      expect(result.messages).toHaveLength(1);
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/chat/history/t1`,
        expect.objectContaining({ method: "GET" }),
      );
    });
  });
});
