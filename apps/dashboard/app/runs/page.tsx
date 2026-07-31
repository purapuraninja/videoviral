"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listRuns } from "@/lib/api";

type Run = {
  id: string;
  keyword: string;
  status: string;
  candidate_count: number;
  created_at: string;
};

export default function RunsListPage() {
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    listRuns().then(setRuns).catch(() => setRuns([]));
  }, []);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">Research runs</h1>
        <Link href="/runs/new" className="rounded bg-emerald-600 px-3 py-2 text-sm font-medium">
          New run
        </Link>
      </div>
      <table className="w-full text-sm">
        <thead className="text-slate-400 border-b border-slate-800">
          <tr>
            <th className="text-left py-2">Keyword</th>
            <th className="text-left">Status</th>
            <th className="text-left">Candidates</th>
            <th className="text-left">Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-b border-slate-900">
              <td className="py-2">{r.keyword}</td>
              <td>{r.status}</td>
              <td>{r.candidate_count}</td>
              <td>{new Date(r.created_at).toLocaleString()}</td>
              <td>
                <Link href={`/runs/${r.id}`} className="text-emerald-400 hover:underline">
                  Review
                </Link>
              </td>
            </tr>
          ))}
          {runs.length === 0 && (
            <tr>
              <td colSpan={5} className="py-4 text-slate-500 text-center">
                No runs yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
