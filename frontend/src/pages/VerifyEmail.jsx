import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../api/auth";
import { extractErrorMessage } from "../api/client";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [status, setStatus] = useState("checking"); // checking | success | error
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("This link is missing a verification token.");
      return;
    }
    verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setError(extractErrorMessage(err, "That verification link is invalid or has expired."));
      });
  }, [token]);

  return (
    <div className="container">
      <div className="form-card">
        <h2>Email verification</h2>
        {status === "checking" && <p className="spinner-text">Confirming your email…</p>}
        {status === "success" && (
          <div className="alert alert-success">Your email is confirmed. Thanks!</div>
        )}
        {status === "error" && <div className="alert alert-error">{error}</div>}
        <p className="field-hint" style={{ marginTop: 16, textAlign: "center" }}>
          <Link to="/">Back to case listings</Link>
        </p>
      </div>
    </div>
  );
}
