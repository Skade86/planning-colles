import React from 'react';

function DownloadButton() {
  const handleDownload = () => {
    window.open('http://localhost:8000/api/download_planning', '_blank');
  };

  return (
    <button onClick={handleDownload} style={{marginTop: '1em', marginLeft: '1em', background: '#4caf50'}}>
      Télécharger le planning (CSV)
    </button>
  );
}

export default DownloadButton;
