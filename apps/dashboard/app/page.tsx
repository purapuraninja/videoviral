"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Landing page acts as an auth router: send authed users to /runs, others to /login.
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then((r) => router.replace(r.ok ? "/runs" : "/login"))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <p className="text-slate-400">Memuat…</p>;
}

