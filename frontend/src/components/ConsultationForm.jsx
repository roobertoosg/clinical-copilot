import { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'

function ConsultationForm({ onProcess, loading, onPatientLookup }) {
  const [patientId, setPatientId] = useState(null)
  const [search, setSearch] = useState('')
  const [results, setResults] = useState([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [searching, setSearching] = useState(false)

  const [vitalSigns, setVitalSigns] = useState('')
  const [physicalExam, setPhysicalExam] = useState('')
  const [conversationText, setConversationText] = useState('')

  // Evita relanzar la búsqueda inmediatamente después de elegir un paciente
  const skipSearchRef = useRef(false)
  const wrapperRef = useRef(null)

  useEffect(() => {
    if (skipSearchRef.current) {
      skipSearchRef.current = false
      return
    }
    const term = search.trim()
    if (!term) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const response = await fetch(
          `${API_BASE}/patients/?search=${encodeURIComponent(term)}`
        )
        if (!response.ok) throw new Error(`Error ${response.status}`)
        setResults(await response.json())
        setShowDropdown(true)
      } catch {
        setResults([])
      } finally {
        setSearching(false)
      }
    }, 250)
    return () => clearTimeout(timer)
  }, [search])

  // Cierra el desplegable al hacer clic fuera del componente
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSearchChange = (e) => {
    setSearch(e.target.value)
    setPatientId(null) // Al reescribir se pierde la selección previa
  }

  const handleSelectPatient = (patient) => {
    skipSearchRef.current = true
    setPatientId(patient.id)
    setSearch(patient.nombre || `Paciente ${patient.id}`)
    setShowDropdown(false)
    setResults([])
    // Carga silenciosa del perfil en el Workspace
    onPatientLookup?.(patient.id)
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!patientId) return
    onProcess({
      patient_id: patientId,
      conversation_text: conversationText,
      vital_signs: vitalSigns,
      physical_exam: physicalExam,
    })
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
        <label htmlFor="patient_search">Paciente</label>
        <div className="patient-search" ref={wrapperRef}>
          <input
            id="patient_search"
            type="text"
            autoComplete="off"
            placeholder="Buscar por nombre o ID…"
            value={search}
            onChange={handleSearchChange}
            onFocus={() => results.length > 0 && setShowDropdown(true)}
          />
          {patientId && (
            <span className="patient-search-badge" title="Paciente seleccionado">
              ✓ ID {patientId}
            </span>
          )}

          {showDropdown && (
            <ul className="patient-search-dropdown">
              {searching && <li className="patient-search-empty">Buscando…</li>}
              {!searching && results.length === 0 && (
                <li className="patient-search-empty">Sin coincidencias.</li>
              )}
              {!searching &&
                results.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      className="patient-search-option"
                      onClick={() => handleSelectPatient(p)}
                    >
                      <span className="patient-search-name">
                        {p.nombre || '—'}
                      </span>
                      <span className="patient-search-meta">ID {p.id}</span>
                    </button>
                  </li>
                ))}
            </ul>
          )}
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

      <button
        type="submit"
        className="process-button"
        disabled={loading || !patientId}
      >
        {loading ? 'Procesando…' : 'Procesar con IA'}
      </button>
    </form>
  )
}

export default ConsultationForm
