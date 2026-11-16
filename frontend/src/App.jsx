import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";

import AuthProvider from "./context/AuthProvider";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminLayout from "./components/AdminLayout";
import CinemaSelectionPage from "./pages/CinemaSelectionPage";
import CinemaPage from "./pages/CinemaPage";
import ShowtimePage from "./pages/ShowtimePage";
import AdminLoginPage from "./pages/AdminLoginPage";
import AdminCallbackPage from "./pages/AdminCallbackPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import AdminSetupPage from "./pages/AdminSetupPage";
import AdminShowtimesPage from "./pages/AdminShowtimesPage";
import AdminShowtimePage from "./pages/AdminShowtimePage";
import AdminBookingsPage from "./pages/AdminBookingsPage";
import AdminMoviesPage from "./pages/AdminMoviesPage";
import AdminHallsPage from "./pages/AdminHallsPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<CinemaSelectionPage />} />
          {/* where the sales page used to be */}
          <Route path="/for-cinemas" element={<Navigate to="/admin" replace />} />
          <Route path="/cinemas" element={<Navigate to="/" replace />} />
          <Route path="/cinemas/:slug" element={<CinemaPage />} />
          <Route
            path="/cinemas/:slug/showtimes/:showtimeId"
            element={<ShowtimePage />}
          />

          <Route path="/admin/login" element={<AdminLoginPage />} />
          {/* registered as redirect URI of the cinecloud-web client */}
          <Route path="/admin/callback" element={<AdminCallbackPage />} />
          {/* a new account opens its cinema here */}
          <Route path="/admin/setup" element={<AdminSetupPage />} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AdminDashboardPage />} />
            <Route path="showtimes" element={<AdminShowtimesPage />} />
            <Route path="showtimes/:showtimeId" element={<AdminShowtimePage />} />
            <Route path="bookings" element={<AdminBookingsPage />} />
            <Route path="movies" element={<AdminMoviesPage />} />
            <Route path="halls" element={<AdminHallsPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
