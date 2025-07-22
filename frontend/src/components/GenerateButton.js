import React from 'react';

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
      setStatus({ type: 'error', text: "Erreur lors de la génération. Vérifiez que le backend tourne et qu'un fichier a été uploadé." });
    }
  };

  return (
    <button onClick={handleGenerate} style={{marginTop: '1em'}}>
      Générer le planning
    </button>
  );
}

export default GenerateButton;
