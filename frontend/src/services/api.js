const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const cinemaService = {
  // all cinemas from backend
  getAll: async () => {
    const response = await fetch(`${API_BASE_URL}/cinemas/`);
    if (!response.ok) {
      throw new Error('Failed to fetch cinemas from server');
    }
    return response.json();
  },

};