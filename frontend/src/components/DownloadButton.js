import React from 'react';
import Button from 'react-bootstrap/Button';

function DownloadButton() {
  const handleDownload = () => {
    window.open('http://localhost:8000/api/download_planning', '_blank');
  };

  return (
    <Button onClick={handleDownload} style={{marginTop: '1em', marginLeft: '1em', background: '#4caf50'}}>
      Télécharger le planning (CSV)
    </Button>
  );
}

export default DownloadButton;
