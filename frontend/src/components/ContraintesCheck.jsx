import React, { useState, useEffect } from 'react';

function ContraintesCheck({ contraintes }) {
  const [selectedGroup, setSelectedGroup] = useState(null);

  const groupesDisponibles = Object.keys(contraintes.groupes).map(Number).sort((a, b) => a - b);

  // initialise le groupe sélectionné automatiquement sur le 1er dispo
  useEffect(() => {
    if (groupesDisponibles.length > 0 && selectedGroup === null) {
      setSelectedGroup(groupesDisponibles[0]);
    }
  }, [groupesDisponibles, selectedGroup]);

  const totalErrorsGlobal = contraintes.globales.length;
  const totalErrorsGroups = Object.values(contraintes.groupes).reduce((sum, errors) => sum + errors.length, 0);
  const totalErrors = totalErrorsGlobal + totalErrorsGroups;

  return (
    <div className="contraintes-container">
      {/* Résumé global */}
      <div className="contraintes-summary">
        <div className={`summary-card ${totalErrors === 0 ? 'success' : 'error'}`}>
          <h4>Résumé global</h4>
          <p>{totalErrors === 0 ? '✅ Toutes les contraintes sont respectées !' : `❌ ${totalErrors} erreur(s) détectée(s)`}</p>
          <p>Contraintes globales : {totalErrorsGlobal === 0 ? '✅' : `❌ ${totalErrorsGlobal}`}</p>
          <p>Contraintes par groupe : {totalErrorsGroups === 0 ? '✅' : `❌ ${totalErrorsGroups}`}</p>
        </div>
      </div>

      {/* Contraintes globales */}
      <div className="contraintes-section">
        <h4>Contraintes globales</h4>
        {contraintes.globales.length === 0 ? (
          <div className="success-message">✅ Aucun conflit détecté</div>
        ) : (
          <div className="error-list">
            {contraintes.globales.map((error, index) => (
              <div key={index} className="error-item">❌ {error}</div>
            ))}
          </div>
        )}
      </div>

      {/* Contraintes par groupe */}
      <div className="contraintes-section">
        {/* <h4>Contraintes par groupe</h4>

        
        === Partie détaillée à commenter ===

        // Sélecteur de groupe
        <div className="group-selector">
          <label>Groupe à analyser : </label>
          <select 
            value={selectedGroup || ''} 
            onChange={(e) => setSelectedGroup(parseInt(e.target.value))}
          >
            {groupesDisponibles.map(g => (
              <option key={g} value={g}>Groupe {g}</option>
            ))}
          </select>
        </div>

        // Affichage des erreurs pour le groupe sélectionné
        {selectedGroup !== null && (
          <div className="group-constraints">
            <h5>Groupe {selectedGroup}</h5>
            {contraintes.groupes[selectedGroup].length === 0 ? (
              <div className="success-message">✅ Toutes les contraintes respectées</div>
            ) : (
              <div className="error-list">
                {contraintes.groupes[selectedGroup].map((error, index) => (
                  <div key={index} className="error-item">❌ {error}</div>
                ))}
              </div>
            )}
          </div>
        )}
        */}

        {/* Vue d'ensemble de tous les groupes */}
        {/*<div className="all-groups-overview">
          <h5>Vue d'ensemble</h5>
          <div className="groups-grid">
            {groupesDisponibles.map(g => (
              <div 
                key={g} 
                className={`group-status ${contraintes.groupes[g].length === 0 ? 'success' : 'error'}`}
                onClick={() => setSelectedGroup(g)}
              >
                <span>G{g}</span>
                <span>{contraintes.groupes[g].length === 0 ? '✅' : `❌${contraintes.groupes[g].length}`}</span>
              </div>
            ))}
          </div>
        </div>*/}
      </div>
    </div>
  );
}

export default ContraintesCheck;