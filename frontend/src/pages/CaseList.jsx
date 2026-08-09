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

  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const emptyAdvanced = { gender: "", age_min: "", age_max: "", last_seen_after: "", last_seen_before: "", region: "" };
  const [advancedInputs, setAdvancedInputs] = useState(emptyAdvanced);
  const [appliedAdvanced, setAppliedAdvanced] = useState(emptyAdvanced);

  const advancedFilterCount = Object.values(appliedAdvanced).filter(Boolean).length;

  // Ledger counts shown in the hero — real numbers from the same
  // endpoint the list uses, never placeholder figures.
  const [ledger, setLedger] = useState(null);

  useEffect(() => {
    // Real counts from the same endpoint the list uses (capped at the
    // API's max page size) — never placeholder figures. When a count
    // hits the cap we show it as "100+" rather than implying exactness.
    Promise.all([
      listCases({ status: "open", limit: 100 }),
      listCases({ status: "lead_found", limit: 100 }),
      listCases({ status: "resolved", limit: 100 }),
    ])
      .then(([open, lead, resolved]) => {
        const fmt = (n) => (n >= 100 ? "100+" : String(n));
        setLedger({
          open: fmt(open.data.length),
          lead: fmt(lead.data.length),
          resolved: fmt(resolved.data.length),
        });
      })
      .catch(() => setLedger(null));
  }, []);

  useEffect(() => {
    if (nearbyMode) return; // nearby search is triggered explicitly, not by the filter effect
    setIsLoading(true);
    setError(null);
    listCases({
      status: statusFilter || undefined,
      gender: appliedAdvanced.gender || undefined,
      age_min: appliedAdvanced.age_min || undefined,
      age_max: appliedAdvanced.age_max || undefined,
      last_seen_after: appliedAdvanced.last_seen_after ? new Date(appliedAdvanced.last_seen_after).toISOString() : undefined,
      last_seen_before: appliedAdvanced.last_seen_before ? new Date(appliedAdvanced.last_seen_before).toISOString() : undefined,
      region: appliedAdvanced.region || undefined,
    })
      .then(({ data }) => setCases(data))
      .catch((err) => setError(extractErrorMessage(err, "Couldn't load cases.")))
      .finally(() => setIsLoading(false));
  }, [statusFilter, nearbyMode, appliedAdvanced]);

  function handleApplyAdvancedFilters(e) {
    e.preventDefault();
    setAppliedAdvanced(advancedInputs);
  }

  function handleClearAdvancedFilters() {
    setAdvancedInputs(emptyAdvanced);
    setAppliedAdvanced(emptyAdvanced);
  }

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
      <div className="hero">
        <div className="hero-inner">
          <div className="hero-eyebrow">National Missing Persons Registry</div>
          <h2 className="hero-title">Every report can help bring someone home.</h2>
          <p className="hero-sub">
            Families, police, and NGOs use this registry together — filing cases, reporting
            sightings, and verifying leads in one place. If you recognize someone below, open
            their case to report what you saw.
          </p>
          <div className="hero-actions">
            {isAuthenticated ? (
              <Link to="/cases/new" className="btn btn-primary">
                File a new case
              </Link>
            ) : (
              <Link to="/register" className="btn btn-primary">
                Register to file a case
              </Link>
            )}
            <a href="#cases" className="btn btn-secondary">
              Browse cases
            </a>
          </div>
          {ledger && (
            <div className="hero-ledger">
              <div className="hero-ledger-item">
                <div className="hero-ledger-value">{ledger.open}</div>
                <div className="hero-ledger-label">Open cases</div>
              </div>
              <div className="hero-ledger-item">
                <div className="hero-ledger-value">{ledger.lead}</div>
                <div className="hero-ledger-label">Leads found</div>
              </div>
              <div className="hero-ledger-item">
                <div className="hero-ledger-value">{ledger.resolved}</div>
                <div className="hero-ledger-label">Resolved</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {!nearbyMode ? (
        <div className="filter-bar" id="cases">
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
          <button
            className={`filter-chip${advancedFilterCount > 0 ? " active" : ""}`}
            onClick={() => setShowMoreFilters((v) => !v)}
            type="button"
          >
            {showMoreFilters ? "Hide filters" : "More filters"}
            {advancedFilterCount > 0 ? ` (${advancedFilterCount})` : ""}
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

      {showMoreFilters && !nearbyMode && (
        <form onSubmit={handleApplyAdvancedFilters} className="dashboard-card" style={{ marginBottom: 24 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="filter-gender">Gender</label>
              <select
                id="filter-gender"
                value={advancedInputs.gender}
                onChange={(e) => setAdvancedInputs({ ...advancedInputs, gender: e.target.value })}
              >
                <option value="">Any</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="filter-age-min">Age (min)</label>
              <input
                id="filter-age-min"
                type="number"
                min="0"
                max="130"
                value={advancedInputs.age_min}
                onChange={(e) => setAdvancedInputs({ ...advancedInputs, age_min: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="filter-age-max">Age (max)</label>
              <input
                id="filter-age-max"
                type="number"
                min="0"
                max="130"
                value={advancedInputs.age_max}
                onChange={(e) => setAdvancedInputs({ ...advancedInputs, age_max: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="filter-region">Region</label>
              <input
                id="filter-region"
                placeholder="e.g. Belagavi"
                value={advancedInputs.region}
                onChange={(e) => setAdvancedInputs({ ...advancedInputs, region: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="filter-date-after">Last seen after</label>
              <input
                id="filter-date-after"
                type="date"
                value={advancedInputs.last_seen_after}
                onChange={(e) => setAdvancedInputs({ ...advancedInputs, last_seen_after: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="filter-date-before">Last seen before</label>
              <input
                id="filter-date-before"
                type="date"
                value={advancedInputs.last_seen_before}
                onChange={(e) => setAdvancedInputs({ ...advancedInputs, last_seen_before: e.target.value })}
              />
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button type="submit" className="btn btn-primary">
              Apply filters
            </button>
            <button type="button" className="btn btn-secondary" onClick={handleClearAdvancedFilters}>
              Clear
            </button>
          </div>
        </form>
      )}

      {isLoading && <p className="spinner-text">Loading cases…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      {!isLoading && !error && cases.length === 0 && (
        <div className="empty-state">
          <svg className="empty-state-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.6" />
            <path d="M20 20l-4.35-4.35" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
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
