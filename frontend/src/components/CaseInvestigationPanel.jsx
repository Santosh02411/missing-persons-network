import { useEffect, useState } from "react";
import { searchAuthorities } from "../api/authorities";
import {
  addCaseCollaborator,
  addCaseNote,
  getCaseCollaborators,
  getCaseNotes,
  removeCaseCollaborator,
} from "../api/cases";
import { extractErrorMessage } from "../api/client";

/**
 * canManageCollaborators: whether the current user is the case's assigned
 * authority or an admin -- controls whether the "add collaborator" picker
 * is shown. Everyone with case access can view the list, add notes, and
 * remove themselves as a collaborator.
 */
export default function CaseInvestigationPanel({ caseId, currentUserId, canManageCollaborators }) {
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
    </div>
  );
}
