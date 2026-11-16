import { Link } from "react-router-dom";

export const SOURCE_URL = "https://github.com/Kiryl999/cinecloud";

/** Footer of the visitor pages: what this is, and where its code lives. */
function SiteFooter() {
  return (
    <footer className="site-footer">
      <p>
        CineCloud is a demo: bookings work, payment is simulated. The{" "}
        <a href={SOURCE_URL}>source code is on GitHub</a>. Running a cinema?{" "}
        <Link to="/admin">Open your own</Link>.
      </p>
    </footer>
  );
}

export default SiteFooter;
