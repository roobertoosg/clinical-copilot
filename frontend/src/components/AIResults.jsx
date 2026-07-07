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

function AIResults({ aiResponse, loading }) {
  return (
    <div className="ai-results">
      <div className="column-header">
        <span className="column-header-accent" aria-hidden="true" />
        <h2 className="section-title">Resultados de IA</h2>
      </div>

      <div className="ai-results-body">
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
                    {aiResponse.alertas.map((alerta, index) => {
                      const item =
                        typeof alerta === 'string'
                          ? { descripcion: alerta }
                          : alerta
                      return (
                        <li
                          key={index}
                          className={`alert-item ${severityModifier(item.severidad)}`}
                        >
                          <div className="alert-item-head">
                            {item.tipo && (
                              <span className="alert-tag">{item.tipo}</span>
                            )}
                            {item.severidad && (
                              <span className="alert-severity">
                                {item.severidad}
                              </span>
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
                          <span className="diagnosis-prob">
                            {dx.probabilidad}
                          </span>
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
                {aiResponse.receta?.length > 0 ? (
                  <div className="prescription-table-wrap">
                    <table className="prescription-table">
                      <thead>
                        <tr>
                          <th>Medicamento</th>
                          <th>Dosis</th>
                          <th>Frecuencia</th>
                          <th>Duración</th>
                          <th>Indicaciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {aiResponse.receta.map((med, index) => (
                          <tr key={index}>
                            <td data-label="Medicamento" className="med-name">
                              {med.medicamento || '—'}
                            </td>
                            <td data-label="Dosis">{med.dosis || '—'}</td>
                            <td data-label="Frecuencia">
                              {med.frecuencia || '—'}
                            </td>
                            <td data-label="Duración">{med.duracion || '—'}</td>
                            <td data-label="Indicaciones">
                              {med.indicaciones || '—'}
                            </td>
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
            <p>
              Complete el formulario y procese la consulta para ver los
              resultados.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default AIResults
