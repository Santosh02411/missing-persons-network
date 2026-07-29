import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCases, nearbyCases } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import CaseCard from "../components/CaseCard";
import { useAuth } from "../context/AuthContext";

const FILTERS = [
  { label: "All open", value: "open" },
  { label: "Lead found", value: "lead_found" },
  { label: "Resolved", value: "resolved" },
  { label: "Everything", value: null },
];

const NEARBY_RADIUS_KM = 25;

export default function CaseList() {
  const { isAuthenticated } = useAuth();
  const [statusFilter, setStatusFilter] = useState("open");
  const [cases, setCases] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [nearbyMode, setNearbyMode] = useState(false);
  const [isLocating, setIsLocating] = useState(false);

  useEffect(() => {
    if (nearbyMode) return; // nearby search is triggered explicitly, not by the filter effect
    setIsLoading(true);
    setError(null);
    listCases({ status: statusFilter || undefined })
      .then(({ data }) => setCases(data))
      .catch((err) => setError(extractErrorMessage(err, "Couldn't load cases.")))
      .finally(() => setIsLoading(false));
  }, [statusFilter, nearbyMode]);

  function handleSearchNearMe() {
    if (!navigator.geolocation) {
      setError("Your browser doesn't support location search.");
      return;
    }
    setError(null);
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setIsLocating(false);
        setIsLoading(true);
        nearbyCases({ lat: coords.latitude, lng: coords.longitude, radius_km: NEARBY_RADIUS_KM })
          .then(({ data }) => {
            setCases(data);
            setNearbyMode(true);
          })
          .catch((err) => setError(extractErrorMessage(err, "Couldn't search nearby cases.")))
          .finally(() => setIsLoading(false));
      },
      () => {
        setIsLocating(false);
        setError("Couldn't get your location — check your browser's location permission.");
      }
    );
  }

  function clearNearbyMode() {
    setNearbyMode(false);
  }

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

      {!nearbyMode ? (
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
          <button className="filter-chip" onClick={handleSearchNearMe} disabled={isLocating}>
            {isLocating ? "Getting your location…" : `📍 Cases near me (${NEARBY_RADIUS_KM}km)`}
          </button>
        </div>
      ) : (
        <div className="filter-bar">
          <span className="field-hint">
            Showing open cases within {NEARBY_RADIUS_KM}km of your location.
          </span>
          <button className="filter-chip active" onClick={clearNearbyMode}>
            ✕ Clear location search
          </button>
        </div>
      )}

      {isLoading && <p className="spinner-text">Loading cases…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      {!isLoading && !error && cases.length === 0 && (
        <div className="empty-state">
          <h3>No cases match {nearbyMode ? "this area" : "this filter"}</h3>
          <p>
            {nearbyMode
              ? "Try a wider search, or browse all cases instead."
              : "Try a different status, or check back later."}
          </p>
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
