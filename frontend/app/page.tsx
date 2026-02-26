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

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  const counts = useMemo(() => {
    const bySeverity = (data?.by_severity || {}) as Record<string, number>;
    return {
      critical: bySeverity["critical"] || 0,
      high: bySeverity["high"] || 0,
      medium: bySeverity["medium"] || 0,
      low: bySeverity["low"] || 0,
      total: data?.totals?.cases || 0,
    };
  }, [data]);

  useEffect(() => {
    (async () => {
      try {
        const s = await apiGet("/stats");
        setData(s);
      } catch (e: any) {
        setErr(e?.message || "Failed to load stats");
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Local SOAR-style case management UI. Backend: FastAPI + Postgres + Celery.
          </p>
        </div>
        <div className="flex gap-2">
          <Button href="/cases" variant="primary">
            View Cases
          </Button>
          <Button href="http://localhost:3000" target="_blank" variant="ghost">
            Open Grafana
          </Button>
        </div>
      </div>

      {err ? (
        <Card title="Error">
          <div className="text-sm text-red-200">{err}</div>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card title="Total Cases">
          <div className="text-3xl font-semibold">{counts.total}</div>
          <div className="mt-1 text-xs text-zinc-400">All time</div>
        </Card>
        <Card title="Critical">
          <div className="text-3xl font-semibold">{counts.critical}</div>
          <div className="mt-2"><Pill text="critical" tone="critical" /></div>
        </Card>
        <Card title="High">
          <div className="text-3xl font-semibold">{counts.high}</div>
          <div className="mt-2"><Pill text="high" tone="high" /></div>
        </Card>
        <Card title="Medium">
          <div className="text-3xl font-semibold">{counts.medium}</div>
          <div className="mt-2"><Pill text="medium" tone="medium" /></div>
        </Card>
        <Card title="Low">
          <div className="text-3xl font-semibold">{counts.low}</div>
          <div className="mt-2"><Pill text="low" tone="low" /></div>
        </Card>
      </div>

      <Card
        title="Latest Cases"
        right={<Button href="/cases" variant="ghost">All cases →</Button>}
      >
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
              {(data?.latest_cases || []).map((c: Case) => (
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
              {!data?.latest_cases?.length ? (
                <tr>
                  <td className="py-4 text-zinc-400" colSpan={5}>
                    No cases yet. Run simulators to generate sample incidents.
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