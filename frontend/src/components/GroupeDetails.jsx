const BASE_URL = import.meta.env.VITE_API_URL;
import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "../AuthContext";

export default function GroupeDetails({ groupId }) {
  const { token } = useAuth();
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    if (!groupId) return;
    setLoading(true);
    setDetails(null);
    setError(null);
    fetch(`${BASE_URL}/api/group_details/${groupId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then((res) => {
        if (!res.ok) {
          throw new Error("Erreur API");
        }
        return res.json();
      })
      .then((data) => {
        setDetails(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Erreur chargement détails groupe", err);
        setError("Impossible de charger les détails du groupe.");
        setLoading(false);
      });
  }, [groupId, token]);

  useEffect(() => {
    load();
  }, [load]);

  if (!groupId) {
    return <p>⚠️ Veuillez sélectionner un groupe pour voir ses détails.</p>;
  }

  if (loading) {
    return <p>Chargement des détails...</p>;
  }

  if (error) {
    return <p style={{ color: "red" }}>{error}</p>;
  }

  if (!details) {
    return <p>Aucune donnée disponible pour ce groupe.</p>;
  }

  return (
    <div style={{ padding: "1rem", border: "1px solid #ccc", borderRadius: "8px" }}>
      <h2>Détails du groupe {details.groupe}</h2>

      {/* Créneaux */}
      <h3>📅 Créneaux planifiés</h3>
      {details.creneaux && details.creneaux.length > 0 ? (
        <ul>
          {details.creneaux.map((c, index) => (
            <li key={index}>
              <strong>Semaine {c.semaine}</strong> : {c.matiere} avec {c.prof} (
              {c.jour} {c.heure})
            </li>
          ))}
        </ul>
      ) : (
        <p>Aucun créneau trouvé pour ce groupe.</p>
      )}

      {/* Stats */}
      <h3>📊 Statistiques</h3>

      <h4>Colles par semaine</h4>
      {details.stats && details.stats.colles_par_semaine ? (
        <ul>
          {Object.entries(details.stats.colles_par_semaine).map(([sem, ncol]) => (
            <li key={sem}>
              Semaine {sem} → {ncol} colle(s)
            </li>
          ))}
        </ul>
      ) : (
        <p>Aucune donnée hebdomadaire.</p>
      )}

      <h4>Colles par matière</h4>
      {details.stats && details.stats.colles_par_matiere ? (
        <ul>
          {Object.entries(details.stats.colles_par_matiere).map(([mat, ncol]) => (
            <li key={mat}>
              {mat} → {ncol} colle(s)
            </li>
          ))}
        </ul>
      ) : (
        <p>Aucune donnée matière.</p>
      )}
    </div>
  );
}