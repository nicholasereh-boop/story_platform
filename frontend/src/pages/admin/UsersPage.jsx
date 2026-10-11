import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listUsers, patchUser, resendUserVerification, revokeUserSessions } from "../../api/security";
import { useAuth } from "../../auth/AuthContext";
import ConfirmDialog from "../../components/ConfirmDialog";
import Pagination from "../../components/Pagination";
import { fmtDate, fmtDateTime } from "../../utils/format";
import { cleanParams } from "../../utils/audit";

const ROLES = [{ value: "", label: "All roles" }, { value: "reader", label: "Readers" }, { value: "staff", label: "Staff" }, { value: "superuser", label: "Superusers" }];
const ACTIVE = [{ value: "", label: "Any status" }, { value: "1", label: "Active" }, { value: "0", label: "Deactivated" }];
const VERIFIED = [{ value: "", label: "Any email state" }, { value: "1", label: "Verified" }, { value: "0", label: "Not verified" }];
const EMPTY = { q: "", role: "", active: "", verified: "" };
const ROLE_LABEL = { reader: "Reader", staff: "Staff", superuser: "Superuser" };

// Why a button is disabled (shown as its tooltip and read by screen readers), or "" when the action is allowed.
// These mirror the rules the SERVER enforces (backend apps/accounts/admin_views.py); the server is the real gate.
export function actionRules({ me, target, isSuperuser, lastSuperuser }) {
  const self = me?.id === target.id;
  const deniedSuper = target.is_superuser && !isSuperuser ? "Only a superuser can change a superuser account." : "";
  const gone = target.anonymised ? "This account was deleted by its owner." : "";
  return {
    toggleActive: gone || deniedSuper || (target.is_active && self ? "You cannot deactivate yourself." : "") ||
      (target.is_active && target.is_superuser && lastSuperuser ? "This is the only active superuser. Make another superuser first." : ""),
    toggleStaff: gone || (!isSuperuser ? "Only a superuser can grant or remove the staff role." : "") ||
      (target.is_superuser ? "A superuser always has the staff role." : "") || (self ? "You cannot change your own role." : ""),
    sessions: gone || deniedSuper,
    verification: gone || deniedSuper || (!target.is_active ? "This account is deactivated." : "") || (target.email_verified ? "Already verified." : ""),
  };
}

function ActionButton({ reason, onClick, children }) {
  return (
    <button type="button" className="btn secondary small" disabled={Boolean(reason)} title={reason || undefined} aria-label={reason ? `${children} (unavailable: ${reason})` : undefined} onClick={onClick}>
      {children}
    </button>
  );
}

// Admin: all accounts, with role changes for superusers. Every action asks for confirmation first.
export default function UsersPage() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const isSuperuser = Boolean(me?.is_superuser);
  const [draft, setDraft] = useState(EMPTY);
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [pending, setPending] = useState(null); // {user, kind}
  const [notice, setNotice] = useState("");

  const params = cleanParams(filters, page);
  const users = useQuery({ queryKey: ["admin", "users", params], queryFn: () => listUsers(params), placeholderData: (prev) => prev });
  // Is there more than one active superuser? Needed to explain why the last one cannot be deactivated.
  const supers = useQuery({ queryKey: ["admin", "users", "superusers"], queryFn: () => listUsers({ role: "superuser", active: "1", page_size: 2 }) });
  const lastSuperuser = (supers.data?.pagination?.count ?? 2) <= 1;

  const run = useMutation({
    mutationFn: ({ user, kind }) => {
      if (kind === "deactivate") return patchUser(user.id, { is_active: false });
      if (kind === "activate") return patchUser(user.id, { is_active: true });
      if (kind === "grant") return patchUser(user.id, { is_staff: true });
      if (kind === "revoke-staff") return patchUser(user.id, { is_staff: false });
      if (kind === "sessions") return revokeUserSessions(user.id);
      return resendUserVerification(user.id);
    },
    onSuccess: (_result, { user, kind }) => {
      setNotice(DONE[kind](user));
      setPending(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });

  const apply = (event) => {
    event.preventDefault();
    setPage(1);
    setFilters(draft);
  };
  const ask = (user, kind) => { run.reset(); setNotice(""); setPending({ user, kind }); };
  const rows = users.data?.items || [];
  const name = (u) => u.display_name || u.email;

  return (
    <div className="users-page">
      <h1>Users</h1>
      <form className="filters row wrap" onSubmit={apply} role="search" aria-label="Filter users">
        <div className="field">
          <label htmlFor="user-q">Search</label>
          <input id="user-q" type="search" value={draft.q} placeholder="Email or name" onChange={(e) => setDraft({ ...draft, q: e.target.value })} />
        </div>
        <Select id="user-role" label="Role" value={draft.role} options={ROLES} onChange={(v) => setDraft({ ...draft, role: v })} />
        <Select id="user-active" label="Status" value={draft.active} options={ACTIVE} onChange={(v) => setDraft({ ...draft, active: v })} />
        <Select id="user-verified" label="Email" value={draft.verified} options={VERIFIED} onChange={(v) => setDraft({ ...draft, verified: v })} />
        <button className="btn">Apply</button>
        <button type="button" className="btn ghost" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(1); }}>Clear</button>
      </form>

      {notice && <div className="notice info" role="status">{notice}</div>}
      {users.isLoading && <p className="muted">Loading users…</p>}
      {users.isError && <div className="notice error" role="alert">{users.error.friendly} <button type="button" className="link-button" onClick={() => users.refetch()}>Try again</button></div>}
      {users.isSuccess && rows.length === 0 && <p className="empty">No users match these filters.</p>}

      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table users-table">
            <caption className="sr-only">Users</caption>
            <thead>
              <tr><th scope="col">User</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Joined</th><th scope="col">Last login</th><th scope="col">Activity</th><th scope="col">Actions</th></tr>
            </thead>
            <tbody>
              {rows.map((u) => {
                const rules = actionRules({ me, target: u, isSuperuser, lastSuperuser });
                return (
                  <tr key={u.id}>
                    <th scope="row">
                      <span className="user-name">{name(u)}</span>
                      <span className="muted small block">{u.email}</span>
                    </th>
                    <td><span className={`badge role-${u.role}`}>{ROLE_LABEL[u.role] || u.role}</span></td>
                    <td>
                      <span className={`badge ${u.is_active ? "published" : "archived"}`}>{u.is_active ? "Active" : "Deactivated"}</span>{" "}
                      <span className={`badge ${u.email_verified ? "published" : "scheduled"}`}>{u.email_verified ? "Verified" : "Not verified"}</span>
                      {u.mfa_enabled && <span className="badge role-staff"> 2-step</span>}
                    </td>
                    <td>{fmtDate(u.date_joined)}</td>
                    <td>{u.last_login ? fmtDateTime(u.last_login) : "Never"}</td>
                    <td className="small">{u.comment_count} comments, {u.like_count} likes</td>
                    <td>
                      <div className="row wrap">
                        <ActionButton reason={rules.toggleActive} onClick={() => ask(u, u.is_active ? "deactivate" : "activate")}>{u.is_active ? "Deactivate" : "Activate"}</ActionButton>
                        <ActionButton reason={rules.toggleStaff} onClick={() => ask(u, u.is_staff ? "revoke-staff" : "grant")}>{u.is_staff ? "Remove staff" : "Make staff"}</ActionButton>
                        <ActionButton reason={rules.sessions} onClick={() => ask(u, "sessions")}>Sign out everywhere</ActionButton>
                        <ActionButton reason={rules.verification} onClick={() => ask(u, "verification")}>Resend verification</ActionButton>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <Pagination pagination={users.data?.pagination} onPage={setPage} />

      {pending && (
        <ConfirmDialog
          title={CONFIRM[pending.kind].title}
          message={CONFIRM[pending.kind].message(pending.user)}
          confirmLabel={CONFIRM[pending.kind].button}
          danger={CONFIRM[pending.kind].danger}
          busy={run.isPending}
          onConfirm={() => run.mutate(pending)}
          onCancel={() => setPending(null)}
        >
          {run.isError && <p className="field-error" role="alert">{run.error.friendly}</p>}
        </ConfirmDialog>
      )}
    </div>
  );
}

function Select({ id, label, value, options, onChange }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

const CONFIRM = {
  deactivate: { title: "Deactivate this account?", button: "Deactivate", danger: true, message: (u) => `${u.email} will be signed out at once and will not be able to log in until you activate the account again.` },
  activate: { title: "Activate this account?", button: "Activate", danger: false, message: (u) => `${u.email} will be able to log in again.` },
  grant: { title: "Give staff access?", button: "Make staff", danger: true, message: (u) => `${u.email} will be able to open the admin area and manage stories, media and comments.` },
  "revoke-staff": { title: "Remove staff access?", button: "Remove staff", danger: true, message: (u) => `${u.email} will lose access to the admin area and will be signed out at once.` },
  sessions: { title: "Sign this user out everywhere?", button: "Sign out", danger: true, message: (u) => `Every device where ${u.email} is logged in will be signed out.` },
  verification: { title: "Resend the verification email?", button: "Send email", danger: false, message: (u) => `A new verification link will be sent to ${u.email}.` },
};
const DONE = {
  deactivate: (u) => `${u.email} was deactivated and signed out.`,
  activate: (u) => `${u.email} was activated.`,
  grant: (u) => `${u.email} now has staff access.`,
  "revoke-staff": (u) => `${u.email} no longer has staff access.`,
  sessions: (u) => `${u.email} was signed out of every device.`,
  verification: (u) => `A verification email was sent to ${u.email}.`,
};
