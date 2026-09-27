import { type ReactNode } from "react";

import { inGroups, useIdentity, type Identity } from "./identity";

export type Page = {
  id: string;
  label: string;
  // Groups the claim must hold for the page to be offered. The backend refuses
  // the request anyway; hiding the tab only saves the user a 403.
  groups: string[];
  render: () => ReactNode;
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
  return (
    <nav>
      {allowed.map((page) => (
        <button
          key={page.id}
          onClick={() => onSelect(page.id)}
          aria-current={page.id === current}
        >
          {page.label}
        </button>
      ))}
    </nav>
  );
}
