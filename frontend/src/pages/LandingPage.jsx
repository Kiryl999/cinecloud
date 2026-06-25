import Hero from "../components/Hero";
import Features from "../components/Features";
import Pricing from "../components/Pricing";
import Contact from "../components/Contact";
import "../styles/LandingPage.css";

function LandingPage() {
  return (
    <div className="landing">
      <Hero />
      <Features />
      <Pricing />
      <Contact />
    </div>
  );
}

export default LandingPage;