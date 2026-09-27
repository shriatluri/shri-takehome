import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { apiGet, apiPost, setDemoUser, type Employee } from "./api";

// Mirrors the claim the backend builds from the X-Demo-User header.
export type Identity = {
  sub: number;
  name: string;
  groups: string[];
};

type IdentityContextValue = {
  identity: Identity | null;
  employees: Employee[];
  signIn: (employeeId: number) => void;
};

const IdentityContext = createContext<IdentityContextValue | null>(null);
const STORAGE_KEY = "demo-user-id";

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [userId, setUserId] = useState<number | null>(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? Number(stored) : null;
  });

  useEffect(() => {
    apiGet<Employee[]>("/demo/employees").then(setEmployees).catch(() => setEmployees([]));
  }, []);

  useEffect(() => {
    setDemoUser(userId);
    if (userId === null) {
      window.localStorage.removeItem(STORAGE_KEY);
      setIdentity(null);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, String(userId));
    // Switching user is this demo's login, and the backend audits it as one.
    apiPost<Identity>("/demo/sign-in").then(setIdentity).catch(() => setIdentity(null));
  }, [userId]);

  return (
    <IdentityContext.Provider value={{ identity, employees, signIn: setUserId }}>
      {children}
    </IdentityContext.Provider>
  );
}

export function useIdentity(): IdentityContextValue {
  const value = useContext(IdentityContext);
  if (!value) {
    throw new Error("useIdentity must be used inside an IdentityProvider");
  }
  return value;
}

export function inGroups(identity: Identity | null, groups: string[]): boolean {
  return identity !== null && groups.every((group) => identity.groups.includes(group));
}
