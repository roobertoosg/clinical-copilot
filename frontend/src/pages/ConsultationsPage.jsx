import { useEffect, useState } from 'react'
import ClinicalCards from '../components/ClinicalCards'
import { downloadConsultationPdf } from '../utils/exportPdf'
import { API_BASE } from '../config'

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('es-MX', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ConsultationsPage() {
  const [consultations, setConsultations] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    const fetchList = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch(`${API_BASE}/clinical-ai/consultations`)
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `Error ${response.status}`)
        }
        setConsultations(await response.json())
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchList()
  }, [])

  const openDetail = async (folio) => {
    setModalOpen(true)
    setDetailLoading(true)
    setDetail(null)
    try {
      const response = await fetch(
        `${API_BASE}/clinical-ai/consultations/${folio}`
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }
      setDetail(await response.json())
    } catch (err) {
      alert(`No se pudo cargar el detalle: ${err.message}`)
      setModalOpen(false)
    } finally {
      setDetailLoading(false)
    }
  }

  const closeModal = () => {
    setModalOpen(false)
    setDetail(null)
  }

  const handleExport = async () => {
    if (!detail?.folio) return
    setExporting(true)
    try {
      await downloadConsultationPdf(detail.folio)
    } catch (err) {
      alert(`No se pudo exportar el PDF: ${err.message}`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="patients-page patients-page--wide">
      <div className="page-header">
        <div>
          <h1 className="page-title">Consultas</h1>
          <p className="page-subtitle">
            Expediente clínico de todas las consultas procesadas.
          </p>
        </div>
      </div>

      {error && <div className="form-feedback form-feedback--error">{error}</div>}

      {loading && (
        <div className="loading-message">
          <span className="loading-spinner" aria-hidden="true" />
          <p>Cargando consultas…</p>
        </div>
      )}

      {!loading && consultations.length > 0 && (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Folio</th>
                <th>Fecha</th>
                <th>Paciente</th>
                <th className="data-table-actions">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {consultations.map((c) => (
                <tr key={c.id}>
                  <td data-label="Folio" className="folio-cell">
                    {c.folio || `#${c.id}`}
                  </td>
                  <td data-label="Fecha">{formatDate(c.date)}</td>
                  <td data-label="Paciente">{c.patient_name}</td>
                  <td data-label="Detalle" className="data-table-actions">
                    <button
                      type="button"
                      className="secondary-button secondary-button--sm"
                      onClick={() => openDetail(c.folio)}
                      disabled={!c.folio}
                    >
                      Ver Detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && consultations.length === 0 && !error && (
        <div className="empty-results">
          <div className="empty-icon" aria-hidden="true" />
          <p>Aún no hay consultas registradas.</p>
        </div>
      )}

      {modalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2 className="modal-title">
                  {detail ? detail.folio || `Consulta #${detail.id}` : 'Detalle'}
                </h2>
                {detail && (
                  <p className="modal-subtitle">
                    {detail.patient_name} · {formatDate(detail.date)}
                  </p>
                )}
              </div>
              <div className="modal-header-actions">
                {detail && detail.folio && (
                  <button
                    type="button"
                    className="secondary-button secondary-button--sm export-pdf-button"
                    onClick={handleExport}
                    disabled={exporting}
                  >
                    {exporting ? 'Generando…' : '⭳ Exportar PDF'}
                  </button>
                )}
                <button
                  type="button"
                  className="modal-close"
                  onClick={closeModal}
                  aria-label="Cerrar"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="modal-body">
              {detailLoading && (
                <div className="loading-message">
                  <span className="loading-spinner" aria-hidden="true" />
                  <p>Cargando detalle…</p>
                </div>
              )}
              {!detailLoading && detail && <ClinicalCards data={detail} />}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ConsultationsPage
