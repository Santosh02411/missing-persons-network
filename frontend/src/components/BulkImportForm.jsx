import { useState } from "react";
import { bulkImportCases } from "../api/cases";
import { extractErrorMessage } from "../api/client";

export default function BulkImportForm() {
  const [isOpen, setIsOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setError(null);
    setResult(null);
    setIsUploading(true);
    try {
      const { data } = await bulkImportCases(file);
      setResult(data);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't import that file."));
    } finally {
      setIsUploading(false);
      e.target.value = "";
    }
  }

  if (!isOpen) {
    return (
      <button type="button" className="btn btn-secondary" onClick={() => setIsOpen(true)}>
        Bulk import from CSV
      </button>
    );
  }

  return (
    <div className="dashboard-card" style={{ width: "100%" }}>
      <div className="section-heading" style={{ marginTop: 0 }}>
        <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Bulk import cases</h3>
      </div>
      <p className="field-hint">
        CSV columns required: <code>name</code>, <code>description</code>,{" "}
        <code>last_seen_address</code>, <code>last_seen_lat</code>, <code>last_seen_lng</code>,{" "}
        <code>last_seen_at</code>. Optional: <code>age_at_disappearance</code>, <code>gender</code>,{" "}
        <code>photo_url</code>. Imported cases go live immediately as Open, assigned to your
        account — up to 500 rows per file.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <input type="file" accept=".csv,text/csv" onChange={handleFileChange} disabled={isUploading} />
      {isUploading && <p className="spinner-text" style={{ marginTop: 8 }}>Importing…</p>}

      {result && (
        <div style={{ marginTop: 16 }}>
          <div className={`alert ${result.failed_count > 0 ? "alert-error" : "alert-success"}`}>
            Imported {result.created_count} case{result.created_count === 1 ? "" : "s"}.
            {result.failed_count > 0 && ` ${result.failed_count} row${result.failed_count === 1 ? "" : "s"} failed.`}
          </div>
          {result.errors.length > 0 && (
            <table className="data-table" style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Errors</th>
                </tr>
              </thead>
              <tbody>
                {result.errors.map((e) => (
                  <tr key={e.row}>
                    <td className="mono">{e.row}</td>
                    <td>{e.errors.join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <button
        type="button"
        className="btn btn-secondary"
        style={{ marginTop: 16 }}
        onClick={() => {
          setIsOpen(false);
          setResult(null);
          setError(null);
        }}
      >
        Close
      </button>
    </div>
  );
}
