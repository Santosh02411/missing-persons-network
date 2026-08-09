import "leaflet/dist/leaflet.css";
import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";
import { getAnalyticsHeatmap, getAnalyticsOverview, getAnalyticsVolume } from "../api/analytics";
import { extractErrorMessage } from "../api/client";

const STATUS_COLORS = {
  open: "#3d5a80",
  lead_found: "#a8790f",
  resolved: "#3f6b52",
  pending_review: "#5b6472",
  dismissed: "#a44a3f",
};

const STATUS_LABELS = {
  open: "Open",
  lead_found: "Lead found",
  resolved: "Resolved",
  pending_review: "Pending review",
  dismissed: "Dismissed",
};

function StatCard({ label, value, hint }) {
  return (
    <div className="dashboard-card" style={{ marginBottom: 0, padding: "16px 20px" }}>
      <div className="hero-ledger-label" style={{ marginBottom: 4 }}>
        {label.toUpperCase()}
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "1.7rem", fontWeight: 600, color: "var(--color-ink)" }}>
        {value}
      </div>
      {hint && <div className="field-hint" style={{ marginTop: 2 }}>{hint}</div>}
    </div>
  );
}

function StatusBreakdownBars({ breakdown, total }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Object.entries(breakdown).map(([key, count]) => (
        <div key={key}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: 3 }}>
            <span>{STATUS_LABELS[key] || key}</span>
            <span className="field-hint">{count}</span>
          </div>
          <div style={{ background: "var(--color-mist)", borderRadius: 4, height: 8, overflow: "hidden" }}>
            <div
              style={{
                width: total > 0 ? `${(count / total) * 100}%` : "0%",
                background: STATUS_COLORS[key] || "var(--color-slate)",
                height: "100%",
                borderRadius: 4,
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function VolumeChart({ points }) {
  const max = Math.max(1, ...points.map((p) => p.count));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 140 }}>
      {points.map((p) => (
        <div key={p.period_start} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
          <div
            title={`${p.count} case${p.count === 1 ? "" : "s"} filed the week of ${p.period_start}`}
            style={{
              width: "100%",
              height: `${Math.max(3, (p.count / max) * 110)}px`,
              background: "var(--color-beacon)",
              borderRadius: "3px 3px 0 0",
            }}
          />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.62rem", color: "var(--color-graytext)", whiteSpace: "nowrap" }}>
            {new Date(p.period_start).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function AdminAnalytics() {
  const [overview, setOverview] = useState(null);
  const [volume, setVolume] = useState([]);
  const [heatmap, setHeatmap] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    Promise.all([getAnalyticsOverview(), getAnalyticsVolume(12), getAnalyticsHeatmap()])
      .then(([{ data: overviewData }, { data: volumeData }, { data: heatmapData }]) => {
        setOverview(overviewData);
        setVolume(volumeData);
        setHeatmap(heatmapData);
      })
      .catch((err) => setError(extractErrorMessage(err, "Couldn't load analytics.")))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <div className="container"><p className="spinner-text">Loading…</p></div>;
  if (error) return <div className="container"><div className="alert alert-error">{error}</div></div>;
  if (!overview) return null;

  const mapCenter = heatmap.length > 0
    ? [heatmap[0].lat, heatmap[0].lng]
    : [20.5937, 78.9629]; // India centroid fallback

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 style={{ marginBottom: 4 }}>Analytics</h2>
          <p className="field-hint" style={{ margin: 0 }}>
            Registry-wide case volume, resolution times, and regional distribution.
          </p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 32 }}>
        <StatCard label="Total cases" value={overview.total_cases} />
        <StatCard
          label="Resolved"
          value={overview.status_breakdown.resolved}
          hint={overview.total_cases > 0 ? `${Math.round((overview.status_breakdown.resolved / overview.total_cases) * 100)}% of all cases` : null}
        />
        <StatCard
          label="Avg. days to resolve"
          value={overview.resolution_time.avg_days_to_resolve ?? "—"}
          hint={overview.resolution_time.resolved_case_count > 0 ? `across ${overview.resolution_time.resolved_case_count} resolved case${overview.resolution_time.resolved_case_count === 1 ? "" : "s"}` : "no resolved cases yet"}
        />
        <StatCard
          label="Median days to resolve"
          value={overview.resolution_time.median_days_to_resolve ?? "—"}
        />
        <StatCard
          label="Sightings reported"
          value={overview.sightings.total}
          hint={`${overview.sightings.verified} verified`}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 24, marginBottom: 24 }}>
        <div className="dashboard-card">
          <div className="section-heading" style={{ marginTop: 0 }}>
            <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Cases filed per week</h3>
          </div>
          {volume.length === 0 ? (
            <p className="field-hint">No cases filed yet.</p>
          ) : (
            <VolumeChart points={volume} />
          )}
        </div>

        <div className="dashboard-card">
          <div className="section-heading" style={{ marginTop: 0 }}>
            <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Status breakdown</h3>
          </div>
          <StatusBreakdownBars breakdown={overview.status_breakdown} total={overview.total_cases} />
        </div>
      </div>

      <div className="dashboard-card">
        <div className="section-heading" style={{ marginTop: 0 }}>
          <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Regional distribution</h3>
        </div>
        {heatmap.length === 0 ? (
          <p className="field-hint">No cases with a location yet.</p>
        ) : (
          <>
            <div style={{ height: 420, borderRadius: "var(--radius-md)", overflow: "hidden", border: "1px solid var(--color-mist)" }}>
              <MapContainer center={mapCenter} zoom={5} style={{ height: "100%", width: "100%" }}>
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {heatmap.map((p, i) => (
                  <CircleMarker
                    key={i}
                    center={[p.lat, p.lng]}
                    radius={7}
                    pathOptions={{
                      color: STATUS_COLORS[p.status] || "var(--color-slate)",
                      fillColor: STATUS_COLORS[p.status] || "var(--color-slate)",
                      fillOpacity: 0.35,
                      weight: 1,
                    }}
                  />
                ))}
              </MapContainer>
            </div>
            <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
              {Object.entries(STATUS_LABELS).map(([key, label]) => (
                <div key={key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.78rem", color: "var(--color-graytext)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: "50%", background: STATUS_COLORS[key], display: "inline-block" }} />
                  {label}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
