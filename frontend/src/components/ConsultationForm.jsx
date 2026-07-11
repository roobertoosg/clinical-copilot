import { useState } from 'react'

function ConsultationForm({ onProcess, loading, onPatientLookup }) {
  const [patientId, setPatientId] = useState(1)
  const [vitalSigns, setVitalSigns] = useState('')
  const [physicalExam, setPhysicalExam] = useState('')
  const [conversationText, setConversationText] = useState('')

  const handleSubmit = (event) => {
    event.preventDefault()
    onProcess({
      patient_id: patientId,
      conversation_text: conversationText,
      vital_signs: vitalSigns,
      physical_exam: physicalExam,
    })
  }

  const handleLookup = () => {
    onPatientLookup?.(patientId)
  }

  return (
    <form className="consultation-doc" onSubmit={handleSubmit}>
      <div className="doc-header">
        <h2 className="doc-title">Captura de consulta</h2>
        <p className="doc-subtitle">
          Registre los datos clínicos y procese con la IA.
        </p>
      </div>

      <div className="doc-field">
        <label htmlFor="patient_id">ID del paciente</label>
        <div className="patient-id-row">
          <input
            id="patient_id"
            type="number"
            min="1"
            value={patientId}
            onChange={(e) => setPatientId(Number(e.target.value))}
            onBlur={handleLookup}
          />
          <button
            type="button"
            className="lookup-button"
            onClick={handleLookup}
          >
            Buscar
          </button>
        </div>
      </div>

      <div className="doc-field">
        <label htmlFor="vital_signs">Signos vitales</label>
        <input
          id="vital_signs"
          type="text"
          placeholder="TA 120/80, FC 72, FR 16, Temp 36.5°C..."
          value={vitalSigns}
          onChange={(e) => setVitalSigns(e.target.value)}
        />
      </div>

      <div className="doc-field">
        <label htmlFor="physical_exam">Examen físico</label>
        <input
          id="physical_exam"
          type="text"
          placeholder="Hallazgos del examen físico..."
          value={physicalExam}
          onChange={(e) => setPhysicalExam(e.target.value)}
        />
      </div>

      <div className="doc-field doc-field--grow">
        <label htmlFor="conversation_text">Conversación / Notas</label>
        <textarea
          id="conversation_text"
          rows={12}
          placeholder="Transcripción de la consulta o notas clínicas..."
          value={conversationText}
          onChange={(e) => setConversationText(e.target.value)}
        />
      </div>

      <button type="submit" className="process-button" disabled={loading}>
        {loading ? 'Procesando…' : 'Procesar con IA'}
      </button>
    </form>
  )
}

export default ConsultationForm
