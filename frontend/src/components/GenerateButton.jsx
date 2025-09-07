import React from 'react';
import Button from 'react-bootstrap/Button';

function GenerateButton({ setPlanning, setStatus }) {
  const handleGenerate = async () => {
    setStatus({ type: 'info', text: 'Génération du planning...' });
    try {
      const res = await fetch('http://localhost:8000/api/generate_planning', {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Erreur réseau');
      const data = await res.json();
      setPlanning(data);
      setStatus({ type: 'success', text: 'Planning généré avec succès !' });
    } catch (error) {
      setStatus({
        type: 'error',
        text: "Erreur lors de la génération. Vérifiez que le backend tourne et qu'un fichier a été uploadé."
      });
    }
  };

  return (
    <Button variant="primary" onClick={handleGenerate} className="me-2 mt-2">
      Générer le planning
    </Button>
  );
}

export default GenerateButton;