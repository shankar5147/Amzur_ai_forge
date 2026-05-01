import { FormEvent, useState } from "react";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { googleLogin, login, signup } from "../services/chatApi";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

export function LoginPage() {
  const { setAuth } = useAuth();
  const navigate = useNavigate();
  const [isSignup, setIsSignup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.endsWith("@amzur.com")) {
      setError("Only Amzur email accounts (@amzur.com) are allowed.");
      return;
    }

    setLoading(true);

    try {
      const result = isSignup
        ? await signup({ email, password, full_name: fullName })
        : await login({ email, password });

      setAuth(result.access_token, result.user);
      navigate("/chat", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse: {
    credential?: string;
  }) => {
    if (!credentialResponse.credential) return;
    setError(null);
    setLoading(true);
    try {
      const result = await googleLogin({
        credential: credentialResponse.credential,
      });
      setAuth(result.access_token, result.user);
      navigate("/chat", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <main className="relative flex min-h-screen items-center justify-center p-4">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_20%,#ffdbc8_0%,transparent_35%),radial-gradient(circle_at_80%_10%,#cde9ff_0%,transparent_33%),radial-gradient(circle_at_60%_85%,#fbe8ba_0%,transparent_38%)]" />

        <div className="w-full max-w-md rounded-2xl border border-black/10 bg-white/80 p-8 shadow-lg backdrop-blur">
          <h1 className="font-heading mb-2 text-2xl text-(--ink)">
            AI Forge Chat
          </h1>
          <p className="mb-6 text-sm text-(--muted)">
            {isSignup ? "Create your account" : "Sign in to continue"}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignup && (
              <input
                type="text"
                placeholder="Full Name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="w-full rounded-xl border border-black/15 bg-white px-4 py-3 text-sm outline-none transition focus:border-(--clay) focus:ring-2 focus:ring-(--clay)/20"
              />
            )}
            <input
              type="email"
              placeholder="Email (@amzur.com)"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-xl border border-black/15 bg-white px-4 py-3 text-sm outline-none transition focus:border-(--clay) focus:ring-2 focus:ring-(--clay)/20"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full rounded-xl border border-black/15 bg-white px-4 py-3 text-sm outline-none transition focus:border-(--clay) focus:ring-2 focus:ring-(--clay)/20"
            />

            {error && (
              <p className="rounded-lg border border-red-400/40 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-(--clay) py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-60"
            >
              {loading ? "Please wait..." : isSignup ? "Sign Up" : "Sign In"}
            </button>
          </form>

          {GOOGLE_CLIENT_ID && (
            <div className="mt-4">
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-black/10" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white/80 px-2 text-(--muted)">or</span>
                </div>
              </div>
              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError("Google login failed.")}
                  theme="outline"
                  size="large"
                  width="100%"
                />
              </div>
            </div>
          )}

          <p className="mt-5 text-center text-sm text-(--muted)">
            {isSignup ? "Already have an account?" : "Don't have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setIsSignup(!isSignup);
                setError(null);
              }}
              className="font-medium text-(--clay) hover:underline"
            >
              {isSignup ? "Sign In" : "Sign Up"}
            </button>
          </p>
        </div>
      </main>
    </GoogleOAuthProvider>
  );
}
