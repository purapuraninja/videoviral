"use client";

import RequireAuth from "@/components/RequireAuth";

export default function OutputsPage() {
  return (
    <RequireAuth>
      <div className="max-w-3xl mx-auto">
        <h1 className="text-xl font-bold mb-2">Outputs</h1>
        <p className="text-slate-500">
          Video hasil render akan muncul di sini setelah local render agent
          selesai memproses job (Milestone 4: output management).
        </p>
      </div>
    </RequireAuth>
  );
}
