"use client";

import RequireAuth from "@/components/RequireAuth";

export default function JobsLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
