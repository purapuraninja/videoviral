"use client";

import { useEffect, useState } from "react";
import { getJob, getJobEvents, getJobOutputs, cancelJob } from "@/lib/api";

type Job = {
  id: string;
  status: string;
  candidate_id: string;
  attempt: number;
  error_message?: string | null;
  claimed_by_agent_id?: string | null;
  created_at: string;
  payload_json?: { candidate?: { title?: string } };
};

type Ev = { status: string; message: string; progress: number; created_at: string };
type Out = {
  artifact_type: string;
  storage_url: string;
  preview_url?: string | null;
  size_bytes?: number | null;
  duration_seconds?: number | null;
};

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<Job | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [outputs, setOutputs] = useState<Out[]>([]);

  async function refresh() {
    const j = await getJob(params.id);
    if (j) setJob(j);
    setEvents(await getJobEvents(params.id));
    setOutputs(await getJobOutputs(params.id));
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [params.id]);

  if (!job) return <p className="text-slate-400">Loading…</p>;

  const last = events[events.length - 1];
  const progress = last?.progress ?? 0;
  const title = job.payload_json?.candidate?.title || job.candidate_id;
  const terminal = ["completed", "failed", "cancelled"].includes(job.status);

  async function onCancel() {
    await cancelJob(params.id);
    refresh();
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold">{title}</h1>
        <p className="text-slate-400 text-sm">
          Job {job.id} · attempt {job.attempt}
          {job.claimed_by_agent_id ? ` · agent ${job.claimed_by_agent_id}` : ""}
        </p>
      </div>

      <div>
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="font-medium capitalize">{job.status.replace(/_/g, " ")}</span>
          <span className="text-slate-400">{progress}%</span>
        </div>
        <div className="h-2 rounded bg-slate-800 overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        {job.error_message && (
          <p className="text-red-400 text-sm mt-2">{job.error_message}</p>
        )}
      </div>

      {!terminal && (
        <button
          onClick={onCancel}
          className="rounded border border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-800"
        >
          Cancel job
        </button>
      )}

      <div>
        <h2 className="font-semibold mb-2">Events</h2>
        <ul className="space-y-1 text-sm max-h-64 overflow-auto">
          {events
            .slice()
            .reverse()
            .map((e, i) => (
              <li key={i} className="text-slate-300">
                <span className="text-slate-500">
                  {new Date(e.created_at).toLocaleTimeString()}
                </span>{" "}
                <span className="text-sky-400">{e.status}</span> — {e.message} (
                {e.progress}%)
              </li>
            ))}
          {events.length === 0 && <li className="text-slate-500">No events yet.</li>}
        </ul>
      </div>

      <div>
        <h2 className="font-semibold mb-2">Artifacts</h2>
        {/* Video preview: streamed from the render PC via the API's Tailscale
            proxy (not stored on the VPS). */}
        {outputs
          .filter((o) => o.preview_url)
          .slice(0, 1)
          .map((o, i) => (
            <video
              key={i}
              controls
              playsInline
              preload="metadata"
              className="w-full max-w-xs rounded border border-slate-800 mb-3 bg-black"
              src={`/api/v1${o.preview_url}`}
            />
          ))}
        <ul className="space-y-1 text-sm">
          {outputs.map((o, i) => (
            <li key={i}>
              {o.preview_url ? (
                <a
                  href={`/api/v1${o.preview_url}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-400 hover:underline"
                >
                  {o.artifact_type} (preview)
                </a>
              ) : (
                <a
                  href={o.storage_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-400 hover:underline"
                >
                  {o.artifact_type}
                </a>
              )}
              {o.size_bytes ? ` · ${Math.round(o.size_bytes / 1024)} KB` : ""}
              {o.duration_seconds ? ` · ${o.duration_seconds}s` : ""}
            </li>
          ))}
          {outputs.length === 0 && <li className="text-slate-500">No artifacts yet.</li>}
        </ul>
      </div>
    </div>
  );
}
