import React, { useState, useEffect } from 'react';
import FileUpload from './components/FileUpload';
import PlanningTable from './components/PlanningTable';
import GenerateButton from './components/GenerateButton';
import DownloadButton from './components/DownloadButton';
import AnalysePage from './components/AnalysePage';
import GroupeDetails from './components/GroupeDetails';
import Extend24Button from './components/Extend24Button';
import FormatToggle from './components/FormatToggle';
import { Navbar, Nav, Container } from "react-bootstrap";
import Form from 'react-bootstrap/Form';  // 👉 à ajouter en haut
import './App.css';

function App() {
  const [planning, setPlanning] = useState(null);
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState(null);
  const [currentPage, setCurrentPage] = useState('planning'); // onglet actif

  // Nouveaux states pour gestion groupes
  const [groups, setGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState("");

  // Format de téléchargement global
  const [downloadFormat, setDownloadFormat] = useState('csv');

  // Charger la liste des groupes après génération d'un planning
  useEffect(() => {
    if (planning) {
      fetch("http://localhost:8000/api/get_groups")
        .then((res) => res.json())
        .then((data) => {
          if (data.groups) {
            setGroups(data.groups);
          }
        })
        .catch((err) => console.error("Erreur chargement groupes:", err));
    }
  }, [planning]);

  return (
    <div>
      {/* ✅ Header avec titre + navbar */}
      <header className="p-3 bg-white shadow-sm">
        <Container fluid>
          <h1>Générateur de planning de colles</h1>
          <Navbar bg="primary" variant="dark" expand="lg" className="mt-3 rounded">
            <Navbar.Toggle aria-controls="main-navbar-nav" />
            <Navbar.Collapse id="main-navbar-nav">
              <Nav
                activeKey={currentPage}
                onSelect={(selectedKey) => setCurrentPage(selectedKey)}
                className="me-auto"
              >
                <Nav.Link eventKey="planning">Planning</Nav.Link>
                <Nav.Link eventKey="analyse">Analyse</Nav.Link>
                <Nav.Link eventKey="groupe">Détail groupe</Nav.Link>
              </Nav>
            </Navbar.Collapse>
          </Navbar>
        </Container>
      </header>

      {/* ✅ Contenu principal */}
      <main className="container-fluid mt-4">
        {/* Page Planning */}
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

            <div className="d-flex flex-wrap gap-2 mt-2">
              <GenerateButton setPlanning={setPlanning} setStatus={setStatus} />
            </div>

            {planning && (
              <div className="mt-3">
                <FormatToggle format={downloadFormat} setFormat={setDownloadFormat} />
                <div className="d-flex flex-wrap gap-2 mt-2">
                  <DownloadButton format={downloadFormat} />
                  <Extend24Button disabled={!planning} setStatus={setStatus} format={downloadFormat} />
                </div>
              </div>
            )}

            {planning && <PlanningTable planning={planning} title="Planning généré" />}
            {status && (
              <div className={`status-message${status.type === 'error' ? ' error' : ''}`}>
                {status.text}
              </div>
            )}
          </div>
        )}

        {/* Page Analyse */}
        {currentPage === 'analyse' && (
          <AnalysePage />
        )}

        {/* Page Détail Groupe */}
        {currentPage === 'groupe' && (
          <div style={{ padding: "1rem" }}>
            <h2>Choisir un groupe</h2>
            {groups.length === 0 ? (
              <p style={{ color: "orange" }}>
                ⚠️ Vous devez d'abord <b>générer un planning</b> avant d'accéder aux détails des groupes.
              </p>
            ) : (
              <>

          <Form.Select 
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            style={{ maxWidth: "250px" }}  // optionnel, pour limiter la largeur
          >
            <option value="">-- Sélectionnez un groupe --</option>
            {groups.map((g) => (
              <option key={g} value={g}>Groupe {g}</option>
            ))}
          </Form.Select>
                {selectedGroup && <GroupeDetails groupId={selectedGroup} />}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;