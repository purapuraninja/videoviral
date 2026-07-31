"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  // Already logged in? Skip straight to the app.
  useEffect(() => {
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then((r) => {
        if (r.ok) router.replace("/runs");
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
      const next =
        new URLSearchParams(window.location.search).get("next") || "/runs";
      router.replace(next);
    } catch (err) {
      setError(String(err));
    }
  }

  if (checking) return <p className="text-slate-400">Memeriksa sesi…</p>;

  return (
    <div className="max-w-sm mx-auto mt-16">
      <h1 className="text-xl font-bold mb-4">Sign in</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <input
          className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2"
          placeholder="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button className="w-full rounded bg-emerald-600 px-3 py-2 font-medium">
          Sign in
        </button>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </form>
    </div>
  );
}

