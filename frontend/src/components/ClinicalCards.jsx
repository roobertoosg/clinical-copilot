import {
  PATIENT_SUMMARY_FIELDS,
  normalizePatientSummary,
  patientSummaryHasContent,
} from '../utils/patientSummary'

const soapeFields = [
  { key: 'subjetivo', label: 'Subjetivo' },
  { key: 'objetivo', label: 'Objetivo' },
  { key: 'analisis', label: 'Análisis' },
  { key: 'plan', label: 'Plan' },
  { key: 'evaluacion', label: 'Evaluación' },
]

const severityModifier = (severidad) => {
  const value = (severidad || '').toString().trim().toLowerCase()
  if (value.startsWith('alt')) return 'alert-item--high'
  if (value.startsWith('baj')) return 'alert-item--low'
  return 'alert-item--medium'
}

/**
 * Tarjetas clínicas reutilizables (Workspace y detalle de consulta).
 * `data` acepta: { soape, diagnosticos_sugeridos, receta, alertas, resumen_paciente }
 */
function ClinicalCards({ data }) {
  if (!data) return null

  return (
    <div className="results-content">
      {data.alertas && data.alertas.length > 0 && (
        <div className="card card--alert">
          <h3 className="card-header">
            <span className="card-header-bar" aria-hidden="true" />
            ⚠️ Alertas Clínicas
          </h3>
          <div className="card-body">
            <ul className="alert-list">
              {data.alertas.map((alerta, index) => {
                const item =
                  typeof alerta === 'string' ? { descripcion: alerta } : alerta
                return (
                  <li
                    key={index}
                    className={`alert-item ${severityModifier(item.severidad)}`}
                  >
                    <div className="alert-item-head">
                      {item.tipo && <span className="alert-tag">{item.tipo}</span>}
                      {item.severidad && (
                        <span className="alert-severity">{item.severidad}</span>
                      )}
                    </div>
                    <p className="alert-desc">{item.descripcion}</p>
                  </li>
                )
              })}
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
                <p>{data.soape?.[key] || '—'}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {data.diagnosticos_sugeridos && (
        <div className="card card--diagnosis">
          <h3 className="card-header">
            <span className="card-header-bar" aria-hidden="true" />
            Diagnósticos
          </h3>
          <div className="card-body">
            {data.diagnosticos_sugeridos?.length > 0 ? (
              <ul className="diagnosis-list">
                {data.diagnosticos_sugeridos.map((dx, index) => (
                  <li key={index}>
                    {dx.codigo && (
                      <span className="diagnosis-code">{dx.codigo}</span>
                    )}
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
      )}

      <div className="card card--prescription">
        <h3 className="card-header">
          <span className="card-header-bar" aria-hidden="true" />
          Receta
        </h3>
        <div className="card-body">
          {data.receta?.length > 0 ? (
            <div className="prescription-table-wrap">
              <table className="prescription-table">
                <thead>
                  <tr>
                    <th>Denominación genérica</th>
                    <th>Dosis</th>
                    <th>Frecuencia</th>
                    <th>Duración</th>
                    <th>Indicaciones</th>
                  </tr>
                </thead>
                <tbody>
                  {data.receta.map((med, index) => (
                    <tr key={index}>
                      <td data-label="Denominación genérica" className="med-name">
                        {med.sustancia_activa || med.medicamento || '—'}
                        {med.sustancia_activa &&
                          med.medicamento &&
                          med.medicamento.toLowerCase() !==
                            med.sustancia_activa.toLowerCase() && (
                            <span className="med-commercial">
                              {med.medicamento}
                            </span>
                          )}
                      </td>
                      <td data-label="Dosis">{med.dosis || '—'}</td>
                      <td data-label="Frecuencia">{med.frecuencia || '—'}</td>
                      <td data-label="Duración">{med.duracion || '—'}</td>
                      <td data-label="Indicaciones">{med.indicaciones || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-text">Sin medicamentos sugeridos</p>
          )}
        </div>
      </div>

      {patientSummaryHasContent(data.resumen_paciente) && (
        <div className="card card--summary">
          <h3 className="card-header">
            <span className="card-header-bar" aria-hidden="true" />
            Indicaciones para el paciente
          </h3>
          <div className="card-body review-patient-summary">
            {PATIENT_SUMMARY_FIELDS.map(({ key, label }) => {
              const text = normalizePatientSummary(data.resumen_paciente)[key]
              if (!String(text || '').trim()) return null
              return (
                <div key={key} className="review-summary-field">
                  <span className="review-summary-label">{label}</span>
                  <p className="patient-summary">{text}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default ClinicalCards
