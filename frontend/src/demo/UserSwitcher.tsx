import { useIdentity } from "../platform/identity";

/** Demo control. Stands in for an Entra ID login. */
export function UserSwitcher() {
  const { identity, employees, signIn } = useIdentity();

  return (
    <section className="demo-controls">
      <h2>Demo controls</h2>
      <label>
        Signed in as{" "}
        <select
          value={identity?.sub ?? ""}
          onChange={(event) => signIn(Number(event.target.value))}
        >
          <option value="" disabled>
            Choose a user
          </option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.name} — {employee.team} {employee.level}
            </option>
          ))}
        </select>
      </label>
      {identity && <p>Claim groups: {identity.groups.join(", ")}</p>}
    </section>
  );
}
