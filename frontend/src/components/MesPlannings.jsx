
const BASE_URL = import.meta.env.VITE_API_URL;
import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../AuthContext';

export default function MesPlannings() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Téléchargement sécurisé avec token
  const handleDownload = async (id, format) => {
    try {
      const res = await fetch(`${BASE_URL}/api/plannings/${id}/download?format=${format}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Erreur lors du téléchargement');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `planning_${id}.${format === 'csv' ? 'csv' : 'xlsx'}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message || 'Erreur lors du téléchargement');
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${BASE_URL}/api/plannings`, { headers: { 'Authorization': `Bearer ${token}` } });
      if (!res.ok) throw new Error('Erreur serveur');
      const data = await res.json();
      setItems(data.items || []);
    } catch (e) {
      setError(e.message || 'Erreur');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: '1rem' }}>
      <h2>Mes plannings</h2>
      {loading && <p>Chargement…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {!loading && items.length === 0 && <p>Aucun planning enregistré.</p>}
      {items.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Créé le</th>
              <th>Auteur</th>
              <th>Télécharger</th>
            </tr>
          </thead>
          <tbody>
            {items.map(it => (
              <tr key={it.id}>
                <td>{it.name}</td>
                <td>{it.created_at}</td>
                <td>{it.user}</td>
                <td>
                  <button className="btn btn-sm btn-outline-primary me-2" onClick={() => handleDownload(it.id, 'csv')}>CSV</button>
                  <button className="btn btn-sm btn-outline-success" onClick={() => handleDownload(it.id, 'excel')}>Excel</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}


