import React, { useState, useRef } from 'react';
import { useAuth } from '../AuthContext';

const BASE_URL = 'http://localhost:8000';

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('utilisateur');
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [nom, setNom] = useState('');
  const [lycee, setLycee] = useState("");
  const [lyceeOptions, setLyceeOptions] = useState([]);
  const [showLyceeOptions, setShowLyceeOptions] = useState(false);
  const lyceeInputRef = useRef();
  // Auto-complétion lycée (API Education Nationale)
  const handleLyceeInput = async (e) => {
    const value = e.target.value;
    setLycee(value);
    if (value.length < 3) {
      setLyceeOptions([]);
      setShowLyceeOptions(false);
      return;
    }
    try {
      const res = await fetch(`https://data.education.gouv.fr/api/records/1.0/search/?dataset=fr-en-annuaire-education&q=${encodeURIComponent(value)}&rows=10&facet=nom_etablissement&refine.nature_uai=Lycée`);
      const data = await res.json();
      const options = (data.records || []).map(r => r.fields.nom_etablissement).filter(Boolean);
      setLyceeOptions(options);
      setShowLyceeOptions(true);
    } catch {
      setLyceeOptions([]);
      setShowLyceeOptions(false);
    }
  };

  const handleLyceeSelect = (option) => {
    setLycee(option);
    setShowLyceeOptions(false);
    lyceeInputRef.current && lyceeInputRef.current.blur();
  };
  const [classes, setClasses] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'signup') {
        if (!lycee.trim() || !classes.trim()) {
          setError('Lycée et au moins une classe sont obligatoires');
          setLoading(false);
          return;
        }
        const r = await fetch(`${BASE_URL}/api/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, nom, role, lycee: lycee.trim(), classes: classes.split(',').map(s => s.trim()).filter(Boolean) })
        });
        if (!r.ok) throw new Error('Inscription impossible');
      }

      const form = new URLSearchParams();
      form.append('username', email); // username = email côté backend
      form.append('password', password);
      const res = await fetch(`${BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString()
      });
      if (!res.ok) throw new Error('Identifiants invalides');
      const data = await res.json();
      const userInfo = { email, nom, role };
      login(data.access_token, userInfo);
    } catch (err) {
      setError(err.message || 'Erreur');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 360 }}>
      <h2>{mode === 'login' ? 'Connexion' : "Créer un compte"}</h2>
      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <label className="form-label">Email</label>
          <input type="email" className="form-control" value={email} onChange={e => setEmail(e.target.value)} required />
        </div>
        {mode === 'signup' && (
          <>
            <div className="mb-3">
              <label className="form-label">Nom</label>
              <input className="form-control" value={nom} onChange={e => setNom(e.target.value)} required />
            </div>
            <div className="mb-3" style={{ position: 'relative' }}>
              <label className="form-label">Lycée</label>
              <input
                className="form-control"
                value={lycee}
                onChange={handleLyceeInput}
                onFocus={handleLyceeInput}
                ref={lyceeInputRef}
                autoComplete="off"
                required
              />
              {showLyceeOptions && lyceeOptions.length > 0 && (
                <ul style={{ position: 'absolute', zIndex: 10, background: 'white', border: '1px solid #ccc', width: '100%', maxHeight: 180, overflowY: 'auto', margin: 0, padding: 0, listStyle: 'none' }}>
                  {lyceeOptions.map(option => (
                    <li key={option} style={{ padding: 8, cursor: 'pointer' }} onMouseDown={() => handleLyceeSelect(option)}>{option}</li>
                  ))}
                </ul>
              )}
            </div>
            <div className="mb-3">
              <label className="form-label">Classes (séparées par des virgules)</label>
              <input className="form-control" value={classes} onChange={e => setClasses(e.target.value)} required />
            </div>
          </>
        )}
        <div className="mb-3">
          <label className="form-label">Mot de passe</label>
          <input type="password" className="form-control" value={password} onChange={e => setPassword(e.target.value)} required />
        </div>
        {mode === 'signup' && (
          <div className="mb-3">
            <label className="form-label">Rôle</label>
            <select className="form-select" value={role} onChange={e => setRole(e.target.value)}>
              <option value="utilisateur">Utilisateur</option>
              <option value="professeur">Professeur</option>
            </select>
          </div>
        )}
        {error && <div className="alert alert-danger">{error}</div>}
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? '...' : (mode === 'login' ? 'Se connecter' : "S'inscrire")}
        </button>
        <button type="button" className="btn btn-link" onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>
          {mode === 'login' ? "Créer un compte" : 'Déjà un compte ? Connexion'}
        </button>
      </form>
      <div className="mt-3">
        <small>Comptes de démo:<br/>
          • Professeur: <b>admin@demo.fr / admin</b><br/>
          • Utilisateur: <b>user@demo.fr / user</b>
        </small>
      </div>
    </div>
  );
}


