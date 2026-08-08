import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createCase } from "../api/cases";
import { extractErrorMessage } from "../api/client";
import LocationPicker from "../components/LocationPicker";
import PhotoUpload from "../components/PhotoUpload";
import StationPicker from "../components/StationPicker";

export default function CaseCreate() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    age_at_disappearance: "",
    photo_url: "",
    description: "",
    last_seen_address: "",
    last_seen_at: "",
  });
  const [location, setLocation] = useState(null);
  const [targetAuthorityId, setTargetAuthorityId] = useState(null);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!location) {
      setError("Click the map to mark the last-seen location.");
      return;
    }

    setIsSubmitting(true);
    try {
      const { data } = await createCase({
        name: form.name,
        age_at_disappearance: form.age_at_disappearance
          ? Number(form.age_at_disappearance)
          : null,
        photo_url: form.photo_url || null,
        description: form.description,
        last_seen_location: location,
        last_seen_address: form.last_seen_address,
        last_seen_at: new Date(form.last_seen_at).toISOString(),
        target_authority_id: targetAuthorityId,
      });
      navigate(`/cases/${data.id}`);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't create this case."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="container">
      <div className="form-card" style={{ maxWidth: 620 }}>
        <h2>File a missing person case</h2>
        <p className="field-hint" style={{ marginTop: -8, marginBottom: 20 }}>
          Provide as much detail as you can — it helps authorities and the public recognize
          them.
        </p>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="name">Full name</label>
            <input id="name" required value={form.name} onChange={(e) => updateField("name", e.target.value)} />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="age">Age at disappearance</label>
              <input
                id="age"
                type="number"
                min={0}
                max={130}
                value={form.age_at_disappearance}
                onChange={(e) => updateField("age_at_disappearance", e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="last_seen_at">Last seen on</label>
              <input
                id="last_seen_at"
                type="datetime-local"
                required
                value={form.last_seen_at}
                onChange={(e) => updateField("last_seen_at", e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <label>Photo</label>
            <PhotoUpload value={form.photo_url} onChange={(url) => updateField("photo_url", url)} />
            <p className="field-hint">JPEG, PNG, or WEBP, up to 5MB.</p>
          </div>

          <div className="field">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              required
              rows={4}
              placeholder="Physical description, what they were wearing, distinguishing marks, etc."
              value={form.description}
              onChange={(e) => updateField("description", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="last_seen_address">Last-seen address</label>
            <input
              id="last_seen_address"
              required
              placeholder="e.g. Central Market, Belagavi"
              value={form.last_seen_address}
              onChange={(e) => updateField("last_seen_address", e.target.value)}
            />
          </div>

          <div className="field">
            <label>Last-seen location on the map</label>
            <LocationPicker value={location} onChange={setLocation} />
          </div>

          <div className="field">
            <label htmlFor="station">File with this station</label>
            <StationPicker value={targetAuthorityId} onChange={setTargetAuthorityId} location={location} />
            <p className="field-hint">
              This case is only sent to the station you pick (or the nearest verified
              station, if you leave it on auto-route) — not broadcast to every police
              station and NGO nationwide.
            </p>
          </div>

          <button className="btn btn-primary btn-block" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Filing case…" : "File case"}
          </button>
        </form>
      </div>
    </div>
  );
}
