"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Client-side auth gate. Calls GET /api/v1/auth/me (cookie-auth) and redirects
 * to /login?next=... when there is no valid session. Wrap any protected page
 * (or a route-group layout) with this.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<"loading" | "ok">("loading");

  useEffect(() => {
    let active = true;
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then((r) => {
        if (!active) return;
        if (r.ok) {
          setState("ok");
        } else {
          const next = encodeURIComponent(
            window.location.pathname + window.location.search
          );
          router.replace(`/login?next=${next}`);
        }
      })
      .catch(() => {
        if (active) router.replace("/login");
      });
    return () => {
      active = false;
    };
  }, [router]);

  if (state !== "ok") {
    return <p className="text-slate-400">Memeriksa sesi…</p>;
  }
  return <>{children}</>;
}
