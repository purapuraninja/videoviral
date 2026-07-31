"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createResearchRun, startResearchRun } from "@/lib/api";

export default function NewRunPage() {
  const router = useRouter();
  const [keyword, setKeyword] = useState("");
  const [prompt, setPrompt] = useState("");
  const [language, setLanguage] = useState("id-ID");
  const [days, setDays] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await createResearchRun({
        keyword,
        research_prompt: prompt,
        language,
        period_days: days,
      });
      await startResearchRun(run.id);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-xl font-bold mb-4">New research run</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm text-slate-300">Keyword</span>
          <input
            required
            className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="gempa bali terkini"
          />
        </label>
        <label className="block">
          <span className="text-sm text-slate-300">Research prompt (optional)</span>
          <textarea
            className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </label>
        <div className="flex gap-3">
          <label className="flex-1">
            <span className="text-sm text-slate-300">Language</span>
            <select
              className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="id-ID">Indonesian (id-ID)</option>
              <option value="en-US">English (en-US)</option>
            </select>
          </label>
          <label className="flex-1">
            <span className="text-sm text-slate-300">Period (days)</span>
            <input
              type="number"
              className="w-full rounded bg-slate-900 border border-slate-700 px-3 py-2"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            />
          </label>
        </div>
        <button
          disabled={busy}
          className="rounded bg-emerald-600 disabled:opacity-50 px-4 py-2 font-medium"
        >
          {busy ? "Starting..." : "Create & start"}
        </button>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </form>
    </div>
  );
}
