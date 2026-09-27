import { useMemo, useState } from "react";

import { apiGet, type Case } from "../../platform/api";
import { useIdentity } from "../../platform/identity";
import { useApiList } from "../../platform/useApiList";
import { Badge, Card, RiskDial, Skeleton } from "../../platform/ui";

import { CaseDetail } from "./CaseDetail";

const POLL_MS = 5000;
const FILTERS = ["Needs action", "All", "Open", "Escalated", "Decided"] as const;
type Filter = (typeof FILTERS)[number];

const DECIDED = ["Approved", "Rejected", "Suspended"];

/**
 * The queue and the case being reviewed, side by side: deciding a case should
 * not hide the rest of the queue behind a modal.
 *
 * Which cases arrive here is the database's decision, not this component's —
 * `GET /cases` has no `assigned_to` filter, so an analyst's list is short
 * because the RLS policy returned three rows.
 */
export function QueuePage({ search }: { search: string }) {
  const { identity } = useIdentity();
  const { data: cases, error, loading, refresh } = useApiList<Case>(
    () => apiGet<Case[]>("/cases"),
    POLL_MS,
  );
  const [filter, setFilter] = useState<Filter>("Needs action");
  const [selected, setSelected] = useState<number | null>(null);

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return cases.filter((kase) => {
      const matchesFilter =
        filter === "All" ||
        (filter === "Decided" && DECIDED.includes(kase.status)) ||
        (filter === "Needs action" && !DECIDED.includes(kase.status)) ||
        filter === kase.status;
      const matchesSearch =
        !term ||
        kase.customer_name.toLowerCase().includes(term) ||
        kase.country.toLowerCase().includes(term) ||
        kase.status.toLowerCase().includes(term) ||
        String(kase.id) === term.replace("#", "");
      return matchesFilter && matchesSearch;
    });
  }, [cases, filter, search]);

  if (error) {
    return (
      <Card title="Queue unavailable">
        <p role="alert">{error}</p>
      </Card>
    );
  }

  const counts = {
    total: cases.length,
    open: cases.filter((kase) => kase.status === "Open").length,
    escalated: cases.filter((kase) => kase.status === "Escalated").length,
    decided: cases.filter((kase) => DECIDED.includes(kase.status)).length,
  };

  return (
    <>
      <div className="stats">
        <div className="card stat">
          <b>{counts.total}</b>
          <span>Visible to {identity?.name.split(" ")[0] ?? "you"}</span>
        </div>
        <div className="card stat">
          <b>{counts.open}</b>
          <span>Open</span>
        </div>
        <div className="card stat">
          <b>{counts.escalated}</b>
          <span>Escalated</span>
        </div>
        <div className="card stat">
          <b>{counts.decided}</b>
          <span>Decided</span>
        </div>
      </div>

      <div className="workspace">
        <Card
          className="pane-list"
          padded={false}
          title={
            <div className="row">
              <h2>Cases</h2>
              <span className="live">
                <i />
                Live · {POLL_MS / 1000}s
              </span>
            </div>
          }
          action={
            <div className="chips">
              {FILTERS.map((option) => (
                <button
                  key={option}
                  className="chip"
                  aria-pressed={filter === option}
                  onClick={() => setFilter(option)}
                >
                  {option}
                </button>
              ))}
            </div>
          }
        >
          {loading ? (
            <Skeleton rows={5} />
          ) : rows.length === 0 ? (
            <p className="empty">
              {cases.length === 0
                ? "No cases are visible to this user — row-level security, not a filter in the API."
                : "No cases match this filter."}
            </p>
          ) : (
            <div className="table-wrap pane-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Risk</th>
                    <th>Case</th>
                    <th>Customer</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((kase) => (
                    <tr
                      key={kase.id}
                      onClick={() => setSelected(kase.id)}
                      aria-selected={selected === kase.id}
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelected(kase.id);
                        }
                      }}
                    >
                      <td>
                        <RiskDial score={kase.risk_score} />
                      </td>
                      <td className="mono">#{kase.id}</td>
                      <td>
                        {kase.customer_name}
                        <div className="muted" style={{ fontSize: "0.78rem" }}>
                          {kase.country} · {kase.assigned_to_name ?? "Unassigned"}
                        </div>
                      </td>
                      <td>
                        <Badge>{kase.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {selected === null ? (
          <Card padded={false}>
            <div className="detail-empty">
              <div>
                <h3>Select a case</h3>
                <p className="muted">
                  Its risk breakdown, the policy it was scored against, and the decisions you
                  are allowed to make appear here.
                </p>
              </div>
            </div>
          </Card>
        ) : (
          <CaseDetail
            caseId={selected}
            onClose={() => setSelected(null)}
            onChanged={refresh}
          />
        )}
      </div>
    </>
  );
}
