import React from 'react';
import Button from 'react-bootstrap/Button';
import { useAuth } from '../AuthContext';

export default function SavePlanningButton({ defaultName = '' , onSaved }) {
  const { token } = useAuth();

  const handleSave = async () => {
    const name = window.prompt('Nom du planning à enregistrer :', defaultName || '');
    try {
      const url = name ? `http://localhost:8000/api/plannings/save?name=${encodeURIComponent(name)}` : `http://localhost:8000/api/plannings/save`;
      const res = await fetch(url, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
      if (!res.ok) throw new Error('Erreur serveur');
      const data = await res.json();
      if (onSaved) onSaved(data);
      alert('Planning enregistré.');
    } catch (e) {
      console.error(e);
      alert("Impossible d'enregistrer le planning.");
    }
  };

  return (
    <Button variant="outline-secondary" onClick={handleSave} className="me-2 mt-2">
      Enregistrer le planning
    </Button>
  );
}


