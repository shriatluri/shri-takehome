import { apiGet, type AuditEntry } from "./api";
import { useApiList } from "./useApiList";

/** Part of the template: any app built on it gets the same log. */
export function AuditPage() {
  const { data: entries, error } = useApiList<AuditEntry>(() => apiGet<AuditEntry[]>("/audit"));

  if (error) {
    return <p role="alert">{error}</p>;
  }
  return (
    <>
      <p>
        Each entry hashes the one before it. Showing the 100 most recent; paging, filters
        and the chain-verify endpoint arrive in PR 5.
      </p>
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
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td>{entry.id}</td>
              <td>{new Date(entry.timestamp).toLocaleString()}</td>
              <td>{entry.employee_name ?? "System"}</td>
              <td>{entry.action}</td>
              <td>
                {entry.record_type} {entry.record_id}
              </td>
              <td title={entry.hash}>{entry.hash.slice(0, 12)}…</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
