/** The wordmark: a screen above a row of seats, one of them picked. */
function Logo() {
  return (
    <>
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <path d="M5 11c7-3.6 15-3.6 22 0" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
        <rect x="6" y="17" width="5.5" height="5.5" rx="1.5" fill="currentColor" opacity="0.55" />
        <rect x="13.25" y="17" width="5.5" height="5.5" rx="1.5" fill="#ff2400" />
        <rect x="20.5" y="17" width="5.5" height="5.5" rx="1.5" fill="currentColor" opacity="0.55" />
      </svg>
      CineCloud
    </>
  );
}

export default Logo;
