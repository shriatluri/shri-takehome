/**
 * The template's presentation primitives. Small, unopinionated, and styled
 * entirely by the tokens in `index.css`, so a new internal app gets the same
 * look without importing anything from `apps/`.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

export function Card({
  title,
  action,
  children,
  className = "",
  padded = true,
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <header className="card-head">
          {typeof title === "string" ? <h2>{title}</h2> : title}
          {action}
        </header>
      )}
      {padded ? <div className="card-body">{children}</div> : children}
    </section>
  );
}

const BADGE_TONES: Record<string, string> = {
  Open: "badge-open",
  Escalated: "badge-escalated",
  Approved: "badge-approved",
  Active: "badge-approved",
  Rejected: "badge-rejected",
  Failed: "badge-rejected",
  Passed: "badge-approved",
  Suspended: "badge-escalated",
  "Needs review": "badge-escalated",
};

export function Badge({ children }: { children: string }) {
  return <span className={`badge ${BADGE_TONES[children] ?? "badge-neutral"}`}>{children}</span>;
}

/** Score as a dial. The colour is the tier, so the number is read twice. */
export function RiskDial({ score, large = false }: { score: number; large?: boolean }) {
  const color = score >= 70 ? "var(--danger)" : score >= 30 ? "var(--warn)" : "var(--ok)";
  const style = { "--risk": Math.min(score, 100), "--risk-color": color } as CSSProperties;
  return (
    <div
      className={`risk ${large ? "risk-lg" : ""}`}
      style={style}
      data-score={score}
      role="img"
      aria-label={`Risk score ${score}`}
    />
  );
}

/** A read-only fact in the box a form field would use. */
export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="field-box">
      <span>{label}</span>
      <b>{children ?? "—"}</b>
    </div>
  );
}

export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-head">
        <h3>{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export function initials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0] ?? "")
    .join("")
    .toUpperCase();
}

/** Slide-over panel. Closes on Escape and on a click outside, like a dialog. */
export function Drawer({
  title,
  subtitle,
  onClose,
  footer,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Case detail">
        <header className="drawer-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p className="muted">{subtitle}</p>}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="drawer-body">{children}</div>
        {footer && <footer className="drawer-foot">{footer}</footer>}
      </aside>
    </>
  );
}

type Toast = { id: number; message: string; tone: "ok" | "error" };
const ToastContext = createContext<(message: string, tone?: "ok" | "error") => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((message: string, tone: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => setToasts((c) => c.filter((t) => t.id !== id)), 4000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast ${toast.tone === "error" ? "toast-error" : ""}`}
            role="status"
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  const widths = useMemo(
    () => Array.from({ length: rows }, (_, i) => `${70 + ((i * 37) % 30)}%`),
    [rows],
  );
  return (
    <div className="card-body" aria-hidden>
      {widths.map((width) => (
        <div className="skeleton" key={width} style={{ width }} />
      ))}
    </div>
  );
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  // [upper bound in seconds, unit, seconds per unit]
  const units: [number, Intl.RelativeTimeFormatUnit, number][] = [
    [60, "second", 1],
    [3600, "minute", 60],
    [86400, "hour", 3600],
    [2592000, "day", 86400],
  ];
  const format = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [limit, unit, size] of units) {
    if (Math.abs(seconds) < limit) {
      return format.format(-Math.round(seconds / size), unit);
    }
  }
  return new Date(iso).toLocaleDateString();
}
