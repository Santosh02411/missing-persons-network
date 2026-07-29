import { useEffect, useState } from "react";
import { listCases } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import CaseCard from "../components/CaseCard";
import { useAuth } from "../context/AuthContext";
import { Link } from "react-router-dom";

const FILTERS = [
  { label: "All open", value: "open" },
  { label: "Lead found", value: "lead_found" },
  { label: "Resolved", value: "resolved" },
  { label: "Everything", value: null },
];

export default function CaseList() {
  const { isAuthenticated } = useAuth();
  const [statusFilter, setStatusFilter] = useState("open");
  const [cases, setCases] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    listCases({ status: statusFilter || undefined })
      .then(({ data }) => setCases(data))
      .catch((err) => setError(extractErrorMessage(err, "Couldn't load cases.")))
      .finally(() => setIsLoading(false));
  }, [statusFilter]);

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 style={{ marginBottom: 4 }}>Missing person cases</h2>
          <p className="field-hint" style={{ margin: 0 }}>
            Browse registered cases. If you recognize someone, open the case to report what
            you saw.
          </p>
        </div>
        {isAuthenticated && (
          <Link to="/cases/new" className="btn btn-primary">
            File a new case
          </Link>
        )}
      </div>

      <div className="filter-bar">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            className={`filter-chip ${statusFilter === f.value ? "active" : ""}`}
            onClick={() => setStatusFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="spinner-text">Loading cases…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      {!isLoading && !error && cases.length === 0 && (
        <div className="empty-state">
          <h3>No cases match this filter</h3>
          <p>Try a different status, or check back later.</p>
        </div>
      )}

      {!isLoading && cases.length > 0 && (
        <div className="case-grid">
          {cases.map((c) => (
            <CaseCard key={c.id} caseItem={c} />
          ))}
        </div>
      )}
    </div>
  );
}
