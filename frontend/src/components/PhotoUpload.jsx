import { useState } from "react";
import { apiClient } from "../api/client";

/**
 * value: string (photo URL) | ""
 * onChange: (url: string) => void
 */
export default function PhotoUpload({ value, onChange }) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setError(null);
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post("/uploads/photo", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onChange(data.url);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Couldn't upload that photo.");
    } finally {
      setIsUploading(false);
      e.target.value = ""; // allow re-selecting the same file if they retry
    }
  }

  return (
    <div>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleFileChange}
        disabled={isUploading}
      />
      {isUploading && <p className="field-hint">Uploading…</p>}
      {error && (
        <p className="field-hint" style={{ color: "var(--color-rust)" }}>
          {error}
        </p>
      )}
      {value && !isUploading && (
        <div style={{ marginTop: 8 }}>
          <img
            src={value}
            alt="Uploaded preview"
            style={{ maxWidth: 160, maxHeight: 160, borderRadius: "var(--radius-sm)", display: "block" }}
          />
          <button
            type="button"
            className="btn btn-secondary"
            style={{ marginTop: 8, padding: "4px 10px", fontSize: "0.8rem" }}
            onClick={() => onChange("")}
          >
            Remove photo
          </button>
        </div>
      )}
    </div>
  );
}
