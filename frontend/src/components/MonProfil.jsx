const BASE_URL = import.meta.env.VITE_API_URL;
import React, { useEffect, useState } from 'react';
import { useAuth } from '../AuthContext';

export default function MonProfil() {
  const { token, user } = useAuth();
  const [profil, setProfil] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState("");
  const handlePasswordChange = async () => {
    setPasswordMsg("");
    if (!newPassword.trim()) {
      setPasswordMsg("Veuillez saisir un nouveau mot de passe.");
      return;
    }
    try {
      const res = await fetch(`${BASE_URL}/api/users/me/password`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: newPassword })
      });
      if (!res.ok) throw new Error('Changement impossible');
      setPasswordMsg('Mot de passe modifié !');
      setNewPassword("");
    } catch (e) {
      setPasswordMsg(e.message || 'Erreur');
    }
  };

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${BASE_URL}/api/users/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Erreur serveur');
      const data = await res.json();
      setProfil({
        email: data.email || '',
        nom: data.nom || '',
        classes: (data.classes || []).join(', '),
        lycee: data.lycee || '',
      });
    } catch (e) {
      setError(e.message || 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const payload = {
        email: profil.email,
        nom: profil.nom,
        classes: profil.classes.split(',').map(s => s.trim()).filter(Boolean),
        lycee: profil.lycee,
      };
      const res = await fetch(`${BASE_URL}/api/users/me`, {
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
        <label className="form-label">Lycée</label>
        <input className="form-control" value={profil.lycee} onChange={e => setProfil({ ...profil, lycee: e.target.value })} />
      </div>
      <div className="mb-3">
        <label className="form-label">Classes (séparées par des virgules)</label>
        <input className="form-control" value={profil.classes} onChange={e => setProfil({ ...profil, classes: e.target.value })} />
      </div>
      {/* Champs matières et disponibilités supprimés car non présents dans le schéma backend */}
      <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</button>

      <hr />
      <h5>Changer le mot de passe</h5>
      <div className="mb-3">
        <input type="password" className="form-control" placeholder="Nouveau mot de passe" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
      </div>
      <button className="btn btn-secondary" type="button" onClick={handlePasswordChange}>Changer le mot de passe</button>
      {passwordMsg && <div className="mt-2">{passwordMsg}</div>}
    </div>
  );
}


