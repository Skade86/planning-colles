import React, { useState } from 'react';
import StatsCharts from './StatsCharts';
import ContraintesCheck from './ContraintesCheck';
import Button from 'react-bootstrap/Button';

function AnalysePage() {
  const [analysisData, setAnalysisData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);
    setAnalysisData(null);

    try {
      const res = await fetch('http://localhost:8000/api/analyse_planning', { 
        method: 'POST' 
      });
      const data = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        setAnalysisData(data);
      }
    } catch (e) {
      setError("Erreur de connexion au backend. Vérifiez qu'il est lancé sur localhost:8000");
      console.log(e.data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container-fluid">
      <h2>Analyse du planning généré</h2>
      <p>Cette page permet d'analyser le planning généré et de vérifier le respect des contraintes.</p>

     <Button 
        onClick={fetchAnalysis} 
        disabled={loading}
        variant="primary"   // ✅ comme les autres ("Générer le planning")
>
        {loading ? 'Analyse en cours...' : 'Analyser le planning'}
      </Button>

      {error && (
        <div className="error-message mt-3">
          ❌ {error}
        </div>
      )}

      {analysisData && (
        <div className="analysis-results mt-4">
          <h3>📊 Statistiques</h3>
          <StatsCharts stats={analysisData.stats} />

          <h3 className="mt-4">✅ Vérification des contraintes</h3>
          <ContraintesCheck contraintes={analysisData.contraintes} />
        </div>
      )}
    </div>
  );
}

export default AnalysePage;