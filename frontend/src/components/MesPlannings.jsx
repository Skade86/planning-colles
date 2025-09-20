import React, { useEffect, useState } from 'react';
import { useAuth } from '../AuthContext';

export default function MesPlannings() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
  const BASE_URL = process.env.REACT_APP_API_URL;
  const res = await fetch(`${BASE_URL}/api/plannings`, { headers: { 'Authorization': `Bearer ${token}` } });
      if (!res.ok) throw new Error('Erreur serveur');
      const data = await res.json();
      setItems(data.items || []);
    } catch (e) {
      setError(e.message || 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

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
                  <a className="btn btn-sm btn-outline-primary me-2" href={`${BASE_URL}/api/plannings/${it.id}/download?format=csv`} target="_blank" rel="noreferrer" onClick={(e)=>{e.stopPropagation();}}>CSV</a>
                  <a className="btn btn-sm btn-outline-success" href={`${BASE_URL}/api/plannings/${it.id}/download?format=excel`} target="_blank" rel="noreferrer" onClick={(e)=>{e.stopPropagation();}}>Excel</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}


