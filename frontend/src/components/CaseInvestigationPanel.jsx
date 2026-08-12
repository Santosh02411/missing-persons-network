import { useEffect, useState } from "react";
import { searchAuthorities } from "../api/authorities";
import {
  addCaseCollaborator,
  addCaseNote,
  getCaseCollaborators,
  getCaseNotes,
  removeCaseCollaborator,
  reopenCase,
  sendCaseAlert,
  updateAgeProgression,
} from "../api/cases";
import { extractErrorMessage } from "../api/client";
import PhotoUpload from "./PhotoUpload";

/**
 * canManageCollaborators: whether the current user is the case's assigned
 * authority or an admin -- controls whether the "add collaborator" picker
 * is shown. Everyone with case access can view the list, add notes, and
 * remove themselves as a collaborator.
 */
export default function CaseInvestigationPanel({
  caseId,
  currentUserId,
  canManageCollaborators,
  caseStatus,
  ageProgressedPhotoUrl,
  ageProgressionNote,
  onCaseUpdated,
}) {
  const [notes, setNotes] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [noteBody, setNoteBody] = useState("");
  const [isPosting, setIsPosting] = useState(false);
  const [error, setError] = useState(null);
  const [hasAccess, setHasAccess] = useState(true);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isAddingCollaborator, setIsAddingCollaborator] = useState(false);

  const [ageProgressedUrl, setAgeProgressedUrl] = useState(ageProgressedPhotoUrl || "");
  const [ageProgressionNoteInput, setAgeProgressionNoteInput] = useState(ageProgressionNote || "");
  const [isSavingAgeProgression, setIsSavingAgeProgression] = useState(false);

  const [isReopening, setIsReopening] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [isSubmittingReopen, setIsSubmittingReopen] = useState(false);

  const [isSendingAlert, setIsSendingAlert] = useState(false);
  const [alertResult, setAlertResult] = useState(null);

  function reload() {
    Promise.all([getCaseNotes(caseId), getCaseCollaborators(caseId)])
      .then(([{ data: noteData }, { data: collabData }]) => {
        setNotes(noteData);
        setCollaborators(collabData);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          // Not the assigned authority, a collaborator, or an admin --
          // this panel simply isn't for this viewer, not an error to show.
          setHasAccess(false);
          return;
        }
        setError(extractErrorMessage(err, "Couldn't load the investigation log."));
      });
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  useEffect(() => {
    if (!isAddingCollaborator) return;
    setIsSearching(true);
    const timeout = setTimeout(() => {
      searchAuthorities(query)
        .then(({ data }) => setResults(data))
        .catch(() => setResults([]))
        .finally(() => setIsSearching(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [query, isAddingCollaborator]);

  async function handleAddNote(e) {
    e.preventDefault();
    if (!noteBody.trim()) return;
    setError(null);
    setIsPosting(true);
    try {
      await addCaseNote(caseId, noteBody.trim());
      setNoteBody("");
      reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't add that note."));
    } finally {
      setIsPosting(false);
    }
  }

  async function handleAddCollaborator(authorityId) {
    setError(null);
    try {
      await addCaseCollaborator(caseId, authorityId);
      setIsAddingCollaborator(false);
      setQuery("");
      reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't add that collaborator."));
    }
  }

  async function handleRemoveCollaborator(userId) {
    setError(null);
    try {
      await removeCaseCollaborator(caseId, userId);
      reload();
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't remove that collaborator."));
    }
  }

  if (!hasAccess) return null;

  async function handleSaveAgeProgression(e) {
    e.preventDefault();
    if (!ageProgressedUrl) return;
    setError(null);
    setIsSavingAgeProgression(true);
    try {
      const { data } = await updateAgeProgression(caseId, {
        age_progressed_photo_url: ageProgressedUrl,
        age_progression_note: ageProgressionNoteInput || null,
      });
      if (onCaseUpdated) onCaseUpdated(data);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't save the age-progressed photo."));
    } finally {
      setIsSavingAgeProgression(false);
    }
  }

  async function handleReopen(e) {
    e.preventDefault();
    if (!reopenReason.trim()) return;
    setError(null);
    setIsSubmittingReopen(true);
    try {
      const { data } = await reopenCase(caseId, reopenReason.trim());
      if (onCaseUpdated) onCaseUpdated(data);
      setIsReopening(false);
      setReopenReason("");
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't reopen this case."));
    } finally {
      setIsSubmittingReopen(false);
    }
  }

  async function handleSendAlert() {
    setError(null);
    setAlertResult(null);
    setIsSendingAlert(true);
    try {
      const { data } = await sendCaseAlert(caseId);
      setAlertResult(data);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't send the alert."));
    } finally {
      setIsSendingAlert(false);
    }
  }

  return (
    <div className="dashboard-card" style={{ marginTop: 24 }}>
      <div className="section-heading" style={{ marginTop: 0 }}>
        <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Investigation (private)</h3>
      </div>
      <p className="field-hint" style={{ marginTop: -8, marginBottom: 16 }}>
        Only visible to authorities and NGOs working this case — never to the reporter or
        the public.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <strong style={{ fontSize: "0.9rem" }}>Collaborators</strong>
          {canManageCollaborators && !isAddingCollaborator && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ padding: "4px 10px", fontSize: "0.78rem" }}
              onClick={() => setIsAddingCollaborator(true)}
            >
              + Add
            </button>
          )}
        </div>

        {collaborators.length === 0 && !isAddingCollaborator && (
          <p className="field-hint">No other authorities added yet.</p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {collaborators.map((c) => (
            <div
              key={c.user_id}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.88rem" }}
            >
              <span>
                {c.org_name || c.full_name}
                {c.org_name && <span className="field-hint"> — {c.full_name}</span>}
              </span>
              {(canManageCollaborators || c.user_id === currentUserId) && (
                <button
                  type="button"
                  onClick={() => handleRemoveCollaborator(c.user_id)}
                  style={{ background: "none", border: "none", color: "var(--color-rust)", cursor: "pointer", fontSize: "0.78rem" }}
                >
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>

        {isAddingCollaborator && (
          <div style={{ marginTop: 10 }}>
            <input
              placeholder="Search station or NGO name…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
              {isSearching && <p className="spinner-text">Searching…</p>}
              {!isSearching &&
                results
                  .filter((r) => !collaborators.some((c) => c.user_id === r.id))
                  .map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => handleAddCollaborator(r.id)}
                      className="filter-chip"
                      style={{ textAlign: "left", justifyContent: "flex-start" }}
                    >
                      {r.org_name || r.full_name}
                    </button>
                  ))}
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ marginTop: 8, padding: "4px 10px", fontSize: "0.78rem" }}
              onClick={() => setIsAddingCollaborator(false)}
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      <div>
        <strong style={{ fontSize: "0.9rem" }}>Investigation log</strong>
        <form onSubmit={handleAddNote} style={{ marginTop: 8, marginBottom: 16 }}>
          <textarea
            rows={2}
            placeholder="Add a note — a lead followed up, a call made, a decision made…"
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
          />
          <button
            type="submit"
            className="btn btn-primary"
            style={{ marginTop: 8, padding: "6px 14px", fontSize: "0.85rem" }}
            disabled={isPosting || !noteBody.trim()}
          >
            {isPosting ? "Adding…" : "Add note"}
          </button>
        </form>

        {notes.length === 0 ? (
          <p className="field-hint">No notes yet.</p>
        ) : (
          <div className="sighting-list">
            {notes.map((n) => (
              <div key={n.id} className="sighting-item">
                <div className="sighting-item-header">
                  <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>{n.author_name}</span>
                  <span className="sighting-item-meta">{new Date(n.created_at).toLocaleString()}</span>
                </div>
                <div style={{ whiteSpace: "pre-wrap" }}>{n.body}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--color-mist)" }}>
        <strong style={{ fontSize: "0.9rem" }}>Age-progressed photo</strong>
        <p className="field-hint" style={{ marginTop: 4, marginBottom: 10 }}>
          For cases open long enough that appearance has likely changed. Shown alongside the
          original photo on the case page, never replacing it.
        </p>
        <form onSubmit={handleSaveAgeProgression}>
          <PhotoUpload value={ageProgressedUrl} onChange={setAgeProgressedUrl} />
          <div className="field" style={{ marginTop: 10, marginBottom: 10 }}>
            <label htmlFor="age-progression-note">Note (optional)</label>
            <input
              id="age-progression-note"
              placeholder="e.g. Progressed to an estimated age 15, produced by..."
              value={ageProgressionNoteInput}
              onChange={(e) => setAgeProgressionNoteInput(e.target.value)}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ padding: "6px 14px", fontSize: "0.85rem" }}
            disabled={isSavingAgeProgression || !ageProgressedUrl}
          >
            {isSavingAgeProgression ? "Saving…" : "Save age-progressed photo"}
          </button>
        </form>
      </div>

      {(caseStatus === "open" || caseStatus === "lead_found") && (
        <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--color-mist)" }}>
          <strong style={{ fontSize: "0.9rem" }}>Geofenced alert</strong>
          <p className="field-hint" style={{ marginTop: 4, marginBottom: 10 }}>
            Notify everyone who's opted in to alerts near this case's last-seen location — a
            community-scale, opt-in analog of an Amber Alert. Limited to once per case every 24
            hours.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            style={{ padding: "6px 14px", fontSize: "0.85rem" }}
            onClick={handleSendAlert}
            disabled={isSendingAlert}
          >
            {isSendingAlert ? "Sending…" : "Send geofenced alert"}
          </button>
          {alertResult && (
            <p className="field-hint" style={{ marginTop: 8 }}>
              Sent to {alertResult.notified_count} nearby subscriber
              {alertResult.notified_count === 1 ? "" : "s"}.
            </p>
          )}
        </div>
      )}

      {caseStatus === "resolved" && (
        <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--color-mist)" }}>
          <strong style={{ fontSize: "0.9rem" }}>Reopen this case</strong>
          <p className="field-hint" style={{ marginTop: 4, marginBottom: 10 }}>
            If the person has gone missing again, or this was resolved in error.
          </p>
          {!isReopening ? (
            <button
              type="button"
              className="btn btn-danger"
              style={{ padding: "6px 14px", fontSize: "0.85rem" }}
              onClick={() => setIsReopening(true)}
            >
              Reopen case
            </button>
          ) : (
            <form onSubmit={handleReopen}>
              <div className="field" style={{ marginBottom: 10 }}>
                <label htmlFor="reopen-reason">Reason (required)</label>
                <textarea
                  id="reopen-reason"
                  rows={2}
                  required
                  placeholder="e.g. Family reports they went missing again on..."
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
                />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="submit"
                  className="btn btn-danger"
                  style={{ padding: "6px 14px", fontSize: "0.85rem" }}
                  disabled={isSubmittingReopen || !reopenReason.trim()}
                >
                  {isSubmittingReopen ? "Reopening…" : "Confirm reopen"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: "6px 14px", fontSize: "0.85rem" }}
                  onClick={() => setIsReopening(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
