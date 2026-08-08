import { useState } from "react";

/**
 * Drop-in replacement for a plain <input type="password">. Renders the
 * usual .field wrapper (label + hint), plus an eye button that toggles
 * between hidden and plain text so people can check what they've typed
 * before submitting.
 *
 * Props mirror a normal input: id, label, value, onChange, required,
 * minLength, autoComplete, placeholder. Anything else is spread onto the
 * <input> itself.
 */
export default function PasswordField({
  id,
  label,
  value,
  onChange,
  hint,
  required,
  minLength,
  autoComplete,
  placeholder,
  ...rest
}) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div className="field">
      {label && <label htmlFor={id}>{label}</label>}
      <div className="password-field">
        <input
          id={id}
          type={isVisible ? "text" : "password"}
          required={required}
          minLength={minLength}
          autoComplete={autoComplete}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          {...rest}
        />
        <button
          type="button"
          className="password-toggle"
          onClick={() => setIsVisible((v) => !v)}
          aria-label={isVisible ? "Hide password" : "Show password"}
          aria-pressed={isVisible}
          tabIndex={-1}
        >
          {isVisible ? (
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M3 3l18 18M10.6 10.6a2.5 2.5 0 003.5 3.5M9.4 5.5A10.4 10.4 0 0112 5c5 0 9 4 10 7a12.7 12.7 0 01-3.1 4.2M6.5 6.7C4.2 8.2 2.6 10.4 2 12c1 3 5 7 10 7 1.3 0 2.6-.3 3.8-.8"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" />
            </svg>
          )}
        </button>
      </div>
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}
