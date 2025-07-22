import React, { useRef } from 'react';
import Form from 'react-bootstrap/Form';

function FileUpload({ setPreview, setStatus }) {
  const fileInput = useRef();

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setStatus({ type: 'info', text: 'Chargement du fichier...' });
    const formData = new FormData();
    formData.append('file', file);

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
      setStatus({ type: 'error', text: "Erreur lors de l'import. Vérifiez que le backend tourne." });
    }
  };

  return (
    <div>
      <h2>Importer un fichier de créneaux (.csv)</h2>
      <Form.Group controlId="formFile" className="mb-3">
        <Form.Label>Default file input example</Form.Label>
        <Form.Control type="file" accept=".csv" onChange={handleUpload} />
      </Form.Group>
    </div>
  );
}

export default FileUpload;
