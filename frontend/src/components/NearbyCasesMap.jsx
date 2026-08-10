import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import L from "leaflet";
import { useNavigate } from "react-router-dom";
import { MapContainer, Marker, TileLayer } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";

const meIcon = L.divIcon({
  className: "",
  html: '<span style="display:block;width:16px;height:16px;border-radius:50%;background:#c8871f;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4);"></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const caseIcon = L.divIcon({
  className: "",
  html: '<span style="display:block;width:14px;height:14px;border-radius:50%;background:#3d5a80;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4);"></span>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

export default function NearbyCasesMap({ userLocation, cases }) {
  const navigate = useNavigate();
  const withCoords = cases.filter((c) => c.last_seen_location);

  return (
    <div
      style={{
        height: 320,
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
        border: "1px solid var(--color-mist)",
        marginBottom: 24,
      }}
    >
      <MapContainer
        center={[userLocation.lat, userLocation.lng]}
        zoom={11}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={[userLocation.lat, userLocation.lng]} icon={meIcon} />
        <MarkerClusterGroup chunkedLoading maxClusterRadius={50}>
          {withCoords.map((c) => (
            <Marker
              key={c.id}
              position={[c.last_seen_location.lat, c.last_seen_location.lng]}
              icon={caseIcon}
              eventHandlers={{ click: () => navigate(`/cases/${c.id}`) }}
            />
          ))}
        </MarkerClusterGroup>
      </MapContainer>
    </div>
  );
}
