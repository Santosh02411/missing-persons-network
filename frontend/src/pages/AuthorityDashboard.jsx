import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { assignedToMe } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import { pendingSightings, reviewSighting } from "../api/sightings";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";

export default function AuthorityDashboard() {
  const { user } = useAuth();
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
      const [{ data: sightings }, { data: cases }] = await Promise.all([
        pendingSightings(),
        assignedToMe(),
      ]);
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
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <section style={{ marginBottom: 40 }}>
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
                  <div>
                    <StatusBadge status={s.status} />{" "}
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

      <section>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>My assigned cases ({assignedCases.length})</h3>
        </div>
        {assignedCases.length === 0 ? (
          <p className="field-hint">
            You haven't claimed any cases yet — open a case from the{" "}
            <Link to="/">case list</Link> and claim it there.
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
