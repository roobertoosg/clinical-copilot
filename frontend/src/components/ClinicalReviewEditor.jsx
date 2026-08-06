import { useEffect, useId, useRef, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { API_BASE } from '../config'
import {
  PATIENT_SUMMARY_FIELDS,
  normalizePatientSummary,
} from '../utils/patientSummary'

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
  sustancia_activa: '',
  medicamento: '',
  dosis: '',
  frecuencia: '',
  duracion: '',
  indicaciones: '',
}

/** Compacta espacios y recorta extremos (sin tocar mayúsculas). */
function collapseWhitespace(value) {
  return String(value ?? '')
    .trim()
    .replace(/\s+/g, ' ')
}

/**
 * Sentence case: solo la primera letra de la oración en mayúscula.
 * Ej: "CADA 8 HORAS" → "Cada 8 horas"
 */
function toSentenceCase(value) {
  const text = collapseWhitespace(value)
  if (!text) return ''
  const lower = text.toLocaleLowerCase('es')
  return lower.charAt(0).toLocaleUpperCase('es') + lower.slice(1)
}

/**
 * Minúsculas estrictas para dosis / duración.
 * Ej: "500 MG" → "500 mg", "7 DÍAS" → "7 días"
 */
function toStrictLowercase(value) {
  const text = collapseWhitespace(value)
  if (!text) return ''
  return text.toLocaleLowerCase('es')
}

/** Normalizadores onBlur por campo (medicamento nunca se normaliza). */
const RX_FIELD_NORMALIZERS = {
  sustancia_activa: toSentenceCase,
  dosis: toStrictLowercase,
  duracion: toStrictLowercase,
  frecuencia: toSentenceCase,
  indicaciones: toSentenceCase,
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

async function searchIcd11(term) {
  const q = term.trim()
  if (q.length < 2) return []

  const response = await fetch(
    `${API_BASE}/clinical-ai/icd11/search?q=${encodeURIComponent(q)}&limit=10`
  )
  if (!response.ok) {
    throw new Error(`Búsqueda CIE-11 falló (${response.status})`)
  }
  const payload = await response.json()
  return Array.isArray(payload?.results) ? payload.results : []
}

const DX_PROBABILITIES = ['Alta', 'Media', 'Baja']

/**
 * Typeahead CIE-11: debounce 300 ms + dropdown flotante.
 */
function Icd11Typeahead({ onSelect }) {
  const inputId = useId()
  const [searchTerm, setSearchTerm] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const wrapperRef = useRef(null)

  useEffect(() => {
    const onDocClick = (event) => {
      if (!wrapperRef.current?.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  useEffect(() => {
    const q = searchTerm.trim()
    if (q.length < 2) {
      setSuggestions([])
      setOpen(false)
      setLoading(false)
      return undefined
    }

    let cancelled = false
    setLoading(true)
    const timer = setTimeout(async () => {
      try {
        const results = await searchIcd11(q)
        if (!cancelled) {
          setSuggestions(results)
          setOpen(true)
        }
      } catch {
        if (!cancelled) {
          setSuggestions([])
          setOpen(false)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [searchTerm])

  const handlePick = (item) => {
    onSelect(item)
    setSearchTerm('')
    setSuggestions([])
    setOpen(false)
  }

  return (
    <div className="med-typeahead review-dx-typeahead" ref={wrapperRef}>
      <label className="visually-hidden" htmlFor={inputId}>
        Buscar diagnóstico CIE-11
      </label>
      <input
        id={inputId}
        type="text"
        className="review-input"
        placeholder="Buscar en CIE-11 (ej. Salmonelosis)…"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        onFocus={() => {
          if (suggestions.length > 0) setOpen(true)
        }}
        autoComplete="off"
      />
      {loading && <span className="med-typeahead-status">Buscando…</span>}
      {open && suggestions.length > 0 && (
        <ul className="med-typeahead-dropdown" role="listbox">
          {suggestions.map((item, idx) => (
            <li key={`${item.codigo}-${idx}`} role="option">
              <button
                type="button"
                className="med-typeahead-option review-dx-option"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handlePick(item)}
              >
                <span className="diagnosis-code">{item.codigo || '—'}</span>
                <span className="med-typeahead-name">{item.descripcion}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
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

  const resumen = normalizePatientSummary(data.resumen_paciente)

  const diagnosticos = Array.isArray(data.diagnosticos_sugeridos)
    ? data.diagnosticos_sugeridos
    : []

  const updateDiagnosticoField = (index, field, value) => {
    const next = diagnosticos.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    )
    onChange({ ...data, diagnosticos_sugeridos: next })
  }

  const removeDiagnostico = (index) => {
    onChange({
      ...data,
      diagnosticos_sugeridos: diagnosticos.filter((_, i) => i !== index),
    })
  }

  const addDiagnostico = (item) => {
    const codigo = (item?.codigo || '').trim()
    const descripcion = (item?.descripcion || '').trim()
    if (!descripcion) return

    const already = diagnosticos.some(
      (dx) =>
        (dx.codigo || '') === codigo &&
        (dx.descripcion || '').toLowerCase() === descripcion.toLowerCase()
    )
    if (already) return

    onChange({
      ...data,
      diagnosticos_sugeridos: [
        ...diagnosticos,
        {
          codigo: codigo || '[Sin Código]',
          descripcion,
          probabilidad: 'Media',
        },
      ],
    })
  }

  const updateResumenField = (key, value) => {
    onChange({
      ...data,
      resumen_paciente: {
        ...resumen,
        [key]: value,
      },
    })
  }

  const updateRecetaField = (index, field, value) => {
    const next = receta.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    )
    onChange({ ...data, receta: next })
  }

  const normalizeRecetaFieldOnBlur = (index, field, rawValue) => {
    const normalize = RX_FIELD_NORMALIZERS[field]
    if (!normalize) return
    const normalized = normalize(rawValue)
    const current = receta[index]?.[field] || ''
    if (normalized === current) return
    updateRecetaField(index, field, normalized)
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
          generarán la nota clínica y la receta (PDFs separados).
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

      <div className="card card--diagnosis">
        <h3 className="card-header">
          <span className="card-header-bar" aria-hidden="true" />
          Diagnósticos CIE-11 (editable)
        </h3>
        <div className="card-body">
          {diagnosticos.length > 0 ? (
            <ul className="diagnosis-list">
              {diagnosticos.map((dx, index) => (
                <li key={`${dx.codigo || 'dx'}-${index}`} className="review-dx-row">
                  {dx.codigo && (
                    <span className="diagnosis-code">{dx.codigo}</span>
                  )}
                  <span className="diagnosis-desc">{dx.descripcion}</span>
                  <label className="review-dx-prob">
                    <span className="visually-hidden">Probabilidad</span>
                    <select
                      className="review-input review-dx-prob-select"
                      value={dx.probabilidad || 'Media'}
                      onChange={(e) =>
                        updateDiagnosticoField(
                          index,
                          'probabilidad',
                          e.target.value
                        )
                      }
                    >
                      {DX_PROBABILITIES.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="review-rx-remove"
                    title="Eliminar diagnóstico"
                    aria-label={`Eliminar diagnóstico ${index + 1}`}
                    onClick={() => removeDiagnostico(index)}
                  >
                    <Trash2 size={16} strokeWidth={2} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-text">Sin diagnósticos. Añada uno desde CIE-11.</p>
          )}

          <div className="review-dx-add">
            <p className="review-dx-add-label">Añadir diagnóstico</p>
            <Icd11Typeahead onSelect={addDiagnostico} />
          </div>
        </div>
      </div>

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
                    <label htmlFor={`rx-${index}-sustancia`}>
                      Denominación genérica (sustancia activa)
                    </label>
                    <input
                      id={`rx-${index}-sustancia`}
                      type="text"
                      className="review-input"
                      placeholder="Ej. Paracetamol"
                      value={med?.sustancia_activa || ''}
                      onChange={(e) =>
                        updateRecetaField(index, 'sustancia_activa', e.target.value)
                      }
                      onBlur={(e) =>
                        normalizeRecetaFieldOnBlur(
                          index,
                          'sustancia_activa',
                          e.target.value
                        )
                      }
                    />
                  </div>

                  <div className="review-rx-field review-rx-field--medication">
                    <label htmlFor={`rx-${index}-medicamento`}>
                      Nombre comercial (catálogo)
                    </label>
                    <MedicationTypeahead
                      id={`rx-${index}-medicamento`}
                      value={med?.medicamento || ''}
                      onFreeTextChange={(text) =>
                        updateRecetaField(index, 'medicamento', text)
                      }
                      onSelect={(label, item) => {
                        const sustancia = (item?.sustancia_activa || '').trim()
                        const next = receta.map((rx, i) =>
                          i === index
                            ? {
                                ...rx,
                                medicamento: label,
                                sustancia_activa: sustancia
                                  ? toSentenceCase(sustancia)
                                  : rx.sustancia_activa || '',
                              }
                            : rx
                        )
                        onChange({ ...data, receta: next })
                      }}
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
                        onBlur={(e) =>
                          normalizeRecetaFieldOnBlur(index, key, e.target.value)
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
          Indicaciones para el paciente
        </h3>
        <div className="card-body review-patient-summary">
          {PATIENT_SUMMARY_FIELDS.map(({ key, label, hint }) => (
            <label key={key} className="review-summary-field">
              <span className="review-summary-label">{label}</span>
              {hint && <span className="review-summary-hint">{hint}</span>}
              <textarea
                className="review-textarea"
                rows={2}
                value={resumen[key] || ''}
                onChange={(e) => updateResumenField(key, e.target.value)}
              />
            </label>
          ))}
        </div>
      </div>

      <button
        type="button"
        className="process-button review-finalize-button"
        onClick={onFinalize}
        disabled={finalizing}
      >
        {finalizing
          ? 'Finalizando y generando PDFs…'
          : 'Finalizar Consulta y Generar PDFs'}
      </button>
    </div>
  )
}

export default ClinicalReviewEditor
