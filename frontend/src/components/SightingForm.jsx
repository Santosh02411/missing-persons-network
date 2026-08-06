import { useState } from "react";
import { submitSighting } from "../api/sightings";
import { extractErrorMessage } from "../api/client";
import LocationPicker from "./LocationPicker";
import PhotoUpload from "./PhotoUpload";

export default function SightingForm({ caseId, defaultCenter, onSubmitted }) {
  const [location, setLocation] = useState(null);
  const [addressText, setAddressText] = useState("");
  const [description, setDescription] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [justSubmitted, setJustSubmitted] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!location) {
      setError("Click the map to mark where you saw them.");
      return;
    }

    setIsSubmitting(true);
    try {
      await submitSighting({
        case_id: caseId,
        location,
        address_text: addressText,
        description,
        photo_url: photoUrl || null,
      });
      setJustSubmitted(true);
      setLocation(null);
      setAddressText("");
      setDescription("");
      setPhotoUrl("");
      onSubmitted?.();
    } catch (err) {
      if (err.response?.status === 429) {
        setError(
          "You've submitted several sighting reports recently — please wait a few minutes before trying again."
        );
      } else {
        setError(extractErrorMessage(err, "Couldn't submit that sighting."));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (justSubmitted) {
    return (
      <div className="alert alert-success">
        Thank you — your sighting has been submitted and will be reviewed by an authority.
        <div style={{ marginTop: 8 }}>
          <button className="btn btn-secondary" onClick={() => setJustSubmitted(false)}>
            Report another sighting
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="field">
        <label>Where did you see them?</label>
        <LocationPicker value={location} onChange={setLocation} defaultCenter={defaultCenter} />
      </div>

      <div className="field">
        <label htmlFor="address_text">Location description</label>
        <input
          id="address_text"
          required
          placeholder="e.g. near the bus stand, outside the pharmacy"
          value={addressText}
          onChange={(e) => setAddressText(e.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="description">What did you see?</label>
        <textarea
          id="description"
          required
          rows={4}
          placeholder="Describe what they were wearing, who they were with, when you saw them, etc."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Photo (optional)</label>
        <PhotoUpload value={photoUrl} onChange={setPhotoUrl} />
      </div>

      <button className="btn btn-primary" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting…" : "Submit sighting"}
      </button>
    </form>
  );
}
