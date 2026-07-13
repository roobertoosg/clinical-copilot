import { useState } from 'react'
import ClinicalCards from './ClinicalCards'
import { downloadConsultationPdf } from '../utils/exportPdf'

function AIResults({ aiResponse, loading }) {
  const [exporting, setExporting] = useState(false)
  const folio = aiResponse?.folio

  const handleExport = async () => {
    setExporting(true)
    try {
      await downloadConsultationPdf(folio)
    } catch (error) {
      alert(`No se pudo exportar el PDF: ${error.message}`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="ai-results">
      <div className="column-header">
        <span className="column-header-accent" aria-hidden="true" />
        <h2 className="section-title">Resultados de IA</h2>
        {!loading && folio && (
          <button
            type="button"
            className="secondary-button secondary-button--sm export-pdf-button"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? 'Generando…' : '⭳ Exportar PDF'}
          </button>
        )}
      </div>

      <div className="ai-results-body">
        {loading && (
          <div className="loading-message">
            <span className="loading-spinner" aria-hidden="true" />
            <p>La IA está analizando el caso clínico...</p>
          </div>
        )}

        {!loading && aiResponse && <ClinicalCards data={aiResponse} />}

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
