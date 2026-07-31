"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs } from "@/lib/api";

type Job = {
  id: string;
  status: string;
  candidate_id: string;
  attempt: number;
  created_at: string;
  payload_json?: { candidate?: { title?: string } };
};

const STATUS_COLOR: Record<string, string> = {
  queued: "text-slate-400",
  claimed: "text-sky-400",
  completed: "text-emerald-400",
  failed: "text-red-400",
  cancelled: "text-slate-500",
  retry_waiting: "text-amber-400",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);

  async function refresh() {
    setJobs(await listJobs());
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-bold mb-4">Render jobs</h1>
      <table className="w-full text-sm">
        <thead className="text-slate-400 border-b border-slate-800">
          <tr>
            <th className="text-left py-2">Status</th>
            <th className="text-left">Candidate</th>
            <th className="text-left">Attempt</th>
            <th className="text-left">Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="border-b border-slate-900">
              <td className={`py-2 ${STATUS_COLOR[j.status] || ""}`}>{j.status}</td>
              <td>{j.payload_json?.candidate?.title || j.candidate_id}</td>
              <td>{j.attempt}</td>
              <td>{new Date(j.created_at).toLocaleString()}</td>
              <td>
                <Link href={`/jobs/${j.id}`} className="text-emerald-400 hover:underline">
                  Detail
                </Link>
              </td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr>
              <td colSpan={5} className="py-4 text-slate-500 text-center">
                No jobs yet. Approve a candidate to create one.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
