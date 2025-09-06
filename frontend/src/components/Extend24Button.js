// src/components/Extend24Button.js
import React, { useState } from 'react';
import Button from 'react-bootstrap/Button';

export default function Extend24Button({ disabled = false, setStatus, format = 'csv' }) {
  const [loading, setLoading] = useState(false);

  const handleExtend = async () => {
    if (disabled || loading) return;
    setLoading(true);
    setStatus?.({ type: 'info', text: `Génération du planning 24 semaines (${format.toUpperCase()})...` });

    try {
      const res = await fetch(`http://localhost:8000/api/extend_planning?format=${format}`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Erreur serveur');

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = format === 'excel' ? 'planning_24_semaines.xlsx' : 'planning_24_semaines.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      setStatus?.({ type: 'success', text: 'Planning 24 semaines généré et téléchargé.' });
    } catch (e) {
      console.error(e);
      setStatus?.({
        type: 'error',
        text: "Impossible d'étendre à 24 semaines. Assurez‑vous qu'un planning 8 semaines est généré."
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      variant="success"
      onClick={handleExtend}
      disabled={disabled || loading}
      className="mt-2"
    >
      {loading ? 'Génération...' : `Étendre à 24 semaines (${format === 'excel' ? 'Excel' : 'CSV'})`}
    </Button>
  );
}