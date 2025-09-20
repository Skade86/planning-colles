import React, { useState } from 'react';
import { Form, Button, Card, Row, Col, Alert } from 'react-bootstrap';

const BASE_URL = import.meta.env.VITE_API_URL;

export default function SaisiePage() {
  // État pour les données du formulaire
  const [formData, setFormData] = useState({
    semaines: [],
    nombreGroupes: 15,
    professeurs: [],
    creneaux: [],
    loading: false,
    message: null
  });

  // Options prédéfinies
  const matieresOptions = [
    'Mathématiques', 'Physique', 'Chimie', 'Anglais', 'Français', 'S.I'
  ];

  const joursOptions = [
    'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'
  ];

  const heuresOptions = [
    '8h-9h', '9h-10h', '10h-11h', '11h-12h',
    '14h-15h', '15h-16h', '16h-17h', '17h-18h', '18h-19h', '19h-20h',
    '10h30-11h30', '11h30-12h30'
  ];

  // Gestion des semaines
  const handleSemainesChange = (e) => {
    const value = e.target.value;
    const semaines = value.split(',').map(s => s.trim()).filter(s => s && !isNaN(s));
    setFormData(prev => ({ ...prev, semaines: semaines.map(Number) }));
  };

  // Ajouter un professeur
  const ajouterProfesseur = () => {
    const nouveauProf = {
      id: Date.now(),
      nom: '',
      matieres: [],
      travaillePaires: true,
      travailleImpaires: true
    };
    setFormData(prev => ({
      ...prev,
      professeurs: [...prev.professeurs, nouveauProf]
    }));
  };

  // Modifier un professeur
  const modifierProfesseur = (id, champ, valeur) => {
    setFormData(prev => ({
      ...prev,
      professeurs: prev.professeurs.map(prof =>
        prof.id === id ? { ...prof, [champ]: valeur } : prof
      )
    }));
  };

  // Supprimer un professeur
  const supprimerProfesseur = (id) => {
    setFormData(prev => ({
      ...prev,
      professeurs: prev.professeurs.filter(prof => prof.id !== id)
    }));
  };

  // Ajouter un créneau
  const ajouterCreneau = () => {
    const nouveauCreneau = {
      id: Date.now(),
      matiere: '',
      professeur: '',
      jour: '',
      heure: '',
      groupesPaires: { min: 1, max: 15 },
      groupesImpaires: { min: 1, max: 15 }
    };
    setFormData(prev => ({
      ...prev,
      creneaux: [...prev.creneaux, nouveauCreneau]
    }));
  };

  // Modifier un créneau
  const modifierCreneau = (id, champ, valeur) => {
    setFormData(prev => ({
      ...prev,
      creneaux: prev.creneaux.map(creneau =>
        creneau.id === id ? { ...creneau, [champ]: valeur } : creneau
      )
    }));
  };

  // Supprimer un créneau
  const supprimerCreneau = (id) => {
    setFormData(prev => ({
      ...prev,
      creneaux: prev.creneaux.filter(creneau => creneau.id !== id)
    }));
  };

  // Générer et télécharger le CSV d'entrée
  const exporterCSV = () => {
    if (!validerFormulaire()) return;

    try {
      const csvContent = convertirEnCSV();
      
      // Créer et télécharger le fichier
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', 'creneaux-planification.csv');
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setFormData(prev => ({
        ...prev,
        message: { type: 'success', text: 'CSV d\'entrée téléchargé avec succès !' }
      }));

    } catch (error) {
      setFormData(prev => ({
        ...prev,
        message: { type: 'error', text: `Erreur lors de l'export: ${error.message}` }
      }));
    }
  };

  // Générer et envoyer le CSV
  const genererPlanning = async () => {
    if (!validerFormulaire()) return;

    setFormData(prev => ({ ...prev, loading: true, message: null }));

    try {
      // Convertir le formulaire en données structurées pour le backend
      const donneesFormulaire = {
        semaines: formData.semaines,
        nombreGroupes: formData.nombreGroupes,
        professeurs: formData.professeurs,
        creneaux: formData.creneaux
      };
      
      const response = await fetch(`${BASE_URL}/api/generate_from_form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(donneesFormulaire)
      });

      if (!response.ok) {
        throw new Error(`Erreur ${response.status}`);
      }

      const _result = await response.json();
      setFormData(prev => ({
        ...prev,
        message: { type: 'success', text: 'Planning généré avec succès !' }
      }));

    } catch (error) {
      setFormData(prev => ({
        ...prev,
        message: { type: 'error', text: `Erreur: ${error.message}` }
      }));
    } finally {
      setFormData(prev => ({ ...prev, loading: false }));
    }
  };

  // Validation du formulaire
  const validerFormulaire = () => {
    if (formData.semaines.length === 0) {
      setFormData(prev => ({
        ...prev,
        message: { type: 'error', text: 'Veuillez saisir au moins une semaine' }
      }));
      return false;
    }
    if (formData.professeurs.length === 0) {
      setFormData(prev => ({
        ...prev,
        message: { type: 'error', text: 'Veuillez ajouter au moins un professeur' }
      }));
      return false;
    }
    if (formData.creneaux.length === 0) {
      setFormData(prev => ({
        ...prev,
        message: { type: 'error', text: 'Veuillez ajouter au moins un créneau' }
      }));
      return false;
    }
    return true;
  };

  // Convertir en format CSV pour export/backend
  const convertirEnCSV = () => {
    const semaines = formData.semaines;
    const professeurs = formData.professeurs;
    const creneaux = formData.creneaux;
    
    // Créer les en-têtes CSV
    const headers = [
      'Matière', 'Prof', 'Jour', 'Heure',
      'Groupes possibles semaine paire', 'Groupes possibles semaine impaire',
      'Travaille les semaines paires', 'Travaille les semaines impaires'
    ].concat(semaines.map(s => s.toString()));
    
    // Créer les lignes de données
    const lignes = [];
    for (const creneau of creneaux) {
      // Trouver le professeur correspondant
      const prof = professeurs.find(p => p.nom === creneau.professeur);
      if (!prof) continue;
      
      // Formater les plages de groupes
      const groupesPaires = `${creneau.groupesPaires.min} à ${creneau.groupesPaires.max}`;
      const groupesImpaires = `${creneau.groupesImpaires.min} à ${creneau.groupesImpaires.max}`;
      
      // Ligne complète
      const ligne = [
        creneau.matiere,
        creneau.professeur,
        creneau.jour,
        creneau.heure,
        groupesPaires,
        groupesImpaires,
        prof.travaillePaires ? 'Oui' : 'Non',
        prof.travailleImpaires ? 'Oui' : 'Non'
      ].concat(semaines.map(() => '')); // Colonnes semaines vides
      
      lignes.push(ligne);
    }
    
    // Assembler le CSV
    const csvContent = [
      headers.join(';'),
      ...lignes.map(ligne => ligne.join(';'))
    ].join('\n');
    
    return csvContent;
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h2>Saisie des données de planning</h2>
      <p className="text-muted">
        Créez votre planning en remplissant le formulaire ci-dessous, 
        puis générez automatiquement le planning optimisé.
      </p>

      {formData.message && (
        <Alert variant={formData.message.type === 'error' ? 'danger' : 'success'}>
          {formData.message.text}
        </Alert>
      )}

      {/* Configuration générale */}
      <Card className="mb-4">
        <Card.Header><h4>Configuration générale</h4></Card.Header>
        <Card.Body>
          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>Semaines (séparées par des virgules)</Form.Label>
                <Form.Control
                  type="text"
                  placeholder="ex: 38,39,40,41,42,45,46"
                  onChange={handleSemainesChange}
                />
                <Form.Text className="text-muted">
                  Numéros des semaines de l'année scolaire
                </Form.Text>
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>Nombre de groupes</Form.Label>
                <Form.Control
                  type="number"
                  value={formData.nombreGroupes}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    nombreGroupes: parseInt(e.target.value) || 15 
                  }))}
                  min="1"
                  max="30"
                />
              </Form.Group>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      {/* Professeurs */}
      <Card className="mb-4">
        <Card.Header>
          <div className="d-flex justify-content-between align-items-center">
            <h4>Professeurs ({formData.professeurs.length})</h4>
            <Button variant="success" size="sm" onClick={ajouterProfesseur}>
              + Ajouter un professeur
            </Button>
          </div>
        </Card.Header>
        <Card.Body>
          {formData.professeurs.length === 0 ? (
            <p className="text-muted">Aucun professeur ajouté</p>
          ) : (
            formData.professeurs.map((prof) => (
              <div key={prof.id} className="border p-3 mb-3 rounded">
                <Row>
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>Nom</Form.Label>
                      <Form.Control
                        type="text"
                        value={prof.nom}
                        onChange={(e) => modifierProfesseur(prof.id, 'nom', e.target.value)}
                        placeholder="Nom du professeur"
                      />
                    </Form.Group>
                  </Col>
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>Matières enseignées</Form.Label>
                      <div style={{ border: '1px solid #ced4da', borderRadius: '0.375rem', padding: '0.5rem', maxHeight: '120px', overflowY: 'auto' }}>
                        {matieresOptions.map(matiere => (
                          <Form.Check
                            key={matiere}
                            type="checkbox"
                            id={`prof-${prof.id}-${matiere}`}
                            label={matiere}
                            checked={prof.matieres.includes(matiere)}
                            onChange={(e) => {
                              const nouvellesmatieres = e.target.checked 
                                ? [...prof.matieres, matiere]
                                : prof.matieres.filter(m => m !== matiere);
                              modifierProfesseur(prof.id, 'matieres', nouvellesmatieres);
                            }}
                          />
                        ))}
                        {prof.matieres.length === 0 && (
                          <small className="text-muted">Aucune matière sélectionnée</small>
                        )}
                      </div>
                    </Form.Group>
                  </Col>
                  <Col md={2}>
                    <Form.Group>
                      <Form.Label>Semaines paires</Form.Label>
                      <Form.Check
                        type="checkbox"
                        checked={prof.travaillePaires}
                        onChange={(e) => modifierProfesseur(prof.id, 'travaillePaires', e.target.checked)}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={2}>
                    <Form.Group>
                      <Form.Label>Semaines impaires</Form.Label>
                      <Form.Check
                        type="checkbox"
                        checked={prof.travailleImpaires}
                        onChange={(e) => modifierProfesseur(prof.id, 'travailleImpaires', e.target.checked)}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={2}>
                    <Form.Group>
                      <Form.Label>&nbsp;</Form.Label>
                      <div>
                        <Button 
                          variant="danger" 
                          size="sm" 
                          onClick={() => supprimerProfesseur(prof.id)}
                        >
                          Supprimer
                        </Button>
                      </div>
                    </Form.Group>
                  </Col>
                </Row>
              </div>
            ))
          )}
        </Card.Body>
      </Card>

      {/* Créneaux */}
      <Card className="mb-4">
        <Card.Header>
          <div className="d-flex justify-content-between align-items-center">
            <h4>Créneaux ({formData.creneaux.length})</h4>
            <Button variant="success" size="sm" onClick={ajouterCreneau}>
              + Ajouter un créneau
            </Button>
          </div>
        </Card.Header>
        <Card.Body>
          {formData.creneaux.length === 0 ? (
            <p className="text-muted">Aucun créneau ajouté</p>
          ) : (
            formData.creneaux.map((creneau) => (
              <div key={creneau.id} className="border p-3 mb-3 rounded">
                <Row>
                  <Col md={2}>
                    <Form.Group>
                      <Form.Label>Matière</Form.Label>
                      <Form.Select
                        value={creneau.matiere}
                        onChange={(e) => modifierCreneau(creneau.id, 'matiere', e.target.value)}
                      >
                        <option value="">Choisir...</option>
                        {matieresOptions.map(matiere => (
                          <option key={matiere} value={matiere}>{matiere}</option>
                        ))}
                      </Form.Select>
                    </Form.Group>
                  </Col>
                  <Col md={2}>
                    <Form.Group>
                      <Form.Label>Professeur</Form.Label>
                      <Form.Select
                        value={creneau.professeur}
                        onChange={(e) => modifierCreneau(creneau.id, 'professeur', e.target.value)}
                      >
                        <option value="">Choisir...</option>
                        {formData.professeurs
                          .filter(prof => prof.matieres.includes(creneau.matiere))
                          .map(prof => (
                            <option key={prof.id} value={prof.nom}>{prof.nom}</option>
                          ))}
                      </Form.Select>
                    </Form.Group>
                  </Col>
                  <Col md={2}>
                    <Form.Group>
                      <Form.Label>Jour</Form.Label>
                      <Form.Select
                        value={creneau.jour}
                        onChange={(e) => modifierCreneau(creneau.id, 'jour', e.target.value)}
                      >
                        <option value="">Choisir...</option>
                        {joursOptions.map(jour => (
                          <option key={jour} value={jour}>{jour}</option>
                        ))}
                      </Form.Select>
                    </Form.Group>
                  </Col>
                  <Col md={2}>
                    <Form.Group>
                      <Form.Label>Heure</Form.Label>
                      <Form.Select
                        value={creneau.heure}
                        onChange={(e) => modifierCreneau(creneau.id, 'heure', e.target.value)}
                      >
                        <option value="">Choisir...</option>
                        {heuresOptions.map(heure => (
                          <option key={heure} value={heure}>{heure}</option>
                        ))}
                      </Form.Select>
                    </Form.Group>
                  </Col>
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>Groupes autorisés</Form.Label>
                      <div className="d-flex">
                        <Form.Control
                          type="number"
                          min="1"
                          max={formData.nombreGroupes}
                          value={creneau.groupesPaires.min}
                          onChange={(e) => modifierCreneau(creneau.id, 'groupesPaires', {
                            ...creneau.groupesPaires,
                            min: parseInt(e.target.value) || 1
                          })}
                          style={{ width: '60px' }}
                        />
                        <span className="mx-2 align-self-center">à</span>
                        <Form.Control
                          type="number"
                          min="1"
                          max={formData.nombreGroupes}
                          value={creneau.groupesPaires.max}
                          onChange={(e) => modifierCreneau(creneau.id, 'groupesPaires', {
                            ...creneau.groupesPaires,
                            max: parseInt(e.target.value) || 15
                          })}
                          style={{ width: '60px' }}
                        />
                      </div>
                    </Form.Group>
                  </Col>
                  <Col md={1}>
                    <Form.Group>
                      <Form.Label>&nbsp;</Form.Label>
                      <div>
                        <Button 
                          variant="danger" 
                          size="sm" 
                          onClick={() => supprimerCreneau(creneau.id)}
                        >
                          ✕
                        </Button>
                      </div>
                    </Form.Group>
                  </Col>
                </Row>
              </div>
            ))
          )}
        </Card.Body>
      </Card>

      {/* Boutons d'action */}
      <div className="text-center">
        <Button 
          variant="secondary" 
          size="lg" 
          onClick={exporterCSV}
          disabled={formData.loading}
          className="me-3"
        >
          📥 Télécharger le CSV d'entrée
        </Button>
        <Button 
          variant="primary" 
          size="lg" 
          onClick={genererPlanning}
          disabled={formData.loading}
        >
          {formData.loading ? 'Génération en cours...' : '🚀 Générer le planning'}
        </Button>
      </div>

      <div className="mt-3 text-center">
        <small className="text-muted">
          💡 <strong>Télécharger le CSV</strong> : Sauvegarde votre configuration pour la réutiliser plus tard<br/>
          💡 <strong>Générer le planning</strong> : Lance l'optimisation et crée le planning final
        </small>
      </div>
    </div>
  );
}