import React, { useRef, useState } from 'react';
import Form from 'react-bootstrap/Form';
import Card from 'react-bootstrap/Card';
import Button from 'react-bootstrap/Button';

function FileUpload({ setPreview, setStatus }) {
  const fileInput = useRef();
  const [fileSelected, setFileSelected] = useState(false);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) {
      setFileSelected(false);
      return;
    }
    setStatus({ type: 'info', text: 'Chargement du fichier...' });
    const formData = new FormData();
    formData.append('file', file);
    setFileSelected(true);

    try {
      const res = await fetch('http://localhost:8000/api/upload_csv', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Erreur réseau');
      const data = await res.json();
      setPreview(data);
      setStatus({ type: 'success', text: 'Fichier importé avec succès !' });
    } catch (error) {
      setStatus({
        type: 'error',
        text: "Erreur lors de l'import. Vérifiez que le backend tourne (http://localhost:8000)."
      });
    }
  };

  return (
    <div>
      <h2>Importer un fichier de créneaux (.csv)</h2>

      {/* Belle carte Bootstrap avec exemple CSV */}
      <Card className="mb-4 shadow-sm">
        <Card.Header as="h5">Exemple de fichier attendu</Card.Header>
        <Card.Body>
          <Card.Text>
            Votre fichier CSV doit contenir ces colonnes :
            <b> Matière, Prof, Jour, Heure, Groupes possibles, ...</b>
          </Card.Text>
          <img
            src="/csv_example.png"
            alt="Exemple de CSV attendu"
            style={{ border: "1px solid #ccc", maxWidth: "100%", borderRadius: 4 }}
          />
        </Card.Body>
      </Card>

      {/* Formulaire d'upload avec Bootstrap */}
      <Form.Group controlId="formFile" className="mb-3">
        <Form.Label>Sélectionnez votre fichier CSV :</Form.Label>
        <Form.Control
          type="file"
          accept=".csv"
          onChange={handleUpload}
          ref={fileInput}
          style={{ display: "none" }}
        />
      </Form.Group>

      {/* Bouton clair et visible */}
      <Button
        variant="primary"
        onClick={() => fileInput.current?.click()}
      >
        Choisir un fichier
      </Button>
    </div>
  );
}

export default FileUpload;
