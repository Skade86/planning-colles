// src/components/DownloadButton.js
import React from 'react';
import Button from 'react-bootstrap/Button';

function DownloadButton({ format = 'csv' }) {
  const handleDownload = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/download_planning?format=${format}`, {
        method: 'GET',
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