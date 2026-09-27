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
    <section className="demo-controls">
      <h2>Customer submission</h2>
      <form onSubmit={submit}>
        <label>
          Full name <input required {...field("full_name")} />
        </label>
        <label>
          Date of birth <input required type="date" {...field("dob")} />
        </label>
        <label>
          Country <input required {...field("country")} />
        </label>
        <label>
          Address <input required {...field("address")} />
        </label>
        <label>
          SSN <input required {...field("ssn")} />
        </label>
        <label>
          Document expiry <input type="date" {...field("document_expiry")} />
        </label>
        <label>
          Document quality{" "}
          <select {...field("document_quality")}>
            <option>Clear</option>
            <option>Blurry</option>
            <option>Fake</option>
          </select>
        </label>
        <button type="submit" disabled={state === "sending"}>
          Submit
        </button>
      </form>
      {state === "received" && <p>Received.</p>}
      {state === "failed" && <p role="alert">Could not submit.</p>}
    </section>
  );
}
