import { useEffect, useState } from "react";
import {
  approveAuthorityRequest,
  deactivateUser,
  listAuditLogs,
  listAuthorityRequests,
  listUsers,
  reactivateUser,
} from "../api/admin";
import { extractErrorMessage } from "../api/client";

function shortId(id) {
  return id ? id.slice(0, 8) : "—";
}

export default function AdminDashboard() {
  const [pending, setPending] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const [{ data: requests }, { data: logs }, { data: userList }] = await Promise.all([
        listAuthorityRequests(),
        listAuditLogs({ limit: 50 }),
        listUsers({ limit: 100 }),
      ]);
      setPending(requests);
      setAuditLogs(logs);
      setUsers(userList);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't load the dashboard."));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleApprove(userId) {
    setBusyId(userId);
    try {
      await approveAuthorityRequest(userId);
      setPending((prev) => prev.filter((u) => u.id !== userId));
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't approve that account."));
    } finally {
      setBusyId(null);
    }
  }

  async function handleToggleActive(targetUser) {
    setBusyId(targetUser.id);
    try {
      const { data } = targetUser.is_active
        ? await deactivateUser(targetUser.id)
        : await reactivateUser(targetUser.id);
      setUsers((prev) => prev.map((u) => (u.id === data.id ? data : u)));
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't update that account."));
    } finally {
      setBusyId(null);
    }
  }

  if (isLoading) return <div className="container"><p className="spinner-text">Loading…</p></div>;

  return (
    <div className="container">
      <div className="page-header">
        <h2 style={{ margin: 0 }}>Admin dashboard</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <section style={{ marginBottom: 40 }}>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Pending authority approvals ({pending.length})</h3>
        </div>

        {pending.length === 0 ? (
          <p className="field-hint">No authority accounts waiting for approval.</p>
        ) : (
          <div className="sighting-list">
            {pending.map((u) => (
              <div key={u.id} className="sighting-item">
                <div className="sighting-item-header">
                  <div>
                    <strong>{u.full_name}</strong>{" "}
                    <span className="field-hint">({u.email})</span>
                  </div>
                </div>
                <div className="field-hint" style={{ marginBottom: 8 }}>
                  {u.org_name || "No organization name provided"}
                </div>
                <button
                  className="btn btn-primary"
                  disabled={busyId === u.id}
                  onClick={() => handleApprove(u.id)}
                >
                  Approve
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section style={{ marginBottom: 40 }}>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Users ({users.length})</h3>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>2FA</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}</td>
                  <td className="mono">{u.email}</td>
                  <td>{u.role}</td>
                  <td>{u.is_active ? "Active" : "Deactivated"}</td>
                  <td>{u.totp_enabled ? "On" : "Off"}</td>
                  <td>
                    <button
                      className={u.is_active ? "btn btn-danger" : "btn btn-secondary"}
                      style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                      disabled={busyId === u.id}
                      onClick={() => handleToggleActive(u)}
                    >
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Recent activity ({auditLogs.length})</h3>
        </div>
        {auditLogs.length === 0 ? (
          <p className="field-hint">No recorded actions yet.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Action</th>
                  <th>Target</th>
                  <th>Actor</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td className="mono">{new Date(log.created_at).toLocaleString()}</td>
                    <td>{log.action}</td>
                    <td className="mono">
                      {log.target_type}:{shortId(log.target_id)}
                    </td>
                    <td className="mono">{shortId(log.actor_id)}</td>
                    <td className="mono">{JSON.stringify(log.log_metadata)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
