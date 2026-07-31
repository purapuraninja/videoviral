"use client";

import { useRouter } from "next/navigation";

export default function Nav() {
  const router = useRouter();

  async function signOut() {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
    router.replace("/login");
  }

  return (
    <header className="border-b border-slate-800 px-6 py-4 flex items-center gap-6">
      <a href="/" className="font-bold text-lg">
        🎬 Viral Video Factory
      </a>
      <nav className="flex gap-4 text-sm text-slate-300">
        <a href="/runs" className="hover:text-white">Research Runs</a>
        <a href="/jobs" className="hover:text-white">Render Jobs</a>
        <a href="/profiles" className="hover:text-white">Render Profiles</a>
        <a href="/outputs" className="hover:text-white">Outputs</a>
      </nav>
      <button
        onClick={signOut}
        className="ml-auto rounded border border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-800"
      >
        Sign out
      </button>
    </header>
  );
}
