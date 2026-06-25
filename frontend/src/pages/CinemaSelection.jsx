import React from 'react';
import { Link } from 'react-router-dom';

export default function CinemaSelection() {
  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <Link to="/">← Back to Home</Link>
      <h2>Select Your Cinema</h2>
      <p>Cinemas from the backend database will be listed here soon...</p>
    </div>
  );
}