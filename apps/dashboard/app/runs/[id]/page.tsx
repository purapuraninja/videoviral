"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getRun, getCandidates, approveCandidate, createRenderJob } from "@/lib/api";

type Candidate = {
  id: string;
  title: string;
  summary: string;
  facts: string[];
  source_links: { url: string; title: string; publisher?: string; published_at?: string }[];
  final_score: number;
  rank: number;
  status: string;
};

export default function RunDetailPage({ params }: { params: { id: string } }) {
  const [run, setRun] = useState<{ id: string; keyword: string; status: string } | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const router = useRouter();

  async function refresh() {
    const r = await getRun(params.id).catch(() => null);
    if (r) setRun({ id: r.id, keyword: r.keyword, status: r.status });
    const c = await getCandidates(params.id).catch(() => []);
    setCandidates(c);
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function onApprove(c: Candidate) {
    try {
      await approveCandidate(c.id);
      const job = await createRenderJob(c.id, "TikTok ID 45s");
      setMessage(`Approved and queued render job ${job.id}`);
      refresh();
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setMessage(String(err));
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-bold mb-1">
        {run?.keyword ?? "Loading..."}
      </h1>
      <p className="text-slate-400 text-sm mb-4">
        Run {params.id} · status: {run?.status}
      </p>
      {message && <p className="text-emerald-400 text-sm mb-4">{message}</p>}

      {candidates.length === 0 && run?.status !== "completed" && (
        <p className="text-slate-500">Discovery in progress…</p>
      )}

      <div className="grid gap-4">
        {candidates.map((c) => (
          <div key={c.id} className="rounded border border-slate-800 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold">#{c.rank} · {c.title}</h2>
                <p className="text-sm text-slate-300 mt-1">{c.summary}</p>
              </div>
              <div className="text-right text-sm">
                <div className="text-emerald-400 font-mono">
                  {c.final_score.toFixed(2)}
                </div>
                <div className="text-slate-500">final score</div>
              </div>
            </div>

            {c.facts?.length > 0 && (
              <ul className="mt-3 list-disc list-inside text-sm text-slate-300 space-y-1">
                {c.facts.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            )}

            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-slate-400">
                Sources ({c.source_links?.length || 0})
              </summary>
              <ul className="mt-2 space-y-1">
                {c.source_links?.map((s, i) => (
                  <li key={i}>
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
                      {s.title || s.url}
                    </a>
                    {s.publisher && <span className="text-slate-500"> · {s.publisher}</span>}
                  </li>
                ))}
              </ul>
            </details>

            <div className="mt-4 flex gap-2">
              <button
                disabled={c.status !== "proposed"}
                onClick={() => onApprove(c)}
                className="rounded bg-emerald-600 disabled:opacity-40 px-3 py-1.5 text-sm font-medium"
              >
                {c.status === "proposed" ? "Approve & render" : c.status}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
