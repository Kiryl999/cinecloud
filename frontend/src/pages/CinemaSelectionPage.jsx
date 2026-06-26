import { useEffect, useState } from "react";
import { cinemaService } from "../services/api";

function CinemaSelectionPage() {
  const [cinemas, setCinemas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
      cinemaService.getAll()
        .then((data) => setCinemas(data))
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ padding: "2rem" }}>Loading cinemas...</p>;
  if (error) return <p style={{ padding: "2rem" }}>Error: {error}</p>;

  return (
    <div style={{ padding: "2rem" }}>
      <h1>Choose a cinema</h1>
      <ul>
        {cinemas.map((cinema) => (
          <li key={cinema.id}>{cinema.name}</li>
        ))}
      </ul>
    </div>
  );
}

export default CinemaSelectionPage;