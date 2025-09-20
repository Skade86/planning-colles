import React from 'react';
import Button from 'react-bootstrap/Button';
import { useAuth } from '../AuthContext';

function GenerateButton({ setPlanning, setStatus }) {
  const { token } = useAuth();
  const handleGenerate = async () => {
    setStatus({ type: 'info', text: 'Génération du planning...' });
    try {
  const BASE_URL = process.env.REACT_APP_API_URL;
  const res = await fetch(`${BASE_URL}/api/generate_planning`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
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
      console.log(error.data);
    }
  };

  return (
    <Button variant="primary" onClick={handleGenerate} className="me-2 mt-2">
      Générer le planning
    </Button>
  );
}

export default GenerateButton;