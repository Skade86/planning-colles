import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import PlanningTable from './components/PlanningTable';
import GenerateButton from './components/GenerateButton';
import DownloadButton from './components/DownloadButton';
import AnalysePage from './components/AnalysePage';
import GroupeDetails from './components/GroupeDetails';
import './App.css';

function App() {
  const [planning, setPlanning] = useState(null);
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState(null);
  const [currentPage, setCurrentPage] = useState('planning'); // 'planning' ou 'analyse'

  return (
    <div className="App">
      <h1>Générateur de planning de colles</h1>

      {/* Navigation */}
      <div className="navigation">
        <button 
          className={currentPage === 'planning' ? 'nav-active' : 'nav-button'}
          onClick={() => setCurrentPage('planning')}
        >
          Planning
        </button>
        <button 
          className={currentPage === 'analyse' ? 'nav-active' : 'nav-button'}
          onClick={() => setCurrentPage('analyse')}
        >
          Analyse
        </button>

        <button 
          className={currentPage === 'groupe' ? 'nav-active' : 'nav-button'}
          onClick={() => setCurrentPage('groupe')}
        >
         Détail groupe
        </button>
      </div>

      {currentPage === 'planning' && (
        <div>
          <p>
            Importez votre fichier CSV de créneaux, puis cliquez sur <b>Générer le planning</b>.<br />
            <span style={{ color: '#466089' }}>
              Le backend doit être lancé sur <b>localhost:8000</b>.
            </span>
          </p>
          <FileUpload setPreview={setPreview} setStatus={setStatus} />
          {preview && <PlanningTable planning={preview} title="Prévisualisation du CSV" />}
          <GenerateButton setPlanning={setPlanning} setStatus={setStatus} />
          {planning && <DownloadButton />}
          {planning && <PlanningTable planning={planning} title="Planning généré" />}
          {status && (
            <div className={`status-message${status.type === 'error' ? ' error' : ''}`}>
              {status.text}
            </div>
          )}
        </div>
      )}

      {currentPage === 'analyse' && (
        <AnalysePage />
      )}

      {currentPage === 'groupe' && (
        <GroupeDetails />
      )}
    </div>
  );
}

export default App;
