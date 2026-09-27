import { useState } from "react";

import { PolicyPage } from "./apps/kyc/PolicyPage";
import { QueuePage } from "./apps/kyc/QueuePage";
import { SubmissionForm } from "./apps/kyc/SubmissionForm";
import { UserSwitcher } from "./demo/UserSwitcher";
import { AuditPage } from "./platform/AuditPage";
import { IdentityProvider, useIdentity } from "./platform/identity";
import { Icon, ICONS, visiblePages, type Page } from "./platform/nav";
import { Card, Drawer, ToastProvider } from "./platform/ui";

const PAGES: Page[] = [
  {
    id: "queue",
    label: "Review queue",
    groups: ["compliance"],
    section: "Compliance",
    render: (search) => <QueuePage search={search} />,
  },
  {
    id: "policy",
    label: "Policy rules",
    groups: ["admin"],
    section: "Oversight",
    render: (search) => <PolicyPage search={search} />,
  },
  {
    id: "audit",
    label: "Audit log",
    groups: ["admin"],
    section: "Oversight",
    render: (search) => <AuditPage search={search} />,
  },
];

function Shell() {
  const { identity } = useIdentity();
  const [search, setSearch] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [pageId, setPageId] = useState<string | null>(null);
  // Compliance reaches one screen and admin two, so the switch is a pair of
  // tabs in the page head rather than a nav rail down the side.
  const pages = visiblePages(PAGES, identity);
  const current = pages.find((page) => page.id === pageId) ?? pages[0];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">KYC</div>
          <div>
            <h1>KYC Console</h1>
            <small>Internal tools</small>
          </div>
        </div>

        <label className="search">
          <Icon path={ICONS.search} />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search anything"
            aria-label="Search"
          />
        </label>

        <div className="row">
          {/* Anonymous: it stands in for the customer's own signup page, so
              it stays available whoever is signed in. */}
          <button className="btn btn-primary" onClick={() => setSubmitting(true)}>
            <Icon path={ICONS.form} />
            New submission
          </button>
          <UserSwitcher />
        </div>
      </header>

      <main className="content">
        <div className="page-head">
          <h1>{current?.label ?? "No access"}</h1>
          {pages.length > 1 ? (
            <div className="chips" role="tablist">
              {pages.map((page) => (
                <button
                  key={page.id}
                  className="chip"
                  role="tab"
                  aria-pressed={page.id === current?.id}
                  aria-selected={page.id === current?.id}
                  onClick={() => setPageId(page.id)}
                >
                  {page.label}
                </button>
              ))}
            </div>
          ) : (
            <span className="breadcrumb">
              {current?.section ?? "Compliance"} › <b>{current?.label ?? "No access"}</b>
            </span>
          )}
        </div>

        {!identity && (
          <Card title="Sign in">
            <p className="muted">
              Pick a demo user top-right. The switcher stands in for Entra ID; the backend
              reads the claim and the database decides what that user can see.
            </p>
          </Card>
        )}
        {identity && !current && (
          <Card title="No queue for this user">
            <p className="muted">
              {identity.name} is {identity.groups.join(" ")}. Operations is blocked from the
              review queue by design — the API answers 403 and the row-level security
              policies match no cases either.
            </p>
          </Card>
        )}
        {current?.render(search)}
      </main>

      {submitting && (
        <Drawer
          title="Customer submission"
          subtitle="Demo control — stands in for the fintech's own signup form"
          onClose={() => setSubmitting(false)}
        >
          <SubmissionForm />
        </Drawer>
      )}
    </div>
  );
}

export default function App() {
  return (
    <IdentityProvider>
      <ToastProvider>
        <Shell />
      </ToastProvider>
    </IdentityProvider>
  );
}
