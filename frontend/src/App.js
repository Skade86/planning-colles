import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import PlanningTable from './components/PlanningTable';
import GenerateButton from './components/GenerateButton';
import DownloadButton from './components/DownloadButton';
import AnalysePage from './components/AnalysePage';
import GroupeDetails from './components/GroupeDetails';
import Navbar from 'react-bootstrap/Navbar';
import Nav from 'react-bootstrap/Nav';
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
      <Navbar bg="primary" variant="dark" expand="md" className="mb-4">
        <Navbar.Toggle aria-controls="main-navbar-nav" />
        <Navbar.Collapse id="main-navbar-nav">
          <Nav
            activeKey={currentPage}
            onSelect={selectedKey => setCurrentPage(selectedKey)}
            className="me-auto"
          >
            <Nav.Link eventKey="planning">Planning</Nav.Link>
            <Nav.Link eventKey="analyse">Analyse</Nav.Link>
            <Nav.Link eventKey="groupe">Détail groupe</Nav.Link>
          </Nav>
        </Navbar.Collapse>
      </Navbar>

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
