import { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'

const INITIAL_VITALS = {
  ta: '',
  fc: '',
  fr: '',
  temp: '',
  satO2: '',
}

/** Solo dígitos y una barra: "120/80" */
function sanitizeBloodPressure(raw) {
  const cleaned = String(raw).replace(/[^\d/]/g, '')
  const parts = cleaned.split('/')
  if (parts.length === 1) return parts[0].slice(0, 3)
  return `${parts[0].slice(0, 3)}/${parts.slice(1).join('').slice(0, 3)}`
}

function parseBloodPressure(value) {
  const match = String(value).trim().match(/^(\d{2,3})\s*\/\s*(\d{2,3})$/)
  if (!match) return null
  return { systolic: Number(match[1]), diastolic: Number(match[2]) }
}

function isBloodPressureWarning(value) {
  if (!value.trim()) return false
  const bp = parseBloodPressure(value)
  // Solo alerta con formato completo Sistólica/Diastólica
  if (!bp) return false
  const { systolic, diastolic } = bp
  return systolic > 140 || systolic < 90 || diastolic > 90 || diastolic < 60
}

function clampNumericInput(raw, { min, max, decimals = 0 }) {
  if (raw === '' || raw === null || raw === undefined) return ''
  let text = String(raw)
  if (decimals > 0) {
    text = text.replace(/[^\d.]/g, '')
    const firstDot = text.indexOf('.')
    if (firstDot !== -1) {
      text =
        text.slice(0, firstDot + 1) +
        text.slice(firstDot + 1).replace(/\./g, '').slice(0, decimals)
    }
  } else {
    text = text.replace(/\D/g, '')
  }
  if (text === '' || text === '.') return text

  const num = Number(text)
  if (Number.isNaN(num)) return ''
  if (num > max) return String(max)
  if (text !== '.' && num < min && text.length >= String(min).length) {
    // Permitir tipado parcial (ej. "3" mientras escribe "36.5")
    return text
  }
  return text
}

function isOutOfNormalRange(value, minNormal, maxNormal) {
  if (value === '' || value === '.' || value == null) return false
  const num = Number(value)
  if (Number.isNaN(num)) return false
  return num < minNormal || num > maxNormal
}

function formatVitalSignsPayload(vitals) {
  const parts = []
  if (vitals.ta.trim()) parts.push(`TA ${vitals.ta.trim()} mmHg`)
  if (vitals.fc !== '') parts.push(`FC ${vitals.fc} lpm`)
  if (vitals.fr !== '') parts.push(`FR ${vitals.fr} rpm`)
  if (vitals.temp !== '' && vitals.temp !== '.') parts.push(`Temp ${vitals.temp} °C`)
  if (vitals.satO2 !== '') parts.push(`SatO2 ${vitals.satO2} %`)
  return parts.length ? parts.join(', ') : ''
}

function ConsultationForm({ onProcess, loading, onPatientLookup }) {
  const [patientId, setPatientId] = useState(null)
  const [search, setSearch] = useState('')
  const [results, setResults] = useState([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [searching, setSearching] = useState(false)

  const [vitals, setVitals] = useState(INITIAL_VITALS)
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

  const updateVital = (key, value) => {
    setVitals((prev) => ({ ...prev, [key]: value }))
  }

  const handleTaChange = (event) => {
    updateVital('ta', sanitizeBloodPressure(event.target.value))
  }

  const handleFcChange = (event) => {
    updateVital('fc', clampNumericInput(event.target.value, { min: 0, max: 300 }))
  }

  const handleFrChange = (event) => {
    updateVital('fr', clampNumericInput(event.target.value, { min: 0, max: 100 }))
  }

  const handleTempChange = (event) => {
    updateVital(
      'temp',
      clampNumericInput(event.target.value, { min: 30, max: 45, decimals: 1 })
    )
  }

  const handleSatChange = (event) => {
    updateVital('satO2', clampNumericInput(event.target.value, { min: 0, max: 100 }))
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!patientId) return
    onProcess({
      patient_id: patientId,
      conversation_text: conversationText,
      vital_signs: formatVitalSignsPayload(vitals),
      physical_exam: physicalExam,
      ai_provider: aiProvider,
    })
  }

  const taWarning = isBloodPressureWarning(vitals.ta)
  const fcWarning = isOutOfNormalRange(vitals.fc, 60, 100)
  const frWarning = isOutOfNormalRange(vitals.fr, 12, 20)
  const tempWarning = isOutOfNormalRange(vitals.temp, 36.0, 37.5)
  const satWarning = isOutOfNormalRange(vitals.satO2, 90, 100)

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

      <fieldset className="doc-field vitals-fieldset">
        <legend className="vitals-legend">Signos vitales</legend>
        <div className="vitals-grid">
          <div className="vital-field">
            <label htmlFor="vital_ta">TA</label>
            <div className={`vital-input-wrap${taWarning ? ' vital-input-wrap--warning' : ''}`}>
              <input
                id="vital_ta"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                placeholder="120/80"
                value={vitals.ta}
                onChange={handleTaChange}
                className={taWarning ? 'input-warning' : undefined}
                aria-invalid={taWarning}
              />
              <span className="vital-unit" aria-hidden="true">
                mmHg
              </span>
            </div>
          </div>

          <div className="vital-field">
            <label htmlFor="vital_fc">FC</label>
            <div className={`vital-input-wrap${fcWarning ? ' vital-input-wrap--warning' : ''}`}>
              <input
                id="vital_fc"
                type="number"
                inputMode="numeric"
                min={0}
                max={300}
                step={1}
                placeholder="72"
                value={vitals.fc}
                onChange={handleFcChange}
                className={fcWarning ? 'input-warning' : undefined}
                aria-invalid={fcWarning}
              />
              <span className="vital-unit" aria-hidden="true">
                lpm
              </span>
            </div>
          </div>

          <div className="vital-field">
            <label htmlFor="vital_fr">FR</label>
            <div className={`vital-input-wrap${frWarning ? ' vital-input-wrap--warning' : ''}`}>
              <input
                id="vital_fr"
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                step={1}
                placeholder="16"
                value={vitals.fr}
                onChange={handleFrChange}
                className={frWarning ? 'input-warning' : undefined}
                aria-invalid={frWarning}
              />
              <span className="vital-unit" aria-hidden="true">
                rpm
              </span>
            </div>
          </div>

          <div className="vital-field">
            <label htmlFor="vital_temp">Temp</label>
            <div className={`vital-input-wrap${tempWarning ? ' vital-input-wrap--warning' : ''}`}>
              <input
                id="vital_temp"
                type="number"
                inputMode="decimal"
                min={30}
                max={45}
                step={0.1}
                placeholder="36.5"
                value={vitals.temp}
                onChange={handleTempChange}
                className={tempWarning ? 'input-warning' : undefined}
                aria-invalid={tempWarning}
              />
              <span className="vital-unit" aria-hidden="true">
                °C
              </span>
            </div>
          </div>

          <div className="vital-field">
            <label htmlFor="vital_sato2">SatO₂</label>
            <div className={`vital-input-wrap${satWarning ? ' vital-input-wrap--warning' : ''}`}>
              <input
                id="vital_sato2"
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                step={1}
                placeholder="98"
                value={vitals.satO2}
                onChange={handleSatChange}
                className={satWarning ? 'input-warning' : undefined}
                aria-invalid={satWarning}
              />
              <span className="vital-unit" aria-hidden="true">
                %
              </span>
            </div>
          </div>
        </div>
      </fieldset>

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
