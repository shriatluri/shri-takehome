import { apiGet, type AuditEntry } from "./api";
import { Card, Skeleton, relativeTime } from "./ui";
import { useApiList } from "./useApiList";

/** Part of the template: any app built on it gets the same log. */
export function AuditPage({ search }: { search: string }) {
  const { data: entries, error, loading } = useApiList<AuditEntry>(
    () => apiGet<AuditEntry[]>("/audit"),
    5000,
  );
  const term = search.trim().toLowerCase();
  const rows = entries.filter(
    (entry) =>
      !term ||
      entry.action.toLowerCase().includes(term) ||
      (entry.employee_name ?? "system").toLowerCase().includes(term) ||
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
    <Card
      padded={false}
      title="Audit log"
      action={
        <span className="muted">
          Each entry hashes the one before it. 100 most recent; filters and chain-verify in PR 5.
        </span>
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
                <tr key={entry.id}>
                  <td className="mono">{entry.id}</td>
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
