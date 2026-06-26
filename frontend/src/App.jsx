import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import CinemaSelectionPage from "./pages/CinemaSelectionPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/cinemas" element={<CinemaSelectionPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;