"use client";

import { useEffect, useState } from "react";
import { listProfiles } from "@/lib/api";
import RequireAuth from "@/components/RequireAuth";

type Profile = {
  id: string;
  name: string;
  resolution: string;
  duration_seconds: number;
  language: string;
};

export default function ProfilesPage() {
  return (
    <RequireAuth>
      <ProfilesList />
    </RequireAuth>
  );
}

function ProfilesList() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  useEffect(() => {
    listProfiles().then(setProfiles).catch(() => setProfiles([]));
  }, []);
  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-bold mb-4">Render profiles</h1>
      <div className="grid gap-3">
        {profiles.map((p) => (
          <div key={p.id} className="rounded border border-slate-800 p-4">
            <div className="font-semibold">{p.name}</div>
            <div className="text-sm text-slate-400">
              {p.resolution} · {p.duration_seconds}s · {p.language}
            </div>
          </div>
        ))}
        {profiles.length === 0 && <p className="text-slate-500">Belum ada profil.</p>}
      </div>
    </div>
  );
}
