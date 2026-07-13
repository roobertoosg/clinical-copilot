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

  // Proveedor de IA seleccionado: 'gemini' (nube) u 'ollama' (local)
  const [aiProvider, setAiProvider] = useState('gemini')

  // Grabación de audio (Speech-to-Text)
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])

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

  const transcribeBlob = async (blob) => {
    setIsTranscribing(true)
    try {
      const formData = new FormData()
      formData.append('file', blob, 'grabacion.webm')
      const response = await fetch(`${API_BASE}/clinical-ai/transcribe`, {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }
      const data = await response.json()
      const text = (data.transcription || '').trim()
      if (text) {
        // Concatena al final de las notas, separando con salto de línea si ya había texto
        setConversationText((prev) => (prev.trim() ? `${prev}\n${text}` : text))
      }
    } catch (error) {
      alert(`No se pudo transcribir el audio: ${error.message}`)
    } finally {
      setIsTranscribing(false)
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      audioChunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }
      recorder.onstop = async () => {
        // Libera el micrófono
        stream.getTracks().forEach((track) => track.stop())
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        await transcribeBlob(blob)
      }

      mediaRecorderRef.current = recorder
      recorder.start()
      setIsRecording(true)
    } catch (error) {
      alert(`No se pudo acceder al micrófono: ${error.message}`)
    }
  }

  const stopRecording = () => {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
    setIsRecording(false)
  }

  const handleToggleRecording = () => {
    if (isRecording) stopRecording()
    else startRecording()
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!patientId) return
    onProcess({
      patient_id: patientId,
      conversation_text: conversationText,
      vital_signs: vitalSigns,
      physical_exam: physicalExam,
      ai_provider: aiProvider,
    })
  }

  return (
    <form className="consultation-doc" onSubmit={handleSubmit}>
      <div className="doc-header">
        <div className="doc-header-top">
          <div>
            <h2 className="doc-title">Captura de consulta</h2>
            <p className="doc-subtitle">
              Registre los datos clínicos y procese con la IA.
            </p>
          </div>

          <div
            className="ai-provider-switch"
            role="group"
            aria-label="Proveedor de IA"
          >
            <button
              type="button"
              className={`ai-provider-option${
                aiProvider === 'gemini' ? ' ai-provider-option--active' : ''
              }`}
              onClick={() => setAiProvider('gemini')}
              aria-pressed={aiProvider === 'gemini'}
            >
              <span className="ai-provider-icon" aria-hidden="true">
                ✨
              </span>
              <span className="ai-provider-text">
                <span className="ai-provider-name">Gemini</span>
                <span className="ai-provider-tag">Cloud · Recomendado</span>
              </span>
            </button>
            <button
              type="button"
              className={`ai-provider-option${
                aiProvider === 'ollama' ? ' ai-provider-option--active' : ''
              }`}
              onClick={() => setAiProvider('ollama')}
              aria-pressed={aiProvider === 'ollama'}
            >
              <span className="ai-provider-icon" aria-hidden="true">
                🦙
              </span>
              <span className="ai-provider-text">
                <span className="ai-provider-name">Ollama</span>
                <span className="ai-provider-tag">Local</span>
              </span>
            </button>
          </div>
        </div>
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
        <div className="doc-field-label-row">
          <label htmlFor="conversation_text">Conversación / Notas</label>
          <button
            type="button"
            className={`mic-button${isRecording ? ' mic-button--recording' : ''}`}
            onClick={handleToggleRecording}
            disabled={isTranscribing}
            title={isRecording ? 'Detener grabación' : 'Grabar audio'}
          >
            {isTranscribing ? (
              <>
                <span className="loading-spinner loading-spinner--sm" aria-hidden="true" />
                Transcribiendo…
              </>
            ) : isRecording ? (
              <>
                <span className="mic-button-dot" aria-hidden="true" />
                Detener Grabación
              </>
            ) : (
              <>🎤 Grabar Audio</>
            )}
          </button>
        </div>
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
