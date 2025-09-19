import React, { useEffect, useState } from 'react';
import { useAuth } from '../AuthContext';

export default function MonProfil() {
  const { token, user } = useAuth();
  const [profil, setProfil] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('http://localhost:8000/api/users/me', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Erreur serveur');
      const data = await res.json();
      setProfil({
        email: data.email || '',
        nom: data.nom || '',
        classes: (data.classes || []).join(', '),
        matieres: (data.matieres || []).join(', '),
        paires: data.disponibilites?.paires ?? true,
        impaires: data.disponibilites?.impaires ?? true,
      });
    } catch (e) {
      setError(e.message || 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const payload = {
        email: profil.email,
        nom: profil.nom,
        classes: profil.classes.split(',').map(s => s.trim()).filter(Boolean),
        matieres: profil.matieres.split(',').map(s => s.trim()).filter(Boolean),
        disponibilites: { paires: !!profil.paires, impaires: !!profil.impaires }
      };
      const res = await fetch('http://localhost:8000/api/users/me', {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Sauvegarde impossible');
      await load();
      alert('Profil mis à jour');
    } catch (e) {
      setError(e.message || 'Erreur');
    } finally {
      setSaving(false);
    }
  };

  if (!user) return <p>Connectez-vous</p>;
  if (loading) return <p>Chargement…</p>;
  if (error) return <p style={{ color: 'red' }}>{error}</p>;

  return (
    <div style={{ maxWidth: 560 }}>
      <h2>Mon profil</h2>
      <div className="mb-3">
        <label className="form-label">Nom</label>
        <input className="form-control" value={profil.nom} onChange={e => setProfil({ ...profil, nom: e.target.value })} />
      </div>
      <div className="mb-3">
        <label className="form-label">Email</label>
        <input type="email" className="form-control" value={profil.email} onChange={e => setProfil({ ...profil, email: e.target.value })} />
      </div>
      <div className="mb-3">
        <label className="form-label">Classes (séparées par des virgules)</label>
        <input className="form-control" value={profil.classes} onChange={e => setProfil({ ...profil, classes: e.target.value })} />
      </div>
      <div className="mb-3">
        <label className="form-label">Matières (séparées par des virgules)</label>
        <input className="form-control" value={profil.matieres} onChange={e => setProfil({ ...profil, matieres: e.target.value })} />
      </div>
      <div className="form-check mb-3">
        <input id="paires" className="form-check-input" type="checkbox" checked={!!profil.paires} onChange={e => setProfil({ ...profil, paires: e.target.checked })} />
        <label className="form-check-label" htmlFor="paires">Travaille les semaines paires</label>
      </div>
      <div className="form-check mb-3">
        <input id="impaires" className="form-check-input" type="checkbox" checked={!!profil.impaires} onChange={e => setProfil({ ...profil, impaires: e.target.checked })} />
        <label className="form-check-label" htmlFor="impaires">Travaille les semaines impaires</label>
      </div>
      <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</button>
    </div>
  );
}


