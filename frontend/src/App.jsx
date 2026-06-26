import { useState } from 'react'
import './App.css'

function App() {
  const [patient_id, setPatientId] = useState(1)
  const [conversation_text, setConversationText] = useState('')
  const [vital_signs, setVitalSigns] = useState('')
  const [physical_exam, setPhysicalExam] = useState('')
  const [loading, setLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState(null)

  const handleProcessConsultation = async () => {
    setLoading(true)
    setAiResponse(null)

    try {
      const response = await fetch(
        'http://localhost:8000/clinical-ai/process-consultation',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            patient_id,
            conversation_text,
            vital_signs,
            physical_exam,
          }),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setAiResponse(data)
    } catch (error) {
      alert(`Error al procesar la consulta: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const soapeFields = [
    { key: 'subjetivo', label: 'Subjetivo' },
    { key: 'objetivo', label: 'Objetivo' },
    { key: 'analisis', label: 'Análisis' },
    { key: 'plan', label: 'Plan' },
    { key: 'evaluacion', label: 'Evaluación' },
  ]

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-content">
          <div className="header-brand">
            <div className="brand-icon" aria-hidden="true" />
            <div>
              <h1>Clinical Copilot</h1>
              <p className="subtitle">Asistente clínico inteligente</p>
            </div>
          </div>
          <span className="header-badge">
            <span className="header-badge-dot" aria-hidden="true" />
            IA activa
          </span>
        </div>
      </header>

      <div className="dashboard-layout">
        <section className="form-column">
          <div className="column-header">
            <span className="column-header-accent" aria-hidden="true" />
            <h2 className="section-title">Consulta clínica</h2>
          </div>

          <div className="column-body">
            <div className="form-group">
              <label htmlFor="patient_id">ID del paciente</label>
              <input
                id="patient_id"
                type="number"
                min="1"
                value={patient_id}
                onChange={(e) => setPatientId(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="vital_signs">Signos vitales</label>
              <input
                id="vital_signs"
                type="text"
                placeholder="TA 120/80, FC 72, FR 16, Temp 36.5°C..."
                value={vital_signs}
                onChange={(e) => setVitalSigns(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="physical_exam">Examen físico</label>
              <input
                id="physical_exam"
                type="text"
                placeholder="Hallazgos del examen físico..."
                value={physical_exam}
                onChange={(e) => setPhysicalExam(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="conversation_text">Conversación / Notas</label>
              <textarea
                id="conversation_text"
                rows={10}
                placeholder="Transcripción de la consulta o notas clínicas..."
                value={conversation_text}
                onChange={(e) => setConversationText(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="process-button"
              onClick={handleProcessConsultation}
              disabled={loading}
            >
              {loading ? 'Procesando…' : 'Procesar con IA'}
            </button>
          </div>
        </section>

        <section className="results-column">
          <div className="column-header">
            <span className="column-header-accent" aria-hidden="true" />
            <h2 className="section-title">Resultados</h2>
          </div>

          <div className="column-body">
            {loading && (
              <div className="loading-message">
                <span className="loading-spinner" aria-hidden="true" />
                <p>La IA está analizando el caso clínico...</p>
              </div>
            )}

            {!loading && aiResponse && (
              <div className="results-content">
                {aiResponse.alertas && aiResponse.alertas.length > 0 && (
                  <div className="card card--alert">
                    <h3 className="card-header">
                      <span className="card-header-bar" aria-hidden="true" />
                      ⚠️ Alertas Clínicas
                    </h3>
                    <div className="card-body">
                      <ul className="alert-list">
                        {aiResponse.alertas.map((alerta, index) => (
                          <li key={index}>{alerta}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                <div className="card card--soape">
                  <h3 className="card-header">
                    <span className="card-header-bar" aria-hidden="true" />
                    SOAPE
                  </h3>
                  <div className="card-body">
                    <div className="soape-grid">
                      {soapeFields.map(({ key, label }) => (
                        <div key={key} className="soape-item">
                          <h4>{label}</h4>
                          <p>{aiResponse.soape?.[key] || '—'}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card card--diagnosis">
                  <h3 className="card-header">
                    <span className="card-header-bar" aria-hidden="true" />
                    Diagnósticos
                  </h3>
                  <div className="card-body">
                    {aiResponse.diagnosticos_sugeridos?.length > 0 ? (
                      <ul className="diagnosis-list">
                        {aiResponse.diagnosticos_sugeridos.map((dx, index) => (
                          <li key={index}>
                            <span className="diagnosis-code">{dx.codigo}</span>
                            <span className="diagnosis-desc">{dx.descripcion}</span>
                            {dx.probabilidad && (
                              <span className="diagnosis-prob">{dx.probabilidad}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="empty-text">Sin diagnósticos sugeridos</p>
                    )}
                  </div>
                </div>

                <div className="card card--prescription">
                  <h3 className="card-header">
                    <span className="card-header-bar" aria-hidden="true" />
                    Receta
                  </h3>
                  <div className="card-body">
                    {aiResponse.receta_borrador?.length > 0 ? (
                      <ul className="medication-list">
                        {aiResponse.receta_borrador.map((med, index) => (
                          <li key={index}>{med}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="empty-text">Sin medicamentos sugeridos</p>
                    )}
                  </div>
                </div>

                <div className="card card--summary">
                  <h3 className="card-header">
                    <span className="card-header-bar" aria-hidden="true" />
                    Resumen para el paciente
                  </h3>
                  <div className="card-body">
                    <p className="patient-summary">
                      {aiResponse.resumen_paciente || '—'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {!loading && !aiResponse && (
              <div className="empty-results">
                <div className="empty-icon" aria-hidden="true" />
                <p>Complete el formulario y procese la consulta para ver los resultados.</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

export default App
