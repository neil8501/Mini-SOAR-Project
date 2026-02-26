"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

const DEFAULT_ADMIN_KEY = "dev-admin-key";

function pill(status?: string) {
  const s = (status || "").toLowerCase();
  if (s === "critical") return "bg-red-500/20 text-red-200 border-red-500/30";
  if (s === "high") return "bg-orange-500/20 text-orange-200 border-orange-500/30";
  if (s === "medium") return "bg-yellow-500/20 text-yellow-200 border-yellow-500/30";
  if (s === "low") return "bg-emerald-500/20 text-emerald-200 border-emerald-500/30";
  return "bg-zinc-800/60 text-zinc-200 border-zinc-700";
}

export default function TopNav() {
  const [adminKey, setAdminKey] = useState(DEFAULT_ADMIN_KEY);

  useEffect(() => {
    const v = localStorage.getItem("miniSoarAdminKey");
    if (v) setAdminKey(v);
  }, []);

  useEffect(() => {
    localStorage.setItem("miniSoarAdminKey", adminKey);
  }, [adminKey]);

  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000", []);

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            Mini-SOAR
          </Link>
          <nav className="flex items-center gap-3 text-sm text-zinc-300">
            <Link href="/" className="hover:text-white">Dashboard</Link>
            <Link href="/cases" className="hover:text-white">Cases</Link>
            <a href={`${apiBase}/docs`} className="hover:text-white" target="_blank" rel="noreferrer">
              API Docs
            </a>
            <a href="http://localhost:3000" className="hover:text-white" target="_blank" rel="noreferrer">
              Grafana
            </a>
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <span className={`hidden sm:inline-flex items-center rounded-full border px-2 py-1 text-xs ${pill("low")}`}>
            UI Local
          </span>

          <div className="flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/40 px-3 py-2">
            <span className="text-xs text-zinc-400">Admin Key</span>
            <input
              value={adminKey}
              onChange={(e) => setAdminKey(e.target.value)}
              className="w-40 bg-transparent text-xs text-zinc-100 outline-none placeholder:text-zinc-600"
              placeholder="X-Admin-Key"
            />
          </div>
        </div>
      </div>
    </header>
  );
}