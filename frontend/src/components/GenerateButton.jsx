const BASE_URL = import.meta.env.VITE_API_URL;
import React from 'react';
import Button from 'react-bootstrap/Button';
import { useAuth } from '../AuthContext';

function GenerateButton({ setPlanning, setStatus, reglesAlternance }) {
  const { token } = useAuth();
  const handleGenerate = async () => {
    setStatus({ type: 'info', text: 'Génération du planning...' });
    console.log('[DEBUG] Règles d\'alternance envoyées:', reglesAlternance);
    try {
      const res = await fetch(`${BASE_URL}/api/generate_planning`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: reglesAlternance ? JSON.stringify({ reglesAlternance }) : undefined
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