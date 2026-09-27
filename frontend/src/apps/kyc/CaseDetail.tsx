import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPost, type CaseDetail as Detail, type Reviewer } from "../../platform/api";
import { useIdentity } from "../../platform/identity";
import {
  Badge,
  Fact,
  RiskDial,
  Section,
  Skeleton,
  initials,
  relativeTime,
  useToast,
} from "../../platform/ui";

const DECIDED = ["Approved", "Rejected", "Suspended"];
const ACTIONS = ["Approve", "Reject", "Suspend"] as const;

/**
 * One case, and whatever this reviewer is allowed to do with it.
 *
 * The buttons below mirror the rules the backend enforces; they are a
 * convenience, not the control. Pressing one the server disagrees with returns
 * its reason, and that reason is what the toast shows.
 */
export function CaseDetail({
  caseId,
  onClose,
  onChanged,
}: {
  caseId: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { identity } = useIdentity();
  const toast = useToast();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [assignee, setAssignee] = useState("");

  const isSenior = identity?.groups.includes("senior") ?? false;

  const load = useCallback(() => {
    setDetail(null);
    setError(null);
    apiGet<Detail>(`/cases/${caseId}`)
      .then((row) => {
        setDetail(row);
        setAssignee(String(row.assigned_to ?? ""));
      })
      .catch((problem: Error) => setError(problem.message));
  }, [caseId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (isSenior) {
      apiGet<Reviewer[]>("/reviewers").then(setReviewers).catch(() => setReviewers([]));
    }
  }, [isSenior]);

  const act = (path: string, body: unknown, done: string) => {
    setBusy(true);
    apiPost(`/cases/${caseId}/${path}`, body)
      .then(() => {
        toast(done);
        setReason("");
        load();
        onChanged();
      })
      .catch((problem: Error) => toast(problem.message, "error"))
      .finally(() => setBusy(false));
  };

  if (error) {
    return (
      <section className="card">
        <div className="card-body">
          <p role="alert">{error}</p>
          <p className="muted">
            A case you are not assigned is not hidden by the API — the row-level security
            policy returns nothing, so it does not exist as far as this request is concerned.
          </p>
        </div>
      </section>
    );
  }
  if (!detail) {
    return (
      <section className="card">
        <Skeleton rows={8} />
      </section>
    );
  }

  const decided = DECIDED.includes(detail.status);
  const escalated = detail.status === "Escalated";
  const ownRecommendation = detail.recommended_by === identity?.sub;
  // Maker-checker: an Escalated case is decided by a senior who did not recommend it.
  const canDecide = decided
    ? false
    : escalated
      ? isSenior && detail.recommendation !== null && !ownRecommendation
      : true;

  return (
    <section className="card">
      <header className="card-head">
        <div className="row">
          <h2>Case #{detail.id}</h2>
          <Badge>{detail.status}</Badge>
          <span className="muted">opened {relativeTime(detail.created_at)}</span>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close case">
          ✕
        </button>
      </header>

      <div className="card-body">
        <div className="identity-strip">
          <div className="avatar" aria-hidden>
            {initials(detail.customer_name)}
          </div>
          <div style={{ flex: 1 }}>
            <h2>{detail.customer_name}</h2>
            <p className="muted">
              {detail.country} · account {detail.account_status.toLowerCase()} · assigned to{" "}
              {detail.assigned_to_name ?? "nobody"}
            </p>
          </div>
          <RiskDial score={detail.risk_score} large />
        </div>

        <Section
          title="Risk score"
          action={<span className="muted">Scored against the policy below</span>}
        >
          <ul className="reasons">
            {detail.risk_reasons.length === 0 && <li>No scored risk signals</li>}
            {detail.risk_reasons.map((item) => (
              <li key={item.reason}>
                <span>{item.reason}</span>
                <b>+{item.points}</b>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Customer">
          <div className="grid-2">
            <Fact label="Date of birth">{detail.dob}</Fact>
            <Fact label="SSN">
              <span className="mono">{detail.ssn}</span>
            </Fact>
            <Fact label="Address">{detail.address}</Fact>
            <Fact label="Account status">
              <Badge>{detail.account_status}</Badge>
            </Fact>
          </div>
        </Section>

        <Section title="Verification">
          <div className="grid-2">
            <Fact label="IDV result">
              <Badge>{detail.idv_status}</Badge>
            </Fact>
            <Fact label="Document quality">{detail.document_quality ?? "—"}</Fact>
            <Fact label="Document expiry">{detail.document_expiry ?? "—"}</Fact>
            <Fact label="Sanctions match">
              {detail.sanctions_match_name
                ? `${detail.sanctions_match_name}${
                    detail.sanctions_program ? ` · ${detail.sanctions_program}` : ""
                  }`
                : "None"}
            </Fact>
          </div>
        </Section>

        <Section title="Review">
          <div className="grid-2">
            <Fact label="Recommended">
              {detail.recommendation
                ? `${detail.recommendation} by ${detail.recommended_by_name}`
                : "—"}
            </Fact>
            <Fact label="Decided by">{detail.approved_by_name ?? "—"}</Fact>
            <Fact label="Decided">{detail.decided_at ? relativeTime(detail.decided_at) : "—"}</Fact>
            <Fact label="Reason">{detail.decision_reason || "—"}</Fact>
          </div>
        </Section>

        <Section
          title="Policy snapshot"
          action={<span className="muted">Kept on the case, so the rules can change</span>}
        >
          <ul className="reasons">
            {Object.entries(detail.policy_snapshot).map(([rule, entry]) => (
              <li key={rule}>
                <span className="mono">{rule}</span>
                <b>
                  {entry.value} <span className="muted">v{entry.version}</span>
                </b>
              </li>
            ))}
          </ul>
        </Section>
      </div>

      {!decided && (
        <div className="actions">
          <label className="field">
            Decision note
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="What did you check, and what did you conclude?"
            />
          </label>

          {escalated && detail.recommendation === null && (
            <div className="row">
              <span className="muted">Recommend:</span>
              {ACTIONS.map((action) => (
                <button
                  key={action}
                  className="btn btn-sm"
                  disabled={busy}
                  onClick={() =>
                    act(
                      "recommendation",
                      { recommendation: action, reason },
                      `Recommended ${action.toLowerCase()}`,
                    )
                  }
                >
                  {action}
                </button>
              ))}
            </div>
          )}

          {escalated && detail.recommendation !== null && !canDecide && (
            <p className="muted">
              {ownRecommendation
                ? "You recommended this case. A different compliance senior has to approve it."
                : "Waiting on a compliance senior to approve the recommendation."}
            </p>
          )}

          {canDecide && (
            <div className="row">
              {ACTIONS.map((action) => (
                <button
                  key={action}
                  className={`btn ${
                    action === "Approve" ? "btn-primary" : action === "Reject" ? "btn-danger" : ""
                  }`}
                  disabled={busy}
                  onClick={() => act("decision", { action, reason }, `Case ${action.toLowerCase()}d`)}
                >
                  {action}
                </button>
              ))}
            </div>
          )}

          {isSenior && (
            <div className="row spread">
              <label className="field" style={{ flex: 1 }}>
                Assigned reviewer
                <select value={assignee} onChange={(event) => setAssignee(event.target.value)}>
                  {reviewers.map((reviewer) => (
                    <option key={reviewer.id} value={reviewer.id}>
                      {`${reviewer.name} — ${reviewer.level}`}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="btn"
                disabled={busy || assignee === String(detail.assigned_to ?? "")}
                onClick={() => act("assignment", { assigned_to: Number(assignee) }, "Case reassigned")}
              >
                Reassign
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
