import { apiGet, type Case } from "../../platform/api";
import { useApiList } from "../../platform/useApiList";

/** Read-only for now; decisions and the case detail page are PR 4. */
export function QueuePage() {
  const { data: cases, error, loading } = useApiList<Case>(() => apiGet<Case[]>("/cases"));

  if (error) {
    return <p role="alert">{error}</p>;
  }
  return (
    <>
      <p>
        Rows come back filtered by the row-level security policies, not by a query in the
        API, and the SSN is masked before it is serialized.
      </p>
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>Customer</th>
            <th>Country</th>
            <th>SSN</th>
            <th>Risk</th>
            <th>Status</th>
            <th>Assigned to</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((kase) => (
            <tr key={kase.id}>
              <td>{kase.id}</td>
              <td>{kase.customer_name}</td>
              <td>{kase.country}</td>
              <td>{kase.ssn}</td>
              <td>{kase.risk_score}</td>
              <td>{kase.status}</td>
              <td>{kase.assigned_to_name ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {loading && <p>Loading…</p>}
      {!loading && cases.length === 0 && <p>No cases visible to this user.</p>}
    </>
  );
}
