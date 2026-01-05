import React, { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer
} from "recharts";
import { Card, Row, Col, Form, Button } from 'react-bootstrap';

const BASE_URL = import.meta.env.VITE_API_URL;

export default function AnalysePage() {
  const [file, setFile] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // Configuration des règles d'alternance pour l'analyse
  const [reglesAlternance, setReglesAlternance] = useState({
    'Mathématiques': { active: true, frequence: 1 }, // MPSI: 1/semaine
    'Physique': { active: true, frequence: 2 }, // MPSI: 1/quinzaine
    'Chimie': { active: false, frequence: 4 }, // Non utilisé pour MPSI
    'Anglais': { active: true, frequence: 2 }, // MPSI: 1/quinzaine
    'Français': { active: false, frequence: 8 }, // Non utilisé pour MPSI
    'S.I': { active: false, frequence: 4 } // Non utilisé pour MPSI
  });

  // Options prédéfinies
  const matieresOptions = [
    'Mathématiques', 'Physique', 'Chimie', 'Anglais', 'Français', 'S.I'
  ];

  // Modifier une règle d'alternance
  const modifierRegleAlternance = (matiere, propriete, valeur) => {
    setReglesAlternance(prev => ({
      ...prev,
      [matiere]: {
        ...prev[matiere],
        [propriete]: valeur
      }
    }));
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0] || null);
    setData(null);
    setErrorMsg("");
  };

  const handleAnalyse = async () => {
    if (!file) {
      setErrorMsg("Sélectionnez un fichier CSV.");
      return;
    }
    setLoading(true);
    setErrorMsg("");

    try {
      const formData = new FormData();
      // IMPORTANT: la clé doit être "file" pour coller au backend FastAPI
      formData.append("file", file);
      formData.append("reglesAlternance", JSON.stringify(reglesAlternance));

      const res = await fetch(`${BASE_URL}/api/analyse_planning`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        let details = "";
        try { details = await res.text(); } catch { /* empty */ }
        throw new Error(`Erreur ${res.status} ${res.statusText}${details ? ` - ${details}` : ""}`);
      }

      const result = await res.json();
      setData(result);
    } catch (err) {
      console.error("Erreur analyse:", err);
      setErrorMsg(err.message || "Erreur lors de l'analyse.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyseGenerated = async () => {
    setLoading(true);
    setErrorMsg("");

    try {
      const res = await fetch(`${BASE_URL}/api/analyse_planning_generated`, {
        method: "POST",
        headers: { 
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ reglesAlternance })
      });

      if (!res.ok) {
        let details = "";
        try { details = await res.text(); } catch { /* empty */ }
        throw new Error(`Erreur ${res.status} ${res.statusText}${details ? ` - ${details}` : ""}`);
      }

      const result = await res.json();
      setData(result);
      setFile(null); // Reset file selection
    } catch (err) {
      console.error("Erreur analyse planning généré:", err);
      setErrorMsg(err.message || "Erreur lors de l'analyse du planning généré.");
    } finally {
      setLoading(false);
    }
  };

  const renderBarChart = (title, obj) => {
    if (!obj || Object.keys(obj).length === 0) return (
      <div style={{ marginTop: 24 }}>
        <h4>{title}</h4>
        <p style={{ color: "#777" }}>Aucune donnée</p>
      </div>
    );
    const chartData = Object.entries(obj).map(([k, v]) => ({
      name: isNaN(Number(k)) ? k : `Groupe ${k}`,
      value: v
    }));
    return (
      <div style={{ marginTop: 24 }}>
        <h4>{title}</h4>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" name="Total" fill="#466089" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  const renderChargeHebdo = (chargeObj) => {
    if (!chargeObj || Object.keys(chargeObj).length === 0) return null;
    // On affiche la charge moyenne par groupe (simple)
    const dataAvg = Object.entries(chargeObj).map(([g, arr]) => {
      const avg = Array.isArray(arr) && arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length) : 0;
      return { name: `Groupe ${g}`, value: Number(avg.toFixed(2)) };
    });
    return (
      <div style={{ marginTop: 24 }}>
        <h4>Charge hebdomadaire moyenne par groupe</h4>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={dataAvg}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" name="Colles / semaine (moy.)" fill="#82ca9d" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Analyse du planning</h2>
      <p>Cette page permet d'analyser le planning généré et de vérifier le respect des contraintes :</p>
      <ul style={{ fontSize: "0.9em", color: "#666" }}>
        <li><strong>Contraintes globales</strong> : Pas de conflits (2 groupes/prof en parallèle, 2 colles/groupe simultanées)</li>
        <li><strong>Contraintes par groupe</strong> : Bon nombre de colles par matière selon les règles configurées</li>
        <li><strong>Colles consécutives</strong> : Détection des créneaux adjacents le même jour</li>
        <li><strong>Compatibilités professeurs</strong> : Respect des disponibilités paires/impaires</li>
      </ul>

      {/* Configuration des règles d'alternance */}
      <Card className="mb-4">
        <Card.Header><h5>⚙️ Configuration des règles d'alternance pour l'analyse</h5></Card.Header>
        <Card.Body>
          <p className="text-muted mb-3">
            Configurez les règles d'alternance attendues pour valider le planning. 
            Ces règles serviront à vérifier si le planning respecte vos attentes.
          </p>
          <Row>
            {matieresOptions.map(matiere => (
              <Col md={6} key={matiere} className="mb-3">
                <Form.Check
                  type="checkbox"
                  id={`regle-analyse-${matiere}`}
                  label={matiere}
                  checked={reglesAlternance[matiere]?.active || false}
                  onChange={(e) => modifierRegleAlternance(matiere, 'active', e.target.checked)}
                  className="mb-2"
                />
                {reglesAlternance[matiere]?.active && (
                  <Form.Group>
                    <Form.Label className="small">Fréquence attendue (en semaines)</Form.Label>
                    <Form.Select
                      size="sm"
                      value={reglesAlternance[matiere]?.frequence || 2}
                      onChange={(e) => modifierRegleAlternance(matiere, 'frequence', parseInt(e.target.value))}
                    >
                      <option value={1}>Chaque semaine (1 colle/semaine)</option>
                      <option value={2}>Quinzaine (1 colle/2 semaines)</option>
                      <option value={4}>Mensuelle (1 colle/4 semaines)</option>
                      <option value={8}>Bimestrielle (1 colle/8 semaines)</option>
                    </Form.Select>
                  </Form.Group>
                )}
              </Col>
            ))}
          </Row>
        </Card.Body>
      </Card>

      <div className="mb-3" style={{ maxWidth: 420 }}>
        <input className="form-control" type="file" accept=".csv,text/csv" onChange={handleFileChange} />
      </div>

      <div className="mb-3">
        <button className="btn btn-primary me-2" onClick={handleAnalyse} disabled={loading}>
          {loading ? "Analyse en cours..." : "Analyser le fichier"}
        </button>
        <button className="btn btn-success" onClick={handleAnalyseGenerated} disabled={loading}>
          {loading ? "Analyse en cours..." : "Analyser le planning généré"}
        </button>
      </div>

      <div className="mb-2">
        <small className="text-muted">
          💡 <strong>Analyser le fichier</strong> : sélectionnez un fichier CSV à analyser<br/>
          💡 <strong>Analyser le planning généré</strong> : analyse directe du dernier planning créé
        </small>
      </div>

      {errorMsg && (
        <div className="alert alert-danger mt-3" role="alert">
          {errorMsg}
        </div>
      )}

      {data && (
        <div className="card mt-4">
          <div className="card-body">
            <h3 className="card-title">Résumé global</h3>
            <p style={{ fontSize: 18 }}>
              {data?.resume?.total_erreurs === 0 ? (
                <span style={{ color: "green" }}>✅ Aucun problème détecté</span>
              ) : (
                <span style={{ color: "red" }}>❌ {data?.resume?.total_erreurs} problème(s) détecté(s)</span>
              )}
            </p>
            <ul>
              <li>Contraintes globales : {data?.resume?.globales_ok ? "✅" : "❌"}</li>
              <li>Contraintes par groupe : {data?.resume?.groupes_ok ? "✅" : "❌"}</li>
              <li>Colles consécutives : {data?.resume?.consecutives_ok ? "✅" : "❌"}</li>
              <li>Compatibilités professeurs : {data?.resume?.compatibilites_profs_ok ? "✅" : "❌"}</li>
            </ul>

            <h3 className="mt-4">Statistiques</h3>
            <div className="alert alert-light">
              <div><b>Créneaux utilisés</b>: {data?.stats?.globales?.creneaux_utilises} / {data?.stats?.globales?.total_creneaux}</div>
              <div><b>Taux d'utilisation</b>: {data?.stats?.globales?.taux_utilisation}%</div>
            </div>

            {renderBarChart("Colles par groupe", data?.stats?.groupes)}
            {renderBarChart("Colles par matière", data?.stats?.matieres)}
            {renderBarChart("Colles par professeur", data?.stats?.profs)}
            {renderChargeHebdo(data?.stats?.charge_hebdo)}

            <h3 className="mt-4">Contraintes détaillées</h3>

            <h4>Globales</h4>
            {Array.isArray(data?.contraintes?.globales) && data.contraintes.globales.length > 0 ? (
              <ul>{data.contraintes.globales.map((c, i) => <li key={i}>{c}</li>)}</ul>
            ) : (
              <p style={{ color: "green" }}>✅ Aucun conflit détecté</p>
            )}

            <h4>Par groupe</h4>
            {Object.entries(data?.contraintes?.groupes || {}).map(([g, errs]) => (
              <div key={g} className="mb-2">
                <b>Groupe {g}</b>
                {errs && errs.length > 0 ? (
                  <ul>{errs.map((e, i) => <li key={i}>{e}</li>)}</ul>
                ) : (
                  <p style={{ color: "green" }}>✅ OK</p>
                )}
              </div>
            ))}

            <h4>Consécutives</h4>
            {Array.isArray(data?.contraintes?.consecutives) && data.contraintes.consecutives.length > 0 ? (
              <ul>{data.contraintes.consecutives.map((c, i) => <li key={i}>{c}</li>)}</ul>
            ) : (
              <p style={{ color: "green" }}>✅ Aucune colle consécutive</p>
            )}

            <h4>Compatibilités professeurs</h4>
            {Array.isArray(data?.contraintes?.compatibilites_profs) && data.contraintes.compatibilites_profs.length > 0 ? (
              <ul>{data.contraintes.compatibilites_profs.map((c, i) => <li key={i} style={{ color: "red" }}>{c}</li>)}</ul>
            ) : (
              <p style={{ color: "green" }}>✅ Toutes les compatibilités professeurs respectées</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}