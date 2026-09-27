import { useState } from "react";

import { QueuePage } from "./apps/kyc/QueuePage";
import { SubmissionForm } from "./apps/kyc/SubmissionForm";
import { UserSwitcher } from "./demo/UserSwitcher";
import { AuditPage } from "./platform/AuditPage";
import { IdentityProvider, useIdentity } from "./platform/identity";
import { Nav, visiblePages, type Page } from "./platform/nav";

const PAGES: Page[] = [
  { id: "queue", label: "Review queue", groups: ["compliance"], render: () => <QueuePage /> },
  { id: "audit", label: "Audit log", groups: ["admin"], render: () => <AuditPage /> },
];

function Shell() {
  const { identity } = useIdentity();
  const [page, setPage] = useState("queue");
  const allowed = visiblePages(PAGES, identity);
  const current = allowed.find((candidate) => candidate.id === page) ?? allowed[0];

  return (
    <main>
      <h1>KYC Review Queue</h1>
      <UserSwitcher />
      {/* Anonymous, so it stays on the page whoever is signed in. */}
      <SubmissionForm />
      {!identity && <p>Choose a demo user to sign in.</p>}
      <Nav pages={PAGES} current={current?.id ?? ""} onSelect={setPage} />
      {identity && !current && <p>This user has no pages. Operations is blocked by design.</p>}
      {current?.render()}
    </main>
  );
}

export default function App() {
  return (
    <IdentityProvider>
      <Shell />
    </IdentityProvider>
  );
}
