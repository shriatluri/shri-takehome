import { useState } from "react";

import { apiPost } from "../../platform/api";

const EMPTY = {
  full_name: "",
  dob: "",
  country: "",
  address: "",
  ssn: "",
  document_expiry: "",
  document_quality: "Clear",
};

/**
 * The customer-facing signup, standing in for the fintech's own. It is
 * anonymous — the pipeline behind it runs as the system identity — and it
 * reports nothing back but "Received": the outcome is the reviewer's to see.
 */
export function SubmissionForm() {
  const [form, setForm] = useState(EMPTY);
  const [state, setState] = useState<"editing" | "sending" | "received" | "failed">("editing");

  const field = (name: keyof typeof EMPTY) => ({
    value: form[name],
    onChange: (event: { target: { value: string } }) =>
      setForm({ ...form, [name]: event.target.value }),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setState("sending");
    apiPost("/submissions", { ...form, document_expiry: form.document_expiry || null })
      .then(() => {
        setForm(EMPTY);
        setState("received");
      })
      .catch(() => setState("failed"));
  };

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "0.9rem" }}>
      <div className="grid-2">
        <label className="field">
          Full name
          <input required {...field("full_name")} />
        </label>
        <label className="field">
          Date of birth
          <input required type="date" {...field("dob")} />
        </label>
        <label className="field">
          Country
          <input required placeholder="e.g. Volgaria" {...field("country")} />
        </label>
        <label className="field">
          SSN
          <input required placeholder="900-00-0000" {...field("ssn")} />
        </label>
        <label className="field">
          Document expiry
          <input type="date" {...field("document_expiry")} />
        </label>
        <label className="field">
          Document quality
          <select {...field("document_quality")}>
            <option>Clear</option>
            <option>Blurry</option>
            <option>Fake</option>
          </select>
        </label>
      </div>
      <label className="field">
        Address
        <input required {...field("address")} />
      </label>

      <div className="row spread">
        <p className="muted">
          Runs the mock IDV and sanctions checks, scores the submission, and files a case if
          one is needed.
        </p>
        <button className="btn btn-primary" type="submit" disabled={state === "sending"}>
          {state === "sending" ? "Submitting…" : "Submit"}
        </button>
      </div>

      {state === "received" && <p className="muted">Received.</p>}
      {state === "failed" && <p role="alert">Could not submit.</p>}
    </form>
  );
}
