import React, { useState, useEffect } from "react";

export default function GroupeDetails() {
  const [groupe, setGroupe] = useState(1);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchDetails = async (g) => {
    setLoading(true);
    setError("");
    setDetails(null);
    try {
      const res = await fetch(`http://localhost:8000/api/groupe_details/${g}`);
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        setDetails(data);
      }
    } catch (e) {
      setError("Erreur lors de la récupération des détails.");
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchDetails(groupe);
    // eslint-disable-next-line
  }, [groupe]);

  return (
    <div style={{ maxWidth: 700, margin: "auto" }}>
      <h2>Détail d’un groupe</h2>
      <label>
        Groupe&nbsp;
        <select value={groupe} onChange={e => setGroupe(Number(e.target.value))}>
          {[...Array(16)].map((_, i) => (
            <option key={i+1} value={i+1}>{i+1}</option>
          ))}
        </select>
      </label>
      {loading && <p>Chargement…</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {details && (
        <div>

          <h3>Créneaux</h3>
          {!details.creneaux || details.creneaux.length === 0 ? (
            <p>Aucun créneau trouvé pour ce groupe.</p>
          ) : (
            <ul>
              {details.creneaux.map((c, i) => (
                <li key={i}>
                  Semaine {c.semaine} : <b>{c.matiere}</b> avec {c.prof} ({c.jour} {c.heure})
                </li>
              ))}
            </ul>
          )}
          <h3>Colles par matière</h3>
          {details.colles_par_matiere && Object.entries(details.colles_par_matiere).map(([mat, colles]) => (
            <div key={mat} style={{ marginBottom: 10 }}>
              <strong>{mat} :</strong>
              {(!colles || colles.length === 0) ? (
                <span> aucune</span>
              ) : (
                <ul>
                  {colles.map((c, i) => (
                    <li key={i}>
                      Semaine {c.semaine} avec {c.prof} ({c.jour} {c.heure})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          <h3>Contraintes non respectées</h3>
          {details.contraintes && details.contraintes.length === 0 ? (
            <p style={{ color: "green" }}>Aucune</p>
          ) : (
            <ul>
              {details.contraintes && details.contraintes.map((err, i) => <li key={i}>{err}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}