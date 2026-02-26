import Link from "next/link";

export function Card(props: { title?: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 shadow-sm">
      {(props.title || props.right) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {props.title ? <div className="text-sm font-medium text-zinc-100">{props.title}</div> : <div />}
          {props.right ? <div>{props.right}</div> : null}
        </div>
      )}
      {props.children}
    </div>
  );
}

export function Button(props: {
  children: React.ReactNode;
  onClick?: () => void;
  href?: string;
  variant?: "primary" | "ghost" | "danger";
  target?: string;
}) {
  const base =
    "inline-flex items-center justify-center rounded-xl px-3 py-2 text-sm font-medium border transition active:scale-[0.99]";
  const variant = props.variant || "primary";

  const cls =
    variant === "primary"
      ? "border-zinc-700 bg-white text-zinc-950 hover:bg-zinc-200"
      : variant === "danger"
      ? "border-red-600/40 bg-red-500/15 text-red-100 hover:bg-red-500/25"
      : "border-zinc-800 bg-transparent text-zinc-100 hover:bg-zinc-800/40";

  const className = `${base} ${cls}`;

  if (props.href) {
    return (
      <Link href={props.href} className={className} target={props.target}>
        {props.children}
      </Link>
    );
  }
  return (
    <button className={className} onClick={props.onClick}>
      {props.children}
    </button>
  );
}

export function Pill({ text, tone }: { text: string; tone?: "low" | "medium" | "high" | "critical" | "neutral" }) {
  const t = tone || "neutral";
  const cls =
    t === "critical"
      ? "bg-red-500/20 text-red-200 border-red-500/30"
      : t === "high"
      ? "bg-orange-500/20 text-orange-200 border-orange-500/30"
      : t === "medium"
      ? "bg-yellow-500/20 text-yellow-200 border-yellow-500/30"
      : t === "low"
      ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
      : "bg-zinc-800/60 text-zinc-200 border-zinc-700";

  return <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs ${cls}`}>{text}</span>;
}

export function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-xs text-zinc-200">{children}</span>;
}