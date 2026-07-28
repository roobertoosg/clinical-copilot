import { useEffect, useId, useRef, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

const SOAPE_FIELDS = [
  { key: 'subjetivo', label: 'Subjetivo' },
  { key: 'objetivo', label: 'Objetivo' },
  { key: 'analisis', label: 'Análisis' },
  { key: 'plan', label: 'Plan' },
  { key: 'evaluacion', label: 'Evaluación' },
]

const RX_META_FIELDS = [
  { key: 'dosis', label: 'Dosis' },
  { key: 'frecuencia', label: 'Frecuencia' },
  { key: 'duracion', label: 'Duración' },
  { key: 'indicaciones', label: 'Indicaciones' },
]

const EMPTY_RX_ITEM = {
  medicamento: '',
  dosis: '',
  frecuencia: '',
  duracion: '',
  indicaciones: '',
}

function formatMedicationLabel(item) {
  if (!item) return ''
  if (item.medicamento) return item.medicamento
  const producto = item.producto || ''
  const marca = item.marca ? ` (${item.marca})` : ''
  return `${producto}${marca}`.trim()
}

function normalizeSuggestions(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.results)
      ? payload.results
      : []

  return list.map((item) => ({
    ...item,
    medicamento: formatMedicationLabel(item),
  }))
}

/**
 * Búsqueda difusa contra medications_catalog (PostgreSQL + pg_trgm).
 * GET /api/v1/medications/search?q={term}&limit=10
 */
async function searchMedications(term) {
  const q = term.trim()
  if (q.length < 2) return []

  const response = await fetch(
    `${API_BASE}/api/v1/medications/search?q=${encodeURIComponent(q)}&limit=10`
  )
  if (!response.ok) {
    throw new Error(`Búsqueda de medicamentos falló (${response.status})`)
  }
  return normalizeSuggestions(await response.json())
}

/**
 * Typeahead de medicamento: debounce 300 ms + dropdown flotante.
 */
function MedicationTypeahead({
  id,
  value,
  onSelect,
  onFreeTextChange,
}) {
  const [searchTerm, setSearchTerm] = useState(value || '')
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const skipSearchRef = useRef(false)
  const wrapperRef = useRef(null)
  const listId = useId()

  useEffect(() => {
    setSearchTerm(value || '')
  }, [value])

  useEffect(() => {
    if (skipSearchRef.current) {
      skipSearchRef.current = false
      return
    }

    const term = searchTerm.trim()
    if (term.length < 2) {
      setSuggestions([])
      setOpen(false)
      return
    }

    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const results = await searchMedications(term)
        setSuggestions(results)
        setOpen(results.length > 0)
      } catch {
        setSuggestions([])
        setOpen(false)
      } finally {
        setLoading(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [searchTerm])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleInputChange = (e) => {
    const next = e.target.value
    setSearchTerm(next)
    onFreeTextChange(next)
  }

  const handlePick = (item) => {
    const label = formatMedicationLabel(item)
    skipSearchRef.current = true
    setSearchTerm(label)
    setSuggestions([])
    setOpen(false)
    onSelect(label, item)
  }

  return (
    <div className="med-typeahead" ref={wrapperRef}>
      <input
        id={id}
        type="text"
        className="review-input"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        placeholder="Buscar medicamento…"
        value={searchTerm}
        onChange={handleInputChange}
        onFocus={() => {
          if (suggestions.length > 0) setOpen(true)
        }}
      />
      {loading && <span className="med-typeahead-status">Buscando…</span>}
      {open && suggestions.length > 0 && (
        <ul id={listId} className="med-typeahead-dropdown" role="listbox">
          {suggestions.map((item, idx) => (
            <li key={`${item.ean || item.medicamento}-${idx}`} role="option">
              <button
                type="button"
                className="med-typeahead-option"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handlePick(item)}
              >
                <span className="med-typeahead-name">{item.medicamento}</span>
                {(item.sustancia_activa || item.laboratorio) && (
                  <span className="med-typeahead-meta">
                    {[item.sustancia_activa, item.laboratorio]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Vista Human-in-the-Loop: el médico edita el borrador de la IA
 * (SOAPE + receta) antes de finalizar la consulta.
 */
function ClinicalReviewEditor({
  data,
  onChange,
  onFinalize,
  finalizing = false,
}) {
  if (!data) return null

  const receta = Array.isArray(data.receta) ? data.receta : []

  const updateSoape = (key, value) => {
    onChange({
      ...data,
      soape: {
        ...(data.soape || {}),
        [key]: value,
      },
    })
  }

  const updateResumen = (value) => {
    onChange({ ...data, resumen_paciente: value })
  }

  const updateRecetaField = (index, field, value) => {
    const next = receta.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    )
    onChange({ ...data, receta: next })
  }

  const addMedicamento = () => {
    onChange({ ...data, receta: [...receta, { ...EMPTY_RX_ITEM }] })
  }

  const removeMedicamento = (index) => {
    onChange({
      ...data,
      receta: receta.filter((_, i) => i !== index),
    })
  }

  return (
    <div className="results-content review-editor">
      <div className="review-banner">
        <strong>Revisión médica</strong>
        <span>
          Edite el borrador de la IA. Al finalizar se calculará la precisión y se
          generará el PDF.
        </span>
      </div>

      {data.alertas?.length > 0 && (
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
                  <li key={index} className="alert-item alert-item--medium">
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
          SOAPE (editable)
        </h3>
        <div className="card-body">
          <div className="soape-grid soape-grid--editable">
            {SOAPE_FIELDS.map(({ key, label }) => (
              <div key={key} className="soape-item soape-item--editable">
                <label htmlFor={`review-soape-${key}`}>{label}</label>
                <textarea
                  id={`review-soape-${key}`}
                  className="review-textarea"
                  rows={key === 'plan' || key === 'subjetivo' ? 4 : 3}
                  value={data.soape?.[key] || ''}
                  onChange={(e) => updateSoape(key, e.target.value)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {data.diagnosticos_sugeridos && (
        <div className="card card--diagnosis">
          <h3 className="card-header">
            <span className="card-header-bar" aria-hidden="true" />
            Diagnósticos (CIE-11)
          </h3>
          <div className="card-body">
            {data.diagnosticos_sugeridos.length > 0 ? (
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
          Receta (editable)
        </h3>
        <div className="card-body">
          {receta.length > 0 ? (
            <div className="review-rx-list">
              {receta.map((med, index) => (
                <div key={index} className="review-rx-card">
                  <div className="review-rx-card-head">
                    <span className="review-rx-index">#{index + 1}</span>
                    <button
                      type="button"
                      className="review-rx-remove"
                      title="Eliminar medicamento"
                      aria-label={`Eliminar medicamento ${index + 1}`}
                      onClick={() => removeMedicamento(index)}
                    >
                      <Trash2 size={16} strokeWidth={2} />
                    </button>
                  </div>

                  <div className="review-rx-field review-rx-field--medication">
                    <label htmlFor={`rx-${index}-medicamento`}>Medicamento</label>
                    <MedicationTypeahead
                      id={`rx-${index}-medicamento`}
                      value={med?.medicamento || ''}
                      onFreeTextChange={(text) =>
                        updateRecetaField(index, 'medicamento', text)
                      }
                      onSelect={(label) =>
                        updateRecetaField(index, 'medicamento', label)
                      }
                    />
                  </div>

                  {RX_META_FIELDS.map(({ key, label }) => (
                    <div key={key} className="review-rx-field">
                      <label htmlFor={`rx-${index}-${key}`}>{label}</label>
                      <input
                        id={`rx-${index}-${key}`}
                        type="text"
                        className="review-input"
                        value={med?.[key] || ''}
                        onChange={(e) =>
                          updateRecetaField(index, key, e.target.value)
                        }
                      />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">Sin medicamentos en la receta</p>
          )}

          <button
            type="button"
            className="secondary-button secondary-button--sm review-rx-add"
            onClick={addMedicamento}
          >
            <Plus size={16} strokeWidth={2.5} aria-hidden="true" />
            Añadir medicamento
          </button>
        </div>
      </div>

      <div className="card card--summary">
        <h3 className="card-header">
          <span className="card-header-bar" aria-hidden="true" />
          Resumen para el paciente
        </h3>
        <div className="card-body">
          <textarea
            className="review-textarea"
            rows={3}
            value={data.resumen_paciente || ''}
            onChange={(e) => updateResumen(e.target.value)}
          />
        </div>
      </div>

      <button
        type="button"
        className="process-button review-finalize-button"
        onClick={onFinalize}
        disabled={finalizing}
      >
        {finalizing
          ? 'Finalizando y generando PDF…'
          : 'Finalizar Consulta y Generar PDF'}
      </button>
    </div>
  )
}

export default ClinicalReviewEditor
