const BASE_URL = import.meta.env.VITE_API_URL;
// src/components/DownloadButton.js
import React from 'react';
import Button from 'react-bootstrap/Button';
import { useAuth } from '../AuthContext';

function DownloadButton({ format = 'csv' }) {
  const { token } = useAuth();
  const handleDownload = async () => {
    try {
  const res = await fetch(`${BASE_URL}/api/download_planning?format=${format}`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Erreur serveur');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = format === 'excel' ? 'planning_optimise.xlsx' : 'planning_optimise.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert("Impossible de télécharger le planning.");
    }
  };

  return (
    <Button variant="success" onClick={handleDownload} className="me-2 mt-2">
      {format === 'excel' ? 'Télécharger (Excel)' : 'Télécharger le planning (CSV)'}
    </Button>
  );
}

export default DownloadButton;