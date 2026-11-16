import { Link } from "react-router-dom";

import Logo from "./Logo";

/** Header of the visitor pages. */
function SiteHeader() {
  return (
    <header className="site-header">
      <Link to="/" className="logo">
        <Logo />
      </Link>
      <nav aria-label="Site">
        <Link to="/">Cinemas</Link>
        <Link to="/admin">For cinema operators</Link>
      </nav>
    </header>
  );
}

export default SiteHeader;
