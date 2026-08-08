import { useEffect, useState } from "react";
import { searchAuthorities } from "../api/authorities";
import { shareCase } from "../api/cases";
import { extractErrorMessage } from "../api/client";

export default function ShareCaseForm({ caseId, onClose }) {
  const [mode, setMode] = useState("directory"); // "directory" | "email"
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (mode !== "directory") return;
    setIsSearching(true);
    const timeout = setTimeout(() => {
      searchAuthorities(query)
        .then(({ data }) => setResults(data))
        .catch(() => setResults([]))
        .finally(() => setIsSearching(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [query, mode]);

  async function handleSend(e) {
    e.preventDefault();
    setError(null);
    setIsSending(true);
    try {
      const payload = { message: message || null };
      if (mode === "directory") {
        if (!selectedId) {
          setError("Pick a station or NGO from the list.");
          setIsSending(false);
          return;
        }
        payload.to_authority_id = selectedId;
      } else {
        if (!email) {
          setError("Enter an email address.");
          setIsSending(false);
          return;
        }
        payload.to_email = email;
      }
      await shareCase(caseId, payload);
      setSent(true);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't share this case."));
    } finally {
      setIsSending(false);
    }
  }

  if (sent) {
    return (
      <div className="alert alert-success" style={{ marginTop: 16 }}>
        Case shared — the recipient will get an email with the full details, the case
        photo as a soft copy, and a link to open it on the website.{" "}
        <button
          type="button"
          onClick={onClose}
          style={{ background: "none", border: "none", color: "inherit", textDecoration: "underline", cursor: "pointer", padding: 0 }}
        >
          Close
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSend} className="dashboard-card" style={{ marginTop: 16, maxWidth: 480 }}>
      <div className="section-heading" style={{ marginTop: 0 }}>
        <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Share this case</h3>
      </div>

      <div className="filter-bar" style={{ marginBottom: 16 }}>
        <button
          type="button"
          className={`filter-chip${mode === "directory" ? " active" : ""}`}
          onClick={() => setMode("directory")}
        >
          Find a station
        </button>
        <button
          type="button"
          className={`filter-chip${mode === "email" ? " active" : ""}`}
          onClick={() => setMode("email")}
        >
          Enter an email
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {mode === "directory" ? (
        <div className="field">
          <label htmlFor="share-search">Search by station / NGO name</label>
          <input
            id="share-search"
            placeholder="e.g. Belagavi City Police"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedId(null);
            }}
          />
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
            {isSearching && <p className="spinner-text">Searching…</p>}
            {!isSearching &&
              results.map((r) => (
                <label
                  key={r.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 10px",
                    border: "1.5px solid var(--color-mist-dark)",
                    borderRadius: "var(--radius-sm)",
                    cursor: "pointer",
                    background: selectedId === r.id ? "var(--color-beacon-bg)" : "transparent",
                  }}
                >
                  <input
                    type="radio"
                    name="authority"
                    checked={selectedId === r.id}
                    onChange={() => setSelectedId(r.id)}
                  />
                  <span>
                    <strong>{r.org_name || r.full_name}</strong>
                    <span className="field-hint" style={{ display: "block" }}>
                      {r.email}
                    </span>
                  </span>
                </label>
              ))}
            {!isSearching && results.length === 0 && (
              <p className="field-hint">No matching verified authority found.</p>
            )}
          </div>
        </div>
      ) : (
        <div className="field">
          <label htmlFor="share-email">Recipient email</label>
          <input
            id="share-email"
            type="email"
            placeholder="station@example.gov.in"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <p className="field-hint">
            They don't need an existing account — the email includes a link to register
            and open this case directly.
          </p>
        </div>
      )}

      <div className="field">
        <label htmlFor="share-message">Message (optional)</label>
        <textarea
          id="share-message"
          rows={2}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-primary" type="submit" disabled={isSending}>
          {isSending ? "Sending…" : "Send by email"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  );
}
