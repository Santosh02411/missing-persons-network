import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { approveCase, claimCase, dismissCase, getCase, updateCaseStatus } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import { listSightingsForCase } from "../api/sightings";
import SightingForm from "../components/SightingForm";
import StatusBadge from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";

const STATUS_OPTIONS = ["open", "lead_found", "resolved"];

export default function CaseDetail() {
  const { caseId } = useParams();
  const { user, isAuthenticated } = useAuth();

  const [caseItem, setCaseItem] = useState(null);
  const [sightings, setSightings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  const loadCase = useCallback(async () => {
    try {
      const [{ data: caseData }, { data: sightingData }] = await Promise.all([
        getCase(caseId),
        listSightingsForCase(caseId),
      ]);
      setCaseItem(caseData);
      setSightings(sightingData);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't load this case."));
    } finally {
      setIsLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  async function handleApproveCase() {
    setActionError(null);
    setActionBusy(true);
    try {
      const { data } = await approveCase(caseId);
      setCaseItem(data);
    } catch (err) {
      setActionError(extractErrorMessage(err, "Couldn't approve this case."));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleClaim() {
    setActionError(null);
    setActionBusy(true);
    try {
      const { data } = await claimCase(caseId);
      setCaseItem(data);
    } catch (err) {
      setActionError(extractErrorMessage(err, "Couldn't claim this case."));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleStatusChange(newStatus) {
    setActionError(null);
    setActionBusy(true);
    try {
      const { data } = await updateCaseStatus(caseId, newStatus);
      setCaseItem(data);
    } catch (err) {
      setActionError(extractErrorMessage(err, "Couldn't update the case status."));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleDismissCase() {
    setActionError(null);
    setActionBusy(true);
    try {
      const { data } = await dismissCase(caseId);
      setCaseItem(data);
    } catch (err) {
      setActionError(extractErrorMessage(err, "Couldn't dismiss this case."));
    } finally {
      setActionBusy(false);
    }
  }

  if (isLoading) return <div className="container"><p className="spinner-text">Loading…</p></div>;
  if (error) return <div className="container"><div className="alert alert-error">{error}</div></div>;
  if (!caseItem) return null;

  const isAuthorityOrAdmin = isAuthenticated && (user.role === "authority" || user.role === "admin");
  const isAssignedAuthority =
    isAuthenticated && user.role === "authority" && caseItem.assigned_authority_id === user.id;
  const isAdmin = isAuthenticated && user.role === "admin";
  const isPendingReview = caseItem.status === "pending_review";
  const canApprove = isAuthorityOrAdmin && isPendingReview && user.is_verified !== false;
  const canClaim =
    isAuthorityOrAdmin && !isPendingReview && !caseItem.assigned_authority_id && user.is_verified !== false;
  const canChangeStatus = isAssignedAuthority || isAdmin;
  const isClosed = caseItem.status === "resolved" || caseItem.status === "dismissed";
  const canDismiss =
    !isClosed && (isAdmin || isPendingReview || isAssignedAuthority) && isAuthorityOrAdmin;

  return (
    <div className="container">
      <div className="case-detail-header">
        {caseItem.photo_url ? (
          <img src={caseItem.photo_url} alt={caseItem.name} className="case-detail-photo" />
        ) : (
          <div className="case-detail-photo-placeholder">No photo provided</div>
        )}

        <div className="case-detail-info">
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>{caseItem.name}</h2>
            <StatusBadge status={caseItem.status} />
          </div>

          {caseItem.age_at_disappearance != null && (
            <>
              <div className="case-detail-label">Age at disappearance</div>
              <div>{caseItem.age_at_disappearance}</div>
            </>
          )}

          <div className="case-detail-label">Last seen</div>
          <div>{caseItem.last_seen_address}</div>
          <div className="field-hint">
            {new Date(caseItem.last_seen_at).toLocaleString()}
          </div>

          <div className="case-detail-label">Description</div>
          <div>{caseItem.description}</div>

          {actionError && <div className="alert alert-error" style={{ marginTop: 16 }}>{actionError}</div>}

          {isPendingReview && !isAuthorityOrAdmin && (
            <p className="field-hint" style={{ marginTop: 16 }}>
              This case is awaiting authority approval before it becomes public.
            </p>
          )}

          {(canApprove || canDismiss) && (
            <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
              {canApprove && (
                <button className="btn btn-primary" onClick={handleApproveCase} disabled={actionBusy}>
                  Approve this case
                </button>
              )}
              {canDismiss && (
                <button className="btn btn-danger" onClick={handleDismissCase} disabled={actionBusy}>
                  Dismiss this case
                </button>
              )}
            </div>
          )}

          {canClaim && (
            <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={handleClaim} disabled={actionBusy}>
              Claim this case
            </button>
          )}

          {isAuthorityOrAdmin && caseItem.assigned_authority_id && !canChangeStatus && (
            <p className="field-hint" style={{ marginTop: 16 }}>
              This case is assigned to another authority.
            </p>
          )}

          {canChangeStatus && (
            <div className="field" style={{ marginTop: 16, maxWidth: 240 }}>
              <label htmlFor="status">Update status</label>
              <select
                id="status"
                value={caseItem.status}
                disabled={actionBusy}
                onChange={(e) => handleStatusChange(e.target.value)}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      <section style={{ marginBottom: 40 }}>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Sightings ({sightings.length})</h3>
        </div>
        {sightings.length === 0 ? (
          <p className="field-hint">No sightings reported yet.</p>
        ) : (
          <div className="sighting-list">
            {sightings.map((s) => (
              <div key={s.id} className="sighting-item">
                <div className="sighting-item-header">
                  <StatusBadge status={s.status} />
                  <span className="sighting-item-meta">
                    {new Date(s.created_at).toLocaleString()}
                  </span>
                </div>
                <div>{s.description}</div>
                <div className="field-hint">{s.address_text}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>Report a sighting</h3>
        </div>
        <SightingForm
          caseId={caseItem.id}
          defaultCenter={caseItem.last_seen_location}
          onSubmitted={loadCase}
        />
      </section>
    </div>
  );
}
