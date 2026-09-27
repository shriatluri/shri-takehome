import { Fragment, useEffect, useState } from "react";

import {
  apiGet,
  type AuditEntry,
  type AuditFacets,
  type AuditVerification,
} from "./api";
import { Card, Skeleton, relativeTime } from "./ui";
import { useApiList } from "./useApiList";

const NO_FACETS: AuditFacets = { actions: [], record_types: [] };

/** Part of the template: any app built on it gets the same log. */
export function AuditPage({ search }: { search: string }) {
  const [action, setAction] = useState("");
  const [recordType, setRecordType] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [facets, setFacets] = useState<AuditFacets>(NO_FACETS);
  const [chain, setChain] = useState<AuditVerification | null>(null);
  const [verifying, setVerifying] = useState(false);

  // Filtering happens server-side, so a narrowed view still reaches entries
  // older than the page currently holds.
  const query = new URLSearchParams();
  if (action) query.set("action", action);
  if (recordType) query.set("record_type", recordType);
  const { data: entries, error, loading, refresh } = useApiList<AuditEntry>(
    () => apiGet<AuditEntry[]>(`/audit?${query}`),
    5000,
  );

  useEffect(() => {
    refresh();
  }, [action, recordType, refresh]);

  useEffect(() => {
    apiGet<AuditFacets>("/audit/facets")
      .then(setFacets)
      .catch(() => setFacets(NO_FACETS));
  }, []);

  const verify = () => {
    setVerifying(true);
    apiGet<AuditVerification>("/audit/verify")
      .then(setChain)
      .catch(() => setChain(null))
      .finally(() => setVerifying(false));
  };

  const term = search.trim().toLowerCase();
  // The same two filters again, because `entries` still holds the previous
  // answer until the refreshed request lands.
  const rows = entries
    .filter((entry) => !action || entry.action === action)
    .filter((entry) => !recordType || entry.record_type === recordType)
    .filter(
      (entry) =>
        !term ||
        entry.action.toLowerCase().includes(term) ||
        (entry.employee_name ?? "system").toLowerCase().includes(term) ||
        (entry.record_id ?? "").toLowerCase().includes(term) ||
        entry.record_type.toLowerCase().includes(term),
    );

  if (error) {
    return (
      <Card title="Audit log unavailable">
        <p role="alert">{error}</p>
      </Card>
    );
  }
  return (
    <>
      <Card title="Chain integrity" action={<span className="muted">sha256(prev_hash + row)</span>}>
        <div className="row spread">
          {chain === null ? (
            <p className="muted">
              Each entry hashes the one before it, so an edited row breaks every hash after it.
            </p>
          ) : chain.intact ? (
            <p className="verdict verdict-ok" role="status">
              Chain intact — {chain.checked} entries recomputed and matched.
            </p>
          ) : (
            <p className="verdict verdict-bad" role="alert">
              Broken at entry #{chain.broken_at} — {chain.checked} entries before it still match.
            </p>
          )}
          <button className="btn btn-primary" onClick={verify} disabled={verifying}>
            {verifying ? "Verifying…" : "Verify chain"}
          </button>
        </div>
      </Card>

      <Card
        padded={false}
        title="Audit log"
        action={
          <div className="row">
            <select
              value={action}
              onChange={(event) => setAction(event.target.value)}
              aria-label="Filter by action"
            >
              <option value="">All actions</option>
              {facets.actions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={recordType}
              onChange={(event) => setRecordType(event.target.value)}
              aria-label="Filter by record type"
            >
              <option value="">All records</option>
              {facets.record_types.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        }
      >
        {loading ? (
          <Skeleton rows={6} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>When</th>
                  <th>Who</th>
                  <th>Action</th>
                  <th>Record</th>
                  <th>Hash</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((entry) => (
                  <Fragment key={entry.id}>
                    <tr
                      aria-selected={expanded === entry.id}
                      tabIndex={0}
                      onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setExpanded(expanded === entry.id ? null : entry.id);
                        }
                      }}
                    >
                      <td className="mono">
                        <span className="chevron" aria-hidden="true">
                          {expanded === entry.id ? "▾" : "▸"}
                        </span>
                        {entry.id}
                      </td>
                      <td title={new Date(entry.timestamp).toLocaleString()}>
                        {relativeTime(entry.timestamp)}
                      </td>
                      <td>{entry.employee_name ?? "System"}</td>
                      <td className="mono">{entry.action}</td>
                      <td>
                        {entry.record_type} {entry.record_id}
                      </td>
                      <td className="mono" title={entry.hash}>
                        {entry.hash.slice(0, 12)}…
                      </td>
                    </tr>
                    {expanded === entry.id && (
                      <tr className="row-detail">
                        <td colSpan={6}>
                          <div className="grid-2">
                            <div className="field-box">
                              <span>Details</span>
                              <pre className="mono">{JSON.stringify(entry.details, null, 2)}</pre>
                            </div>
                            <div className="field-box">
                              <span>Previous hash</span>
                              <pre className="mono">{entry.prev_hash ?? "chain start"}</pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="muted">
                      No entries match these filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
