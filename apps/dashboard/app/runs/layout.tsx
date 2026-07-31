"use client";

import RequireAuth from "@/components/RequireAuth";

// Layout for the whole /runs route group: forces a session before any runs page
// (list, new, detail) renders. Unauthenticated users are bounced to /login.
export default function RunsLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
