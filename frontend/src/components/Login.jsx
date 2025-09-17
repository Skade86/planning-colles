import React, { useState } from 'react';
import { useAuth } from '../AuthContext';

const BASE_URL = 'http://localhost:8000';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('utilisateur');
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'signup') {
        const r = await fetch(`${BASE_URL}/api/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, role })
        });
        if (!r.ok) throw new Error('Inscription impossible');
      }

      const form = new URLSearchParams();
      form.append('username', username);
      form.append('password', password);
      const res = await fetch(`${BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString()
      });
      if (!res.ok) throw new Error('Identifiants invalides');
      const data = await res.json();
      // Decode role from JWT payload (optional). Simpler: infer from signup choice when in signup.
      const userInfo = { username, role };
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
          <label className="form-label">Nom d'utilisateur</label>
          <input className="form-control" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="mb-3">
          <label className="form-label">Mot de passe</label>
          <input type="password" className="form-control" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {mode === 'signup' && (
          <div className="mb-3">
            <label className="form-label">Rôle</label>
            <select className="form-select" value={role} onChange={(e) => setRole(e.target.value)}>
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
          • Professeur: <b>admin / admin</b><br/>
          • Utilisateur: <b>user / user</b>
        </small>
      </div>
    </div>
  );
}


