import { useEffect, useState } from "react";
import { listCases } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import ReunitedCard from "../components/ReunitedCard";

export default function SuccessStories() {
  const [cases, setCases] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    listCases({ status: "resolved", limit: 100 })
      .then(({ data }) => setCases(data))
      .catch((err) => setError(extractErrorMessage(err, "Couldn't load reunited cases.")))
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="container">
      <div className="hero reunited-hero">
        <div className="hero-inner">
          <div className="hero-eyebrow">Reunification Network</div>
          <h2 className="hero-title">They came home.</h2>
          <p className="hero-sub">
            Every case here started as a search — a family, a station, an NGO, and often a
            stranger who recognized a face. These are the ones that ended the way everyone
            hopes they will.
          </p>
        </div>
      </div>

      {isLoading && <p className="spinner-text">Loading…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      {!isLoading && !error && cases.length === 0 && (
        <div className="empty-state">
          <h3>No resolved cases yet</h3>
          <p>Reunited cases will appear here as they're resolved.</p>
        </div>
      )}

      {!isLoading && cases.length > 0 && (
        <div className="case-grid">
          {cases.map((c) => (
            <ReunitedCard key={c.id} caseItem={c} />
          ))}
        </div>
      )}
    </div>
  );
}
