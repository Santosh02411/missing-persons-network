import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useState } from "react";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";

// Leaflet's default marker icon references image URLs that don't resolve
// correctly under Vite's bundling -- swap in CDN-hosted versions instead of
// wrestling with asset imports for a single icon.
const markerIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

function ClickHandler({ onPick }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

/**
 * value: {lat, lng} | null
 * onChange: ({lat, lng}) => void
 * defaultCenter: {lat, lng} -- where the map opens before anything's picked
 */
export default function LocationPicker({ value, onChange, defaultCenter }) {
  const [center] = useState(value || defaultCenter || { lat: 20.5937, lng: 78.9629 }); // India centroid fallback

  return (
    <div>
      <div className="map-picker">
        <MapContainer
          center={[center.lat, center.lng]}
          zoom={value ? 13 : 5}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickHandler onPick={onChange} />
          {value && <Marker position={[value.lat, value.lng]} icon={markerIcon} />}
        </MapContainer>
      </div>
      <p className="field-hint">
        {value
          ? `Selected: ${value.lat.toFixed(5)}, ${value.lng.toFixed(5)}`
          : "Click the map to set a location."}
      </p>
    </div>
  );
}
