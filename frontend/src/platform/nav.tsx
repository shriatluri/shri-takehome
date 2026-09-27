import { type ReactNode } from "react";

import { inGroups, type Identity } from "./identity";

export type Page = {
  id: string;
  label: string;
  // Groups the claim must hold for the page to be offered. The backend refuses
  // the request anyway; hiding the tab only saves the user a 403.
  groups: string[];
  // Where the page sits, for the breadcrumb.
  section: string;
  // `search` is the topbar query, so one box filters whichever page is open.
  render: (search: string) => ReactNode;
};

export function visiblePages(pages: Page[], identity: Identity | null): Page[] {
  return pages.filter((page) => inGroups(identity, page.groups));
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
  search: "M11 4a7 7 0 100 14 7 7 0 000-14zm9 16l-4.2-4.2",
  audit: "M12 3l8 4v5c0 5-3.4 7.7-8 9-4.6-1.3-8-4-8-9V7l8-4z",
  form: "M8 4h8a2 2 0 012 2v12a2 2 0 01-2 2H8a2 2 0 01-2-2V6a2 2 0 012-2zm1 5h6M9 13h6M9 17h3",
};
