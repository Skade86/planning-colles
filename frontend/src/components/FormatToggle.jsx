// src/components/FormatToggle.js
import React from 'react';
import Form from 'react-bootstrap/Form';

export default function FormatToggle({ format, setFormat }) {
  const checked = format === 'excel';
  return (
    <Form.Check
      type="checkbox"
      id="format-excel-toggle"
      label="Télécharger en Excel (.xlsx)"
      checked={checked}
      onChange={(e) => setFormat(e.target.checked ? 'excel' : 'csv')}
    />
  );
}