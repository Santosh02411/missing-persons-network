import { useState } from "react";
import { resendVerification } from "../api/auth";
import { useAuth } from "../context/AuthContext";

export default function EmailVerificationBanner() {
  const { user } = useAuth();
  const [sent, setSent] = useState(false);
  const [isSending, setIsSending] = useState(false);

  if (!user || user.email_verified) return null;

  async function handleResend() {
    setIsSending(true);
    try {
      await resendVerification();
      setSent(true);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="container" style={{ marginTop: 16 }}>
      <div
        className="alert alert-error"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}
      >
        <span>
          {sent
            ? "Verification email sent — check your inbox (or the API server logs, in this dev setup)."
            : "Please verify your email address."}
        </span>
        {!sent && (
          <button className="btn btn-secondary" onClick={handleResend} disabled={isSending}>
            {isSending ? "Sending…" : "Resend verification email"}
          </button>
        )}
      </div>
    </div>
  );
}
