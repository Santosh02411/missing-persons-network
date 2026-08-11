import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  approveCase,
  claimCase,
  dismissCase,
  getCase,
  getCaseFlyer,
  getWatchStatus,
  unwatchCase,
  updateCaseStatus,
  watchCase,
} from "../api/cases";
import { extractErrorMessage } from "../api/client";
import { listSightingsForCase } from "../api/sightings";
import CaseInvestigationPanel from "../components/CaseInvestigationPanel";
import EmergencyContactsBanner from "../components/EmergencyContactsBanner";
import MatchScoreBadge from "../components/MatchScoreBadge";
import ShareCaseForm from "../components/ShareCaseForm";
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
  const [isSharing, setIsSharing] = useState(false);
  const [isFlyerLoading, setIsFlyerLoading] = useState(false);
  const [isWatching, setIsWatching] = useState(false);
  const [isWatchBusy, setIsWatchBusy] = useState(false);

  const loadCase = useCallback(async () => {
    try {
      const requests = [getCase(caseId), listSightingsForCase(caseId)];
      if (isAuthenticated) requests.push(getWatchStatus(caseId));
      const results = await Promise.all(requests);
      setCaseItem(results[0].data);
      setSightings(results[1].data);
      if (isAuthenticated && results[2]) setIsWatching(results[2].data.is_watching);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't load this case."));
    } finally {
      setIsLoading(false);
    }
  }, [caseId, isAuthenticated]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  async function handleToggleWatch() {
    setIsWatchBusy(true);
    try {
      if (isWatching) {
        await unwatchCase(caseId);
        setIsWatching(false);
      } else {
        await watchCase(caseId);
        setIsWatching(true);
      }
    } catch (err) {
      setActionError(extractErrorMessage(err, "Couldn't update your watch status."));
    } finally {
      setIsWatchBusy(false);
    }
  }

  async function handleDownloadFlyer() {
    setActionError(null);
    setIsFlyerLoading(true);
    try {
      const { data } = await getCaseFlyer(caseId);
      const blobUrl = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      window.open(blobUrl, "_blank");
      // Revoke a little later rather than immediately -- the new tab/window
      // needs the blob URL to still be valid by the time it finishes
      // opening and loading it.
      setTimeout(() => URL.revokeObjectURL(blobUrl), 30000);
    } catch (err) {
      setActionError(extractErrorMessage(err, "Couldn't generate the flyer."));
    } finally {
      setIsFlyerLoading(false);
    }
  }

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
      {(caseItem.status === "open" || caseItem.status === "lead_found" || caseItem.status === "pending_review") && (
        <EmergencyContactsBanner />
      )}
      <div className="case-detail-header">
        {caseItem.photo_url ? (
          <img src={caseItem.photo_url} alt={caseItem.name} className="case-detail-photo" />
        ) : (
          <div className="case-detail-photo-placeholder">No photo provided</div>
        )}
        {caseItem.age_progressed_photo_url && (
          <div>
            <img
              src={caseItem.age_progressed_photo_url}
              alt={`${caseItem.name} (age-progressed)`}
              className="case-detail-photo"
            />
            <div className="field-hint" style={{ marginTop: 4, maxWidth: 220 }}>
              Age-progressed likeness
              {caseItem.age_progression_note ? ` — ${caseItem.age_progression_note}` : ""}
            </div>
          </div>
        )}

        <div className="case-detail-info">
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>{caseItem.name}</h2>
            <StatusBadge status={caseItem.status} />
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              onClick={handleDownloadFlyer}
              disabled={isFlyerLoading}
            >
              {isFlyerLoading ? "Preparing flyer…" : "Download flyer (PDF)"}
            </button>

            {isAuthenticated && (
              <button
                type="button"
                className={isWatching ? "btn btn-primary" : "btn btn-secondary"}
                style={{ fontSize: "0.85rem", padding: "6px 12px" }}
                onClick={handleToggleWatch}
                disabled={isWatchBusy}
              >
                {isWatching ? "Watching — get email updates" : "Watch this case"}
              </button>
            )}
          </div>

          {caseItem.age_at_disappearance != null && (
            <>
              <div className="case-detail-label">Age at disappearance</div>
              <div>{caseItem.age_at_disappearance}</div>
            </>
          )}

          {(caseItem.height_cm || caseItem.eye_color || caseItem.hair_color || caseItem.blood_type) && (
            <>
              <div className="case-detail-label">Physical identifiers</div>
              <div>
                {[
                  caseItem.height_cm ? `${caseItem.height_cm} cm` : null,
                  caseItem.eye_color ? `${caseItem.eye_color} eyes` : null,
                  caseItem.hair_color ? `${caseItem.hair_color} hair` : null,
                  caseItem.blood_type ? `Blood type ${caseItem.blood_type}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </>
          )}

          {caseItem.distinguishing_marks && (
            <>
              <div className="case-detail-label">Distinguishing marks</div>
              <div>{caseItem.distinguishing_marks}</div>
            </>
          )}

          {caseItem.medical_conditions && (
            <>
              <div className="case-detail-label">Medical conditions</div>
              <div>{caseItem.medical_conditions}</div>
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

          {(isAssignedAuthority || isAdmin) && !isSharing && (
            <button
              className="btn btn-secondary"
              style={{ marginTop: 16 }}
              onClick={() => setIsSharing(true)}
            >
              Share with another authority
            </button>
          )}
          {isSharing && <ShareCaseForm caseId={caseItem.id} onClose={() => setIsSharing(false)} />}
        </div>
      </div>

      {isAuthenticated && (user.role === "authority" || user.role === "admin") && (
        <CaseInvestigationPanel
          caseId={caseItem.id}
          currentUserId={user.id}
          canManageCollaborators={isAssignedAuthority || isAdmin}
          ageProgressedPhotoUrl={caseItem.age_progressed_photo_url}
          ageProgressionNote={caseItem.age_progression_note}
          onAgeProgressionUpdated={(updated) => setCaseItem(updated)}
        />
      )}

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
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <StatusBadge status={s.status} />
                    <MatchScoreBadge score={s.photo_match_score} />
                  </div>
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
