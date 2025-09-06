import React from 'react';
import Button from 'react-bootstrap/Button';

function DownloadButton() {
  const handleDownload = () => {
    window.location.href = 'http://localhost:8000/api/download_planning';
  };

  return (
    <Button variant="success" onClick={handleDownload} className="me-2 mt-2">
      Télécharger le planning (CSV)
    </Button>
  );
}

export default DownloadButton;