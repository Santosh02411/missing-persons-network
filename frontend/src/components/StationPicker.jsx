import { useEffect, useState } from "react";
import { nearbyAuthorities } from "../api/authorities";

/**
 * value: authority id string | null (null = "auto-route to nearest station")
 * onChange: (id | null) => void
 * location: {lat, lng} | null -- the case's last-seen location. Nothing is
 * fetched until this is set.
 */
export default function StationPicker({ value, onChange, location }) {
  const [stations, setStations] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!location) {
      setStations([]);
      return;
    }
    setIsLoading(true);
    nearbyAuthorities({ lat: location.lat, lng: location.lng, radius_km: 100 })
      .then(({ data }) => setStations(data))
      .catch(() => setStations([]))
      .finally(() => setIsLoading(false));
  }, [location?.lat, location?.lng]);

  if (!location) {
    return (
      <p className="field-hint">Mark the last-seen location on the map first.</p>
    );
  }

  if (isLoading) {
    return <p className="spinner-text">Finding nearby stations…</p>;
  }

  if (stations.length === 0) {
    return (
      <p className="field-hint">
        No verified station has registered a location near here yet. This case will be
        routed to the nearest available authority automatically once one does, and is
        visible to any verified authority in the meantime.
      </p>
    );
  }

  return (
    <select value={value || ""} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">Auto-route to nearest station</option>
      {stations.map((s) => (
        <option key={s.id} value={s.id}>
          {s.org_name || s.full_name}
          {s.distance_km != null ? ` — ${s.distance_km} km away` : ""}
        </option>
      ))}
    </select>
  );
}
