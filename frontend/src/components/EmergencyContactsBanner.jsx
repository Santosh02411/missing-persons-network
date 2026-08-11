import { useEffect, useState } from "react";
import { getEmergencyContacts } from "../api/emergency";

export default function EmergencyContactsBanner() {
  const [contacts, setContacts] = useState([]);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    getEmergencyContacts()
      .then(({ data }) => setContacts(data))
      .catch(() => setContacts([])); // never block the page over this
  }, []);

  if (contacts.length === 0) return null;

  const primary = contacts[0];
  const rest = contacts.slice(1);

  return (
    <div className="emergency-banner">
      <div className="emergency-banner-main">
        <div>
          <div className="emergency-banner-label">Missing person? Act now.</div>
          <div className="field-hint" style={{ color: "#f3d9b1", margin: 0 }}>
            The first 24–48 hours matter most. Don't wait to see if they turn up.
          </div>
        </div>
        <a href={`tel:${primary.number}`} className="btn emergency-call-btn">
          Call {primary.label} — {primary.number}
        </a>
      </div>

      {rest.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            className="emergency-banner-toggle"
          >
            {isExpanded ? "Hide other numbers" : `Other helplines (${rest.length})`}
          </button>
          {isExpanded && (
            <div className="emergency-banner-list">
              {rest.map((c) => (
                <a key={c.number} href={`tel:${c.number}`} className="emergency-banner-item">
                  <span className="emergency-banner-item-label">{c.label}</span>
                  <span className="emergency-banner-item-number">{c.number}</span>
                  <span className="emergency-banner-item-desc">{c.description}</span>
                </a>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
