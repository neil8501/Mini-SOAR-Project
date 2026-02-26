"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Button, Card, Pill, Mono } from "@/components/ui";

type Case = {
  id: string;
  type: string;
  status: string;
  severity: string;
  score: number;
  created_at: string;
};

export default function CasesPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [err, setErr] = useState<string>("");

  const [status, setStatus] = useState<string>("");
  const [type, setType] = useState<string>("");
  const [severity, setSeverity] = useState<string>("");

  const query = useMemo(() => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (type) p.set("type", type);
    if (severity) p.set("severity", severity);
    return p.toString() ? `?${p.toString()}` : "";
  }, [status, type, severity]);

  useEffect(() => {
    (async () => {
      try {
        setErr("");
        const r = await apiGet(`/cases${query}`);
        setCases(r.cases || []);
      } catch (e: any) {
        setErr(e?.message || "Failed to load cases");
      }
    })();
  }, [query]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Cases</h1>
          <p className="mt-1 text-sm text-zinc-400">Filter and drill into case details.</p>
        </div>
        <Button href="/" variant="ghost">
          ← Dashboard
        </Button>
      </div>

      <Card title="Filters">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="text-xs text-zinc-400">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="mt-1 w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none"
            >
              <option value="">All</option>
              <option value="open">open</option>
              <option value="closed">closed</option>
              <option value="investigating">investigating</option>
              <option value="contained">contained</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-zinc-400">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="mt-1 w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none"
            >
              <option value="">All</option>
              <option value="phishing">phishing</option>
              <option value="login">login</option>
              <option value="beacon">beacon</option>
              <option value="unknown">unknown</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-zinc-400">Severity</label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="mt-1 w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none"
            >
              <option value="">All</option>
              <option value="critical">critical</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
        </div>
      </Card>

      {err ? (
        <Card title="Error">
          <div className="text-sm text-red-200">{err}</div>
        </Card>
      ) : null}

      <Card title={`Results (${cases.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-zinc-400">
              <tr className="border-b border-zinc-800">
                <th className="py-2 pr-3">Case</th>
                <th className="py-2 pr-3">Type</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Severity</th>
                <th className="py-2 pr-3">Score</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id} className="border-b border-zinc-900 hover:bg-zinc-900/40">
                  <td className="py-2 pr-3">
                    <Link className="hover:underline" href={`/cases/${c.id}`}>
                      <Mono>{c.id.slice(0, 8)}</Mono>
                    </Link>
                  </td>
                  <td className="py-2 pr-3">{c.type}</td>
                  <td className="py-2 pr-3">{c.status}</td>
                  <td className="py-2 pr-3">
                    <Pill text={c.severity} tone={c.severity as any} />
                  </td>
                  <td className="py-2 pr-3">{c.score}</td>
                </tr>
              ))}
              {!cases.length ? (
                <tr>
                  <td className="py-4 text-zinc-400" colSpan={5}>
                    No cases match current filters.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}