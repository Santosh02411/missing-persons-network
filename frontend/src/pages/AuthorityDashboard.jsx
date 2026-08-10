import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { approveCase, assignedToMe, dismissCase, pendingApprovalCases } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import { pendingSightings, reviewSighting } from "../api/sightings";
import BulkImportForm from "../components/BulkImportForm";
import MatchScoreBadge from "../components/MatchScoreBadge";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";

export default function AuthorityDashboard() {
  const { user } = useAuth();
  const [pendingCases, setPendingCases] = useState([]);
  const [queue, setQueue] = useState([]);
  const [assignedCases, setAssignedCases] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const isUnverifiedAuthority = user.role === "authority" && !user.is_verified;

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const [{ data: casesToApprove }, { data: sightings }, { data: cases }] = await Promise.all([
        pendingApprovalCases(),
        pendingSightings(),
        assignedToMe(),
      ]);
      setPendingCases(casesToApprove);
      setQueue(sightings);
      setAssignedCases(cases);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't load the dashboard."));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!isUnverifiedAuthority) load();
    else setIsLoading(false);
  }, [isUnverifiedAuthority]);

  async function handleApproveCase(caseId) {
    setBusyId(caseId);
    try {
      const { data: approved } = await approveCase(caseId);
      setPendingCases((prev) => prev.filter((c) => c.id !== caseId));
      setAssignedCases((prev) => [approved, ...prev]);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't approve that case."));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDismissCase(caseId) {
    setBusyId(caseId);
    try {
      await dismissCase(caseId);
      setPendingCases((prev) => prev.filter((c) => c.id !== caseId));
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't dismiss that case."));
    } finally {
      setBusyId(null);
    }
  }

  async function handleReview(sightingId, status) {
    setBusyId(sightingId);
    try {
      await reviewSighting(sightingId, status);
      setQueue((prev) => prev.filter((s) => s.id !== sightingId));
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't update that sighting."));
    } finally {
      setBusyId(null);
    }
  }

  if (isLoading) return <div className="container"><p className="spinner-text">Loading…</p></div>;

  if (isUnverifiedAuthority) {
    return (
      <div className="container">
        <div className="empty-state">
          <h3>Your account is awaiting approval</h3>
          <p>
            An admin needs to approve your authority account before you can review sightings
            or claim cases. Check back soon.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="page-header">
        <h2 style={{ margin: 0 }}>Authority dashboard</h2>
        <BulkImportForm />
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <section className="dashboard-card">
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Cases awaiting approval ({pendingCases.length})</h3>
        </div>
        <p className="field-hint" style={{ marginTop: -8 }}>
          Newly filed cases aren't public until approved. Approving also assigns the case to you.
        </p>
        {pendingCases.length === 0 ? (
          <p className="field-hint">Nothing waiting for approval right now.</p>
        ) : (
          <div className="sighting-list">
            {pendingCases.map((c) => (
              <div key={c.id} className="sighting-item">
                <div className="sighting-item-header">
                  <div>
                    <StatusBadge status={c.status} /> <Link to={`/cases/${c.id}`}>{c.name}</Link>
                  </div>
                  <span className="sighting-item-meta">
                    {new Date(c.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="field-hint" style={{ marginBottom: 8 }}>{c.last_seen_address}</div>
                {c.possible_duplicates && c.possible_duplicates.length > 0 && (
                  <div className="alert alert-error" style={{ padding: "8px 10px", fontSize: "0.82rem", marginBottom: 8 }}>
                    <strong>
                      Possible duplicate — {c.possible_duplicates.length} similar case
                      {c.possible_duplicates.length === 1 ? "" : "s"} already on file:
                    </strong>
                    <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                      {c.possible_duplicates.map((d) => (
                        <li key={d.case_id}>
                          <Link to={`/cases/${d.case_id}`} target="_blank" rel="noreferrer">
                            {d.name}
                          </Link>{" "}
                          <span className="field-hint">
                            ({Math.round(d.similarity * 100)}% match{d.distance_km != null ? `, ${d.distance_km}km away` : ""})
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn btn-primary"
                    disabled={busyId === c.id}
                    onClick={() => handleApproveCase(c.id)}
                  >
                    Approve
                  </button>
                  <button
                    className="btn btn-danger"
                    disabled={busyId === c.id}
                    onClick={() => handleDismissCase(c.id)}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="dashboard-card">
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Pending sightings ({queue.length})</h3>
        </div>
        {queue.length === 0 ? (
          <p className="field-hint">Nothing waiting for review right now.</p>
        ) : (
          <div className="sighting-list">
            {queue.map((s) => (
              <div key={s.id} className="sighting-item">
                <div className="sighting-item-header">
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <StatusBadge status={s.status} />
                    <MatchScoreBadge score={s.photo_match_score} />{" "}
                    <Link to={`/cases/${s.case_id}`}>{s.case_name}</Link>
                  </div>
                  <span className="sighting-item-meta">
                    {new Date(s.created_at).toLocaleString()}
                  </span>
                </div>
                <div>{s.description}</div>
                <div className="field-hint" style={{ marginBottom: 8 }}>{s.address_text}</div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn btn-primary"
                    disabled={busyId === s.id}
                    onClick={() => handleReview(s.id, "verified")}
                  >
                    Verify
                  </button>
                  <button
                    className="btn btn-danger"
                    disabled={busyId === s.id}
                    onClick={() => handleReview(s.id, "dismissed")}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="dashboard-card">
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>My assigned cases ({assignedCases.length})</h3>
        </div>
        {assignedCases.length === 0 ? (
          <p className="field-hint">
            You haven't approved or claimed any cases yet.
          </p>
        ) : (
          <div className="sighting-list">
            {assignedCases.map((c) => (
              <div key={c.id} className="sighting-item">
                <div className="sighting-item-header">
                  <div>
                    <StatusBadge status={c.status} /> <Link to={`/cases/${c.id}`}>{c.name}</Link>
                  </div>
                </div>
                <div className="field-hint">{c.last_seen_address}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
