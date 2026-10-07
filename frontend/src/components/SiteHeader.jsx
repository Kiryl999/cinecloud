import { Link } from "react-router-dom";

/** Header of the visitor pages. Cinema owners find their way to the sales page. */
function SiteHeader() {
  return (
    <header className="site-header">
      <Link to="/" className="site-header__logo">
        CineCloud
      </Link>
      <Link to="/for-cinemas" className="site-header__link">
        For cinemas
      </Link>
    </header>
  );
}

export default SiteHeader;
