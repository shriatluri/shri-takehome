import { useState } from "react";

import { ApiError, apiGet, apiPut, type PolicyRule } from "../../platform/api";
import { Card, Skeleton, useToast } from "../../platform/ui";
import { useApiList } from "../../platform/useApiList";

const LABELS: Record<string, string> = {
  auto_approve_below: "Auto-approve below",
  escalate_above: "Escalate above",
  sanctions_match_threshold: "Sanctions match threshold",
  doc_expiry_window_days: "Document expiry window (days)",
  high_risk_countries: "High-risk countries",
};

/**
 * Publishing a rule never overwrites: the row in force is closed and the next
 * version inserted, so cases already scored keep the snapshot they recorded.
 */
export function PolicyPage({ search }: { search: string }) {
  const { data: rules, error, loading, refresh } = useApiList<PolicyRule>(
    () => apiGet<PolicyRule[]>("/policy-rules"),
  );
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const toast = useToast();

  const term = search.trim().toLowerCase();
  const current = rules
    .filter((rule) => rule.valid_to === null)
    .filter((rule) => !term || rule.rule_name.includes(term));

  const publish = (rule: PolicyRule) => {
    const value = drafts[rule.rule_name] ?? rule.value;
    setSaving(rule.rule_name);
    apiPut<PolicyRule>(`/policy-rules/${rule.rule_name}`, { value })
      .then((published) => {
        toast(`${LABELS[rule.rule_name] ?? rule.rule_name} is now version ${published.version}`);
        setDrafts((all) => {
          const { [rule.rule_name]: _dropped, ...rest } = all;
          return rest;
        });
        refresh();
      })
      .catch((e: ApiError) => toast(e.message, "error"))
      .finally(() => setSaving(null));
  };

  if (error) {
    return (
      <Card title="Policy rules unavailable">
        <p role="alert">{error}</p>
      </Card>
    );
  }
  if (loading) {
    return <Card title="Policy rules">{<Skeleton rows={5} />}</Card>;
  }

  return (
    <>
      <Card
        title="Rules in force"
        action={
          <span className="muted">
            Publishing closes the current version and opens the next. Cases already scored keep
            theirs.
          </span>
        }
      >
        {current.map((rule) => {
          const draft = drafts[rule.rule_name] ?? rule.value;
          const changed = draft.trim() !== rule.value;
          return (
            <div className="rule" key={rule.rule_name}>
              <label htmlFor={rule.rule_name}>
                {LABELS[rule.rule_name] ?? rule.rule_name}
                <small className="muted">
                  v{rule.version} · {rule.changed_by_name ?? "system"}
                </small>
              </label>
              <input
                id={rule.rule_name}
                value={draft}
                onChange={(event) =>
                  setDrafts((all) => ({ ...all, [rule.rule_name]: event.target.value }))
                }
              />
              <button
                className="btn btn-primary"
                disabled={!changed || saving === rule.rule_name}
                onClick={() => publish(rule)}
              >
                {saving === rule.rule_name ? "Publishing…" : `Publish v${rule.version + 1}`}
              </button>
            </div>
          );
        })}
      </Card>

      <Card padded={false} title="Version history">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rule</th>
                <th>Version</th>
                <th>Value</th>
                <th>In force</th>
                <th>Published by</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id}>
                  <td className="mono">{rule.rule_name}</td>
                  <td className="mono">v{rule.version}</td>
                  <td>{rule.value}</td>
                  <td>
                    {new Date(rule.valid_from).toLocaleDateString()} –{" "}
                    {rule.valid_to ? new Date(rule.valid_to).toLocaleDateString() : "now"}
                  </td>
                  <td>{rule.changed_by_name ?? "system"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
