import { useIdentity } from "../platform/identity";
import { initials } from "../platform/ui";

/**
 * Demo control, dressed as the account chip it replaces: in the real thing the
 * name here comes from Entra ID, not a dropdown.
 */
export function UserSwitcher() {
  const { identity, employees, signIn } = useIdentity();

  return (
    <div className="user-chip">
      <div className="avatar" aria-hidden>
        {identity ? initials(identity.name) : "?"}
      </div>
      <div>
        <select
          value={identity?.sub ?? ""}
          onChange={(event) => signIn(Number(event.target.value))}
          aria-label="Signed in as (demo)"
        >
          <option value="" disabled>
            Choose a user
          </option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.name}
            </option>
          ))}
        </select>
        <div className="muted" style={{ paddingLeft: "0.5rem", fontSize: "0.72rem" }}>
          {identity ? identity.groups.join(" · ") : "Not signed in"}
        </div>
      </div>
    </div>
  );
}
