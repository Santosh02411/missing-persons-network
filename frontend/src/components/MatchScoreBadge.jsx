/**
 * score: number 0..1 | null | undefined
 *
 * A face-similarity score between a sighting's photo and the case's photo,
 * computed at submission time (see backend face_match_service). Null means
 * no score is available (missing photo on either side, or no face
 * detected) -- that's shown as a neutral note, not as "0% match", since
 * it's a different, weaker signal than "compared and scored low".
 */
export default function MatchScoreBadge({ score }) {
  if (score == null) return null;

  const pct = Math.round(score * 100);
  let tier = "low";
  if (score >= 0.75) tier = "high";
  else if (score >= 0.5) tier = "medium";

  return (
    <span className={`match-score-badge match-score-${tier}`} title="Face-similarity score against the case photo — a helpful signal, not a confirmed identification.">
      <span className="beacon-pulse" aria-hidden="true" style={{ display: tier === "high" ? "inline-block" : "none" }} />
      {pct}% photo match
    </span>
  );
}
