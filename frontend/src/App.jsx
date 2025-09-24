const BASE_URL = import.meta.env.VITE_API_URL;
import React, { useState, useEffect } from 'react';
import FileUpload from './components/FileUpload';
import PlanningTable from './components/PlanningTable';
import GenerateButton from './components/GenerateButton';
import DownloadButton from './components/DownloadButton';
import AnalysePage from './components/AnalysePage';
import GroupeDetails from './components/GroupeDetails';
import SaisiePage from './components/SaisiePage';
import FormatToggle from './components/FormatToggle';
import SavePlanningButton from './components/SavePlanningButton';
import MesPlannings from './components/MesPlannings';
import MonProfil from './components/MonProfil';
import { Navbar, Nav, Container, Card, Row, Col } from "react-bootstrap";
import Form from 'react-bootstrap/Form';
import './App.css';
import Login from './components/Login';
import { useAuth } from './AuthContext';

function App() {
  const { isAuthenticated, user, logout } = useAuth();
  const [planning, setPlanning] = useState(null);
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState(null);
  const [currentPage, setCurrentPage] = useState('saisie'); // onglet actif par défaut

  // Nouveaux states pour gestion groupes
  const [groups, setGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState("");

  // Format de téléchargement global
  const [downloadFormat, setDownloadFormat] = useState('csv');

  // Configuration des règles d'alternance pour la page Planning
  const [reglesAlternance, setReglesAlternance] = useState({
    'Mathématiques': { active: true, frequence: 1 }, // 1 = chaque semaine
    'Physique': { active: true, frequence: 2 }, // 2 = quinzaine
    'Chimie': { active: true, frequence: 4 }, // 4 semaines par défaut
    'Anglais': { active: true, frequence: 2 }, // quinzaine
    'Français': { active: true, frequence: 8 }, // 8 semaines
    'S.I': { active: true, frequence: 4 } // 4 semaines
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

  // Charger la liste des groupes après génération d'un planning
  useEffect(() => {
    if (planning) {
  fetch(`${BASE_URL}/api/get_groups`, {
        headers: user ? { 'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}` } : {}
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.groups) {
            setGroups(data.groups);
          }
        })
        .catch((err) => console.error("Erreur chargement groupes:", err));
    }
  }, [planning, user]);

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
                <Nav.Link eventKey="saisie">Saisie</Nav.Link>
                <Nav.Link eventKey="planning">Planning</Nav.Link>
                <Nav.Link eventKey="analyse">Analyse</Nav.Link>
                <Nav.Link eventKey="mesplannings">Mes plannings</Nav.Link>
                <Nav.Link eventKey="profil">Mon profil</Nav.Link>
                <Nav.Link eventKey="groupe">Détail groupe</Nav.Link>
              </Nav>
              <div className="text-white me-3 d-flex align-items-center">
                {isAuthenticated ? (
                  <>
                    <span className="me-3">Connecté{user?.username ? `: ${user.username}` : ''}{user?.role ? ` (${user.role})` : ''}</span>
                    <button className="btn btn-sm btn-outline-light" onClick={logout}>Se déconnecter</button>
                  </>
                ) : (
                  <span>Non connecté</span>
                )}
              </div>
            </Navbar.Collapse>
          </Navbar>
        </Container>
      </header>

      {/* ✅ Contenu principal */}
      <main className="container-fluid mt-4">
        {/* Page Saisie */}
        {currentPage === 'saisie' && (
          isAuthenticated ? <SaisiePage /> : <Login />
        )}

        {/* Page Planning */}
        {currentPage === 'planning' && (
          <div>
            <p>
              Importez votre fichier CSV de créneaux, puis cliquez sur <b>Générer le planning</b>.<br />
              <span style={{ color: '#466089' }}>
                Vous pouvez aussi entrer manuellement les créneaux dans l'onglet "Saisie".
              </span>
            </p>
            {isAuthenticated ? (
              <FileUpload setPreview={setPreview} setStatus={setStatus} />
            ) : (
              <Login />
            )}
            
            {/* Configuration des règles d'alternance */}
            {isAuthenticated && (
              <Card className="mb-4 mt-4">
                <Card.Header><h5>⚙️ Configuration des règles d'alternance</h5></Card.Header>
                <Card.Body>
                  <p className="text-muted mb-3">
                    Configurez la fréquence des colles pour chaque matière (en semaines). 
                    Décochez une matière pour la désactiver complètement.
                  </p>
                  <Row>
                    {matieresOptions.map(matiere => (
                      <Col md={6} key={matiere} className="mb-3">
                        <Form.Check
                          type="checkbox"
                          id={`regle-planning-${matiere}`}
                          label={matiere}
                          checked={reglesAlternance[matiere]?.active || false}
                          onChange={(e) => modifierRegleAlternance(matiere, 'active', e.target.checked)}
                          className="mb-2"
                        />
                        {reglesAlternance[matiere]?.active && (
                          <Form.Group>
                            <Form.Label className="small">Fréquence (en semaines)</Form.Label>
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
            )}
            
            {preview && <PlanningTable planning={preview} title="Prévisualisation du CSV" />}

            {isAuthenticated && (
              <div className="d-flex flex-wrap gap-2 mt-2">
                <GenerateButton setPlanning={setPlanning} setStatus={setStatus} reglesAlternance={reglesAlternance} />
                <SavePlanningButton defaultName={"Planning"} onSaved={() => {}} />
              </div>
            )}

            {planning && (
              <div className="mt-3">
                <FormatToggle format={downloadFormat} setFormat={setDownloadFormat} />
                <div className="d-flex flex-wrap gap-2 mt-2">
                  <DownloadButton format={downloadFormat} />
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
          isAuthenticated ? <AnalysePage /> : <Login />
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

        {/* Page Mes Plannings */}
        {currentPage === 'mesplannings' && (
          isAuthenticated ? <MesPlannings /> : <Login />
        )}

        {/* Page Mon Profil */}
        {currentPage === 'profil' && (
          isAuthenticated ? <MonProfil /> : <Login />
        )}
      </main>
    </div>
  );
}

export default App;