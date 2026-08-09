import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { myCases, watchedCases } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import { mySightings } from "../api/sightings";
import StatusBadge from "../components/StatusBadge";

export default function CitizenDashboard() {
  const [cases, setCases] = useState([]);
  const [watching, setWatching] = useState([]);
  const [sightings, setSightings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    Promise.all([myCases(), mySightings(), watchedCases()])
      .then(([{ data: myCasesData }, { data: mySightingsData }, { data: watchedData }]) => {
        setCases(myCasesData);
        setSightings(mySightingsData);
        // Filed cases are auto-watched, so exclude them here -- this
        // section is for cases watched but not filed by this person.
        const filedIds = new Set(myCasesData.map((c) => c.id));
        setWatching(watchedData.filter((c) => !filedIds.has(c.id)));
      })
      .catch((err) => setError(extractErrorMessage(err, "Couldn't load your dashboard.")))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <div className="container"><p className="spinner-text">Loading…</p></div>;

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 style={{ marginBottom: 4 }}>My dashboard</h2>
          <p className="field-hint" style={{ margin: 0 }}>
            Cases you've filed and sightings you've reported.
          </p>
        </div>
        <Link to="/cases/new" className="btn btn-primary">
          File a new case
        </Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <section style={{ marginBottom: 40 }}>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>My cases ({cases.length})</h3>
        </div>
        {cases.length === 0 ? (
          <p className="field-hint">You haven't filed any cases yet.</p>
        ) : (
          <div className="sighting-list">
            {cases.map((c) => (
              <div key={c.id} className="sighting-item">
                <div className="sighting-item-header">
                  <div>
                    <StatusBadge status={c.status} /> <Link to={`/cases/${c.id}`}>{c.name}</Link>
                  </div>
                  <span className="sighting-item-meta">
                    {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="field-hint">{c.last_seen_address}</div>
                {c.status === "pending_review" && (
                  <p className="field-hint" style={{ marginTop: 4 }}>
                    Waiting for an authority to review and approve this case.
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="section-heading">
          <h3 style={{ margin: 0 }}>My sightings ({sightings.length})</h3>
        </div>
        {sightings.length === 0 ? (
          <p className="field-hint">You haven't reported any sightings yet.</p>
        ) : (
          <div className="sighting-list">
            {sightings.map((s) => (
              <div key={s.id} className="sighting-item">
                <div className="sighting-item-header">
                  <div>
                    <StatusBadge status={s.status} />{" "}
                    <Link to={`/cases/${s.case_id}`}>View case</Link>
                  </div>
                  <span className="sighting-item-meta">
                    {new Date(s.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div>{s.description}</div>
                <div className="field-hint">{s.address_text}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      {watching.length > 0 && (
        <section style={{ marginTop: 40 }}>
          <div className="section-heading">
            <h3 style={{ margin: 0 }}>Cases I'm watching ({watching.length})</h3>
          </div>
          <div className="sighting-list">
            {watching.map((c) => (
              <div key={c.id} className="sighting-item">
                <div className="sighting-item-header">
                  <div>
                    <StatusBadge status={c.status} /> <Link to={`/cases/${c.id}`}>{c.name}</Link>
                  </div>
                  <span className="sighting-item-meta">
                    {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="field-hint">{c.last_seen_address}</div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
