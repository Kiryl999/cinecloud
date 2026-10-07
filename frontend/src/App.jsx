import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";

import AuthProvider from "./context/AuthProvider";
import ProtectedRoute from "./components/ProtectedRoute";
import LandingPage from "./pages/LandingPage";
import CinemaSelectionPage from "./pages/CinemaSelectionPage";
import CinemaPage from "./pages/CinemaPage";
import ShowtimePage from "./pages/ShowtimePage";
import AdminLoginPage from "./pages/AdminLoginPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* visitors start here; the sales page for cinema owners moved */}
          <Route path="/" element={<CinemaSelectionPage />} />
          <Route path="/for-cinemas" element={<LandingPage />} />
          <Route path="/cinemas" element={<Navigate to="/" replace />} />
          <Route path="/cinemas/:slug" element={<CinemaPage />} />
          <Route
            path="/cinemas/:slug/showtimes/:showtimeId"
            element={<ShowtimePage />}
          />

          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminDashboardPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
