import { useCallback, useEffect, useState } from 'react'
import {
  downloadClinicalNotePdf,
  downloadPrescriptionPdf,
} from '../utils/exportPdf'
import { API_BASE } from '../config'

const typeMeta = {
  patient: { icon: '☺', label: 'Paciente', className: 'timeline-marker--patient' },
  consultation: {
    icon: '✚',
    label: 'Consulta',
    className: 'timeline-marker--consultation',
  },
  medication: {
    icon: '⏸',
    label: 'Medicamento',
    className: 'timeline-marker--medication',
  },
}

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString('es-MX', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function HistoryPage() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [exportingKey, setExportingKey] = useState(null)

  const handleExport = async (folio, kind) => {
    if (!folio) return
    const key = `${folio}:${kind}`
    setExportingKey(key)
    try {
      if (kind === 'nota') {
        await downloadClinicalNotePdf(folio)
      } else {
        await downloadPrescriptionPdf(folio)
      }
    } catch (err) {
      alert(`No se pudo exportar el PDF: ${err.message}`)
    } finally {
      setExportingKey(null)
    }
  }

  const fetchLog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/system/activity-log`)
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }
      const data = await response.json()
      setEvents(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLog()
  }, [fetchLog])

  return (
    <div className="patients-page patients-page--wide">
      <div className="page-header">
        <div>
          <h1 className="page-title">Historial de Actividad</h1>
          <p className="page-subtitle">
            Bitácora de eventos del sistema del día de hoy.
          </p>
        </div>
        <button
          type="button"
          className="finish-button"
          onClick={fetchLog}
          disabled={loading}
        >
          {loading ? 'Actualizando…' : '↺ Actualizar'}
        </button>
      </div>

      {error && <div className="form-feedback form-feedback--error">{error}</div>}

      {!loading && events.length > 0 && (
        <div className="timeline">
          {events.map((ev, index) => {
            const meta = typeMeta[ev.type] || {
              icon: '•',
              label: 'Evento',
              className: '',
            }
            return (
              <div key={index} className="timeline-item">
                <div
                  className={`timeline-marker timeline-marker--icon ${meta.className}`}
                  aria-hidden="true"
                >
                  {meta.icon}
                </div>
                <div className="timeline-card">
                  <div className="timeline-card-head">
                    <span className="timeline-date">
                      Hoy a las {formatTime(ev.timestamp)}
                    </span>
                    <span className="timeline-badge">{meta.label}</span>
                    {ev.reference && (
                      <span className="timeline-status">{ev.reference}</span>
                    )}
                  </div>
                  <p className="timeline-reason">{ev.message}</p>
                  {ev.type === 'consultation' && ev.reference && (
                    <div className="timeline-export-actions">
                      <button
                        type="button"
                        className="secondary-button secondary-button--sm export-pdf-button"
                        onClick={() => handleExport(ev.reference, 'nota')}
                        disabled={Boolean(exportingKey)}
                      >
                        {exportingKey === `${ev.reference}:nota`
                          ? 'Generando…'
                          : '⭳ Nota clínica'}
                      </button>
                      <button
                        type="button"
                        className="secondary-button secondary-button--sm export-pdf-button"
                        onClick={() => handleExport(ev.reference, 'receta')}
                        disabled={Boolean(exportingKey)}
                      >
                        {exportingKey === `${ev.reference}:receta`
                          ? 'Generando…'
                          : '⭳ Receta'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {!loading && events.length === 0 && !error && (
        <div className="empty-results">
          <div className="empty-icon" aria-hidden="true" />
          <p>No hay actividad registrada hoy.</p>
        </div>
      )}
    </div>
  )
}

export default HistoryPage
