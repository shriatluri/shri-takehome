import { type ReactNode } from "react";

import { inGroups, useIdentity, type Identity } from "./identity";

export type Page = {
  id: string;
  label: string;
  // Groups the claim must hold for the page to be offered. The backend refuses
  // the request anyway; hiding the tab only saves the user a 403.
  groups: string[];
  // Sidebar heading this page sits under.
  section: string;
  icon: ReactNode;
  // `search` is the topbar query, so one box filters whichever page is open.
  render: (search: string) => ReactNode;
};

export function visiblePages(pages: Page[], identity: Identity | null): Page[] {
  return pages.filter((page) => inGroups(identity, page.groups));
}

export function Nav({
  pages,
  current,
  onSelect,
}: {
  pages: Page[];
  current: string;
  onSelect: (id: string) => void;
}) {
  const { identity } = useIdentity();
  const allowed = visiblePages(pages, identity);

  if (allowed.length === 0) {
    return null;
  }
  const sections = [...new Set(allowed.map((page) => page.section))];

  return (
    <>
      {sections.map((section) => (
        <div className="nav-group" key={section}>
          <span>{section}</span>
          <nav className="nav">
            {allowed
              .filter((page) => page.section === section)
              .map((page) => (
                <button
                  key={page.id}
                  onClick={() => onSelect(page.id)}
                  aria-current={page.id === current}
                >
                  {page.icon}
                  {page.label}
                </button>
              ))}
          </nav>
        </div>
      ))}
    </>
  );
}

/** Line icons, inline so the template pulls in no icon dependency. */
export function Icon({ path }: { path: string }) {
  return (
    <svg
      className="nav-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={path} />
    </svg>
  );
}

export const ICONS = {
  queue: "M4 6h16M4 12h16M4 18h10",
  search: "M11 4a7 7 0 100 14 7 7 0 000-14zm9 16l-4.2-4.2",
  audit: "M12 3l8 4v5c0 5-3.4 7.7-8 9-4.6-1.3-8-4-8-9V7l8-4z",
  form: "M8 4h8a2 2 0 012 2v12a2 2 0 01-2 2H8a2 2 0 01-2-2V6a2 2 0 012-2zm1 5h6M9 13h6M9 17h3",
};
