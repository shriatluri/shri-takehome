import { useEffect, useState } from "react";

import { apiGet, type Health } from "./platform/api";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Health>("/healthz").then(setHealth).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main>
      <h1>KYC Review Queue</h1>
      <p>
        Foundation only: the queue, submission form and admin pages arrive in later PRs. This
        page confirms the backend is up and the database came up seeded.
      </p>
      {error && <p role="alert">Backend unreachable: {error}</p>}
      {health && (
        <table>
          <thead>
            <tr>
              <th>Table</th>
              <th>Rows</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(health.counts).map(([table, count]) => (
              <tr key={table}>
                <td>{table}</td>
                <td>{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
