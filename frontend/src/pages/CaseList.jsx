import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  Compass,
  FilePlus2,
  Lightbulb,
  ListFilter,
  Loader2,
  MapPin,
  Search as SearchIcon,
  Sparkles,
  X,
} from "lucide-react";
import { listCases, nearbyCases } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import CaseCard from "../components/CaseCard";
import { useAuth } from "../context/AuthContext";

const FILTERS = [
  { label: "Open", value: "open", icon: SearchIcon },
  { label: "Lead found", value: "lead_found", icon: Lightbulb },
  { label: "Resolved", value: "resolved", icon: CheckCircle2 },
  { label: "Everything", value: null, icon: ListFilter },
];

const NEARBY_RADIUS_KM = 25;
// Cap for the three hero-stat sample requests below. There's no dedicated
// stats/count endpoint on the backend, so these are real counts from the
// existing (cached) /cases endpoint, capped at 100 per status -- shown as
// "100+" rather than a made-up exact number past that point.
const STAT_SAMPLE_LIMIT = 100;

function formatCount(n, capped) {
  return capped ? `${n}+` : String(n);
}

function isToday(dateString) {
  const d = new Date(dateString);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

export default function CaseList() {
  const { isAuthenticated } = useAuth();
  const [statusFilter, setStatusFilter] = useState("open");
  const [cases, setCases] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");

  const [nearbyMode, setNearbyMode] = useState(false);
  const [isLocating, setIsLocating] = useState(false);

  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (nearbyMode) return; // nearby search is triggered explicitly, not by the filter effect
    setIsLoading(true);
    setError(null);
    listCases({ status: statusFilter || undefined })
      .then(({ data }) => setCases(data))
      .catch((err) => setError(extractErrorMessage(err, "Couldn't load cases.")))
      .finally(() => setIsLoading(false));
  }, [statusFilter, nearbyMode]);

  useEffect(() => {
    // Powers the hero stat strip with real data (see STAT_SAMPLE_LIMIT note
    // above). Runs once on mount, independent of the filter/search state.
    // Decorative only -- fails quietly so a hiccup here never blocks the
    // actual case list from rendering.
    Promise.all([
      listCases({ status: "open", limit: STAT_SAMPLE_LIMIT }),
      listCases({ status: "lead_found", limit: STAT_SAMPLE_LIMIT }),
      listCases({ status: "resolved", limit: STAT_SAMPLE_LIMIT }),
    ])
      .then(([openRes, leadRes, resolvedRes]) => {
        const all = [...openRes.data, ...leadRes.data, ...resolvedRes.data];
        setStats({
          open: openRes.data.length,
          openCapped: openRes.data.length === STAT_SAMPLE_LIMIT,
          leadFound: leadRes.data.length,
          leadFoundCapped: leadRes.data.length === STAT_SAMPLE_LIMIT,
          resolved: resolvedRes.data.length,
          resolvedCapped: resolvedRes.data.length === STAT_SAMPLE_LIMIT,
          newToday: all.filter((c) => isToday(c.created_at)).length,
        });
      })
      .catch(() => setStats(null));
  }, []);

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
    setQuery("");
  }

  // Client-side only -- there's no text-search endpoint on the backend, so
  // this filters whatever page of results is already loaded. Age isn't
  // searchable here because the list endpoint doesn't return it (only the
  // full case-detail endpoint does).
  const visibleCases = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return cases;
    return cases.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.last_seen_address.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q)
    );
  }, [cases, query]);

  return (
    <>
      <section className="hero">
        <div className="hero-pattern" aria-hidden="true" />
        <div className="container hero-inner">
          <div className="hero-copy">
            <span className="hero-eyebrow">
              <Sparkles size={13} aria-hidden="true" /> National Missing Persons Registry
            </span>
            <h1 className="hero-title">Helping families reunite</h1>
            <p className="hero-subtitle">
              Every report can help bring someone home. Browse open cases below, or file a
              new one in minutes.
            </p>
            <div className="hero-actions">
              {isAuthenticated && (
                <Link to="/cases/new" className="btn btn-primary btn-lg">
                  <FilePlus2 size={17} aria-hidden="true" /> File a new case
                </Link>
              )}
              <a href="#case-results" className="btn btn-secondary btn-lg btn-on-dark">
                <Compass size={17} aria-hidden="true" /> Browse cases
              </a>
            </div>
          </div>

          <div className="hero-stats">
            <div className="stat-card">
              <span className="stat-value">
                {stats
                  ? formatCount(stats.open + stats.leadFound, stats.openCapped || stats.leadFoundCapped)
                  : "—"}
              </span>
              <span className="stat-label">Active cases</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">
                {stats ? formatCount(stats.resolved, stats.resolvedCapped) : "—"}
              </span>
              <span className="stat-label">Resolved</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">{stats ? stats.newToday : "—"}</span>
              <span className="stat-label">New today</span>
            </div>
          </div>
        </div>
      </section>

      <div className="container" id="case-results">
        <div className="page-header">
          <div>
            <h2 style={{ marginBottom: 4 }}>Browse cases</h2>
            <p className="field-hint" style={{ margin: 0 }}>
              If you recognize someone, open the case to report what you saw.
            </p>
          </div>
        </div>

        <div className="search-bar">
          <SearchIcon size={18} className="search-icon" aria-hidden="true" />
          <input
            type="search"
            className="search-input"
            placeholder="Search by name, location, or case ID"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search cases"
          />
          {query && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={() => setQuery("")}
              aria-label="Clear search"
            >
              <X size={15} aria-hidden="true" />
            </button>
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
                <f.icon size={14} aria-hidden="true" />
                {f.label}
              </button>
            ))}
            <button className="filter-chip" onClick={handleSearchNearMe} disabled={isLocating}>
              {isLocating ? (
                <Loader2 size={14} className="spin" aria-hidden="true" />
              ) : (
                <MapPin size={14} aria-hidden="true" />
              )}
              {isLocating ? "Getting your location…" : `Near me (${NEARBY_RADIUS_KM}km)`}
            </button>
          </div>
        ) : (
          <div className="filter-bar">
            <span className="field-hint">
              Showing open cases within {NEARBY_RADIUS_KM}km of your location.
            </span>
            <button className="filter-chip active" onClick={clearNearbyMode}>
              <X size={14} aria-hidden="true" /> Clear location search
            </button>
          </div>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        {isLoading && (
          <div className="case-grid">
            {Array.from({ length: 6 }).map((_, i) => (
              <div className="skeleton-card" key={i}>
                <div className="skeleton skeleton-photo" />
                <div className="skeleton skeleton-line" style={{ width: "70%" }} />
                <div className="skeleton skeleton-line" style={{ width: "45%" }} />
              </div>
            ))}
          </div>
        )}

        {!isLoading && !error && visibleCases.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon" aria-hidden="true">
              <SearchIcon size={26} />
            </div>
            <h3>
              {query ? "No cases match your search" : `No cases match ${nearbyMode ? "this area" : "this filter"}`}
            </h3>
            <p>
              {query
                ? "Try a different name, location, or case ID."
                : nearbyMode
                  ? "Try a wider search, or browse all cases instead."
                  : "Try a different status, or check back later."}
            </p>
          </div>
        )}

        {!isLoading && visibleCases.length > 0 && (
          <div className="case-grid">
            {visibleCases.map((c) => (
              <CaseCard key={c.id} caseItem={c} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
