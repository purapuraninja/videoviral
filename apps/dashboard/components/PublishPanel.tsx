"use client";

import { useState } from "react";
import {
  PublishTarget,
  recordManualPublish,
  requestPublish,
  retryPublishTarget,
} from "@/lib/api";

const PLATFORMS = [
  { id: "youtube_shorts", label: "YouTube Shorts" },
  { id: "tiktok", label: "TikTok" },
  { id: "instagram_reels", label: "Instagram Reels" },
];

const STATUS_STYLES: Record<string, string> = {
  published: "text-emerald-400",
  publishing: "text-sky-400",
  pending: "text-slate-400",
  failed: "text-red-400",
  manual_required: "text-amber-400",
  skipped: "text-slate-500",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={STATUS_STYLES[status] ?? "text-slate-300"}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export default function PublishPanel({
  jobId,
  jobStatus,
  targets,
  onChange,
}: {
  jobId: string;
  jobStatus: string;
  targets: PublishTarget[];
  onChange: () => void;
}) {
  const [selected, setSelected] = useState<string[]>(PLATFORMS.map((p) => p.id));
  const [mode, setMode] = useState("auto");
  const [hashtags, setHashtags] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manualUrls, setManualUrls] = useState<Record<string, string>>({});

  const canPublish = ["completed", "publishing", "published", "publish_failed"].includes(
    jobStatus
  );

  function toggle(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  }

  async function run<T>(fn: () => Promise<T>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const onPublish = () =>
    run(() =>
      requestPublish(jobId, {
        platforms: selected,
        mode,
        hashtags: hashtags
          .split(/[,\s]+/)
          .map((h) => h.trim())
          .filter(Boolean),
      })
    );

  return (
    <div>
      <h2 className="font-semibold mb-2">Publish</h2>

      {!canPublish ? (
        <p className="text-slate-500 text-sm">
          Available once the render is complete.
        </p>
      ) : (
        <div className="space-y-3">
          <fieldset className="space-y-1">
            <legend className="text-sm text-slate-400">Platforms</legend>
            {PLATFORMS.map((p) => (
              <label key={p.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selected.includes(p.id)}
                  onChange={() => toggle(p.id)}
                  className="accent-emerald-500"
                />
                {p.label}
              </label>
            ))}
          </fieldset>

          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="block text-slate-400 mb-1">Mode</span>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
              >
                <option value="auto">auto (official APIs)</option>
                <option value="manual">manual (upload by hand)</option>
              </select>
            </label>
            <label className="text-sm flex-1 min-w-48">
              <span className="block text-slate-400 mb-1">Hashtags</span>
              <input
                value={hashtags}
                onChange={(e) => setHashtags(e.target.value)}
                placeholder="berita, gempa"
                className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
              />
            </label>
            <button
              onClick={onPublish}
              disabled={busy || selected.length === 0}
              className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
            >
              {busy ? "Working…" : "Publish"}
            </button>
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}
        </div>
      )}

      <ul className="mt-4 space-y-2 text-sm">
        {targets.map((t) => (
          <li key={t.id} className="rounded border border-slate-800 p-2">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">
                {PLATFORMS.find((p) => p.id === t.platform)?.label ?? t.platform}
              </span>
              <span>
                <StatusBadge status={t.status} />
                {t.attempt > 0 && (
                  <span className="text-slate-500"> · attempt {t.attempt}</span>
                )}
              </span>
            </div>

            {t.post_url && (
              <a
                href={t.post_url}
                target="_blank"
                rel="noreferrer"
                className="text-emerald-400 hover:underline break-all"
              >
                {t.post_url}
              </a>
            )}
            {t.error_message && (
              <p className="text-slate-400 mt-1">{t.error_message}</p>
            )}

            {/* Manual fallback: record the URL of a hand-uploaded post. */}
            {t.status !== "published" && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <input
                  value={manualUrls[t.id] ?? ""}
                  onChange={(e) =>
                    setManualUrls((prev) => ({ ...prev, [t.id]: e.target.value }))
                  }
                  placeholder="https://… (paste the post URL)"
                  className="flex-1 min-w-56 rounded border border-slate-700 bg-slate-900 px-2 py-1"
                />
                <button
                  onClick={() =>
                    run(() => recordManualPublish(t.id, (manualUrls[t.id] ?? "").trim()))
                  }
                  disabled={busy || !(manualUrls[t.id] ?? "").trim()}
                  className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                >
                  Record URL
                </button>
                <button
                  onClick={() => run(() => retryPublishTarget(t.id))}
                  disabled={busy}
                  className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                >
                  Retry
                </button>
              </div>
            )}
          </li>
        ))}
        {targets.length === 0 && (
          <li className="text-slate-500">Not published yet.</li>
        )}
      </ul>
    </div>
  );
}
