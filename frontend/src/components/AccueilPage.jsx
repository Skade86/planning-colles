import React from 'react';
import { Container, Card, Row, Col, Button } from 'react-bootstrap';
import Login from './Login';
import { useAuth } from '../AuthContext';

export default function AccueilPage({ setCurrentPage }) {
  const { isAuthenticated, user } = useAuth();

  return (
    <Container>
      <div className="text-center mb-5">
        <h1 className="display-4 mb-3">🎓 Générateur de planning de colles</h1>
        <p className="lead text-muted">
          Organisez facilement vos colles avec notre outil de planification automatique
        </p>
      </div>

      {/* Si non connecté, afficher le formulaire de login */}
      {!isAuthenticated ? (
        <Row className="justify-content-center">
          <Col md={8} lg={6}>
            <Card className="shadow">
              <Card.Header className="bg-primary text-white text-center">
                <h4 className="mb-0">Connexion requise</h4>
              </Card.Header>
              <Card.Body>
                <p className="text-center mb-4">
                  Connectez-vous pour accéder au générateur de planning
                </p>
                <div className="alert alert-info small">
                  <i className="bi bi-info-circle me-2"></i>
                  <strong>Note :</strong> Les autres menus sont désactivés tant que vous n'êtes pas connecté. 
                  Après connexion, vous aurez accès à toutes les fonctionnalités.
                </div>
                <Login />
              </Card.Body>
            </Card>
          </Col>
        </Row>
      ) : (
        /* Si connecté, afficher les fonctionnalités disponibles */
        <div>
          <div className="text-center mb-4">
            <h3>Bienvenue {user?.username ? user.username : ''} ! 👋</h3>
            <p className="text-muted">Que souhaitez-vous faire aujourd'hui ?</p>
          </div>

          <Row>
            <Col md={6} className="mb-4">
              <Card className="h-100 shadow-sm border-0">
                <Card.Body className="text-center">
                  <div className="mb-3">
                    <i className="bi bi-pencil-square" style={{ fontSize: '2rem', color: '#0d6efd' }}></i>
                  </div>
                  <Card.Title>Saisie des créneaux</Card.Title>
                  <Card.Text>
                    Créez votre planning en saisissant directement les créneaux disponibles via un formulaire intuitif.
                  </Card.Text>
                  <Button 
                    variant="primary" 
                    onClick={() => setCurrentPage('saisie')}
                  >
                    Commencer la saisie
                  </Button>
                </Card.Body>
              </Card>
            </Col>

            <Col md={6} className="mb-4">
              <Card className="h-100 shadow-sm border-0">
                <Card.Body className="text-center">
                  <div className="mb-3">
                    <i className="bi bi-file-earmark-spreadsheet" style={{ fontSize: '2rem', color: '#198754' }}></i>
                  </div>
                  <Card.Title>Import CSV</Card.Title>
                  <Card.Text>
                    Importez un fichier CSV contenant vos créneaux existants pour générer automatiquement le planning.
                  </Card.Text>
                  <Button 
                    variant="success" 
                    onClick={() => setCurrentPage('planning')}
                  >
                    Importer CSV
                  </Button>
                </Card.Body>
              </Card>
            </Col>

            <Col md={6} className="mb-4">
              <Card className="h-100 shadow-sm border-0">
                <Card.Body className="text-center">
                  <div className="mb-3">
                    <i className="bi bi-graph-up" style={{ fontSize: '2rem', color: '#fd7e14' }}></i>
                  </div>
                  <Card.Title>Analyse</Card.Title>
                  <Card.Text>
                    Analysez un planning existant pour vérifier le respect des contraintes et visualiser les statistiques.
                  </Card.Text>
                  <Button 
                    variant="warning" 
                    onClick={() => setCurrentPage('analyse')}
                  >
                    Analyser
                  </Button>
                </Card.Body>
              </Card>
            </Col>

            <Col md={6} className="mb-4">
              <Card className="h-100 shadow-sm border-0">
                <Card.Body className="text-center">
                  <div className="mb-3">
                    <i className="bi bi-collection" style={{ fontSize: '2rem', color: '#6f42c1' }}></i>
                  </div>
                  <Card.Title>Mes plannings</Card.Title>
                  <Card.Text>
                    Consultez et gérez vos plannings sauvegardés. Téléchargez-les dans différents formats.
                  </Card.Text>
                  <Button 
                    variant="secondary" 
                    onClick={() => setCurrentPage('mesplannings')}
                  >
                    Voir mes plannings
                  </Button>
                </Card.Body>
              </Card>
            </Col>
          </Row>

          {/* Section d'informations */}
          <Card className="mt-4 bg-light border-0">
            <Card.Body>
              <h5>ℹ️ Comment ça fonctionne ?</h5>
              <Row>
                <Col md={4}>
                  <div className="text-center mb-3">
                    <div className="badge bg-primary rounded-circle p-2 mb-2">1</div>
                    <h6>Définir les créneaux</h6>
                    <small className="text-muted">Saisissez ou importez vos créneaux disponibles</small>
                  </div>
                </Col>
                <Col md={4}>
                  <div className="text-center mb-3">
                    <div className="badge bg-primary rounded-circle p-2 mb-2">2</div>
                    <h6>Configurer les règles</h6>
                    <small className="text-muted">Définissez la fréquence des colles par matière</small>
                  </div>
                </Col>
                <Col md={4}>
                  <div className="text-center mb-3">
                    <div className="badge bg-primary rounded-circle p-2 mb-2">3</div>
                    <h6>Générer & analyser</h6>
                    <small className="text-muted">Obtenez votre planning optimisé automatiquement</small>
                  </div>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </div>
      )}
    </Container>
  );
}
