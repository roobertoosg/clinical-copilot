import { useState } from 'react'

const API_BASE = 'http://localhost:8000'

const emptyBaseForm = {
  first_name: '',
  last_name: '',
  date_of_birth: '',
  gender: '',
}

const emptyAllergyForm = { allergen: '', reaction: '', severity: '' }
const emptyMedicationForm = { name: '', dosage: '', frequency: '' }

function PatientsPage() {
  // Vista base (crear paciente)
  const [baseForm, setBaseForm] = useState(emptyBaseForm)
  const [creating, setCreating] = useState(false)
  const [baseError, setBaseError] = useState(null)

  // Paciente activo (cambia a la vista de detalles)
  const [activePatient, setActivePatient] = useState(null)

  // Sub-secciones clínicas
  const [allergyForm, setAllergyForm] = useState(emptyAllergyForm)
  const [allergies, setAllergies] = useState([])
  const [allergyLoading, setAllergyLoading] = useState(false)
  const [allergyNotice, setAllergyNotice] = useState(null)

  const [medicationForm, setMedicationForm] = useState(emptyMedicationForm)
  const [medications, setMedications] = useState([])
  const [medicationLoading, setMedicationLoading] = useState(false)
  const [medicationNotice, setMedicationNotice] = useState(null)

  const updateBase = (field) => (e) =>
    setBaseForm((prev) => ({ ...prev, [field]: e.target.value }))
  const updateAllergy = (field) => (e) =>
    setAllergyForm((prev) => ({ ...prev, [field]: e.target.value }))
  const updateMedication = (field) => (e) =>
    setMedicationForm((prev) => ({ ...prev, [field]: e.target.value }))

  const handleCreatePatient = async (e) => {
    e.preventDefault()
    setBaseError(null)
    setCreating(true)

    try {
      const response = await fetch(`${API_BASE}/patients/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(baseForm),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setActivePatient(data)
    } catch (error) {
      setBaseError(`No se pudo registrar el paciente: ${error.message}`)
    } finally {
      setCreating(false)
    }
  }

  const handleAddAllergy = async (e) => {
    e.preventDefault()
    setAllergyNotice(null)
    setAllergyLoading(true)

    try {
      const response = await fetch(
        `${API_BASE}/patients/${activePatient.id}/allergies`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(allergyForm),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setAllergies((prev) => [...prev, data])
      setAllergyForm(emptyAllergyForm)
      setAllergyNotice({ type: 'success', message: 'Alergia registrada.' })
    } catch (error) {
      setAllergyNotice({ type: 'error', message: error.message })
    } finally {
      setAllergyLoading(false)
    }
  }

  const handleAddMedication = async (e) => {
    e.preventDefault()
    setMedicationNotice(null)
    setMedicationLoading(true)

    try {
      const response = await fetch(
        `${API_BASE}/patients/${activePatient.id}/medications`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(medicationForm),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setMedications((prev) => [...prev, data])
      setMedicationForm(emptyMedicationForm)
      setMedicationNotice({ type: 'success', message: 'Medicamento registrado.' })
    } catch (error) {
      setMedicationNotice({ type: 'error', message: error.message })
    } finally {
      setMedicationLoading(false)
    }
  }

  const handleFinish = () => {
    setActivePatient(null)
    setBaseForm(emptyBaseForm)
    setBaseError(null)
    setAllergyForm(emptyAllergyForm)
    setAllergies([])
    setAllergyNotice(null)
    setMedicationForm(emptyMedicationForm)
    setMedications([])
    setMedicationNotice(null)
  }

  // ── Vista 1: formulario base ──────────────────────────────
  if (!activePatient) {
    return (
      <div className="patients-page">
        <div className="page-header">
          <h1 className="page-title">Gestión de Pacientes</h1>
          <p className="page-subtitle">
            Registre nuevos pacientes en la base de datos clínica.
          </p>
        </div>

        <form className="consultation-doc patients-form" onSubmit={handleCreatePatient}>
          <div className="doc-header">
            <h2 className="doc-title">Registro de Paciente Nuevo</h2>
            <p className="doc-subtitle">Complete los datos básicos del paciente.</p>
          </div>

          {baseError && (
            <div className="form-feedback form-feedback--error">{baseError}</div>
          )}

          <div className="field-row">
            <div className="doc-field">
              <label htmlFor="first_name">Nombre(s)</label>
              <input
                id="first_name"
                type="text"
                placeholder="Ej. María"
                value={baseForm.first_name}
                onChange={updateBase('first_name')}
                required
              />
            </div>

            <div className="doc-field">
              <label htmlFor="last_name">Apellido(s)</label>
              <input
                id="last_name"
                type="text"
                placeholder="Ej. González"
                value={baseForm.last_name}
                onChange={updateBase('last_name')}
                required
              />
            </div>
          </div>

          <div className="field-row">
            <div className="doc-field">
              <label htmlFor="date_of_birth">Fecha de nacimiento</label>
              <input
                id="date_of_birth"
                type="date"
                value={baseForm.date_of_birth}
                onChange={updateBase('date_of_birth')}
                required
              />
            </div>

            <div className="doc-field">
              <label htmlFor="gender">Sexo</label>
              <select
                id="gender"
                value={baseForm.gender}
                onChange={updateBase('gender')}
                required
              >
                <option value="" disabled>
                  Seleccione una opción
                </option>
                <option value="Femenino">Femenino</option>
                <option value="Masculino">Masculino</option>
                <option value="Otro">Otro</option>
              </select>
            </div>
          </div>

          <button type="submit" className="process-button" disabled={creating}>
            {creating ? 'Guardando…' : 'Registrar y continuar'}
          </button>
        </form>
      </div>
    )
  }

  // ── Vista 2: panel de detalles (gestión clínica) ──────────
  return (
    <div className="patients-page patients-page--wide">
      <div className="page-header">
        <div>
          <h1 className="page-title">Detalles del Paciente</h1>
          <p className="page-subtitle">
            {activePatient.first_name} {activePatient.last_name} · ID:{' '}
            {activePatient.id}
          </p>
        </div>
        <button type="button" className="finish-button" onClick={handleFinish}>
          Finalizar y limpiar
        </button>
      </div>

      <div className="form-feedback form-feedback--success">
        Paciente registrado correctamente con ID: {activePatient.id}. Agregue sus
        alergias y medicamentos.
      </div>

      <div className="clinical-grid">
        {/* ── Alergias ── */}
        <div className="clinical-card">
          <div className="clinical-card-header">
            <h2>Alergias</h2>
            <span className="clinical-count">{allergies.length}</span>
          </div>

          <form className="mini-form" onSubmit={handleAddAllergy}>
            <div className="doc-field">
              <label htmlFor="allergen">Alérgeno</label>
              <input
                id="allergen"
                type="text"
                placeholder="Ej. Penicilina"
                value={allergyForm.allergen}
                onChange={updateAllergy('allergen')}
                required
              />
            </div>
            <div className="doc-field">
              <label htmlFor="reaction">Reacción</label>
              <input
                id="reaction"
                type="text"
                placeholder="Ej. Erupción cutánea"
                value={allergyForm.reaction}
                onChange={updateAllergy('reaction')}
                required
              />
            </div>
            <div className="doc-field">
              <label htmlFor="allergy_severity">Severidad</label>
              <select
                id="allergy_severity"
                value={allergyForm.severity}
                onChange={updateAllergy('severity')}
                required
              >
                <option value="" disabled>
                  Seleccione severidad
                </option>
                <option value="Alta">Alta</option>
                <option value="Media">Media</option>
                <option value="Baja">Baja</option>
              </select>
            </div>

            {allergyNotice && (
              <div className={`inline-notice inline-notice--${allergyNotice.type}`}>
                {allergyNotice.message}
              </div>
            )}

            <button
              type="submit"
              className="secondary-button"
              disabled={allergyLoading}
            >
              {allergyLoading ? 'Agregando…' : 'Agregar alergia'}
            </button>
          </form>

          {allergies.length > 0 ? (
            <div className="allergy-tags clinical-list">
              {allergies.map((a) => (
                <span key={a.id} className="allergy-tag">
                  {a.allergen}
                  <span className="allergy-tag-severity">{a.severity}</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="profile-empty">Aún no hay alergias registradas.</p>
          )}
        </div>

        {/* ── Medicamentos ── */}
        <div className="clinical-card">
          <div className="clinical-card-header">
            <h2>Medicamentos</h2>
            <span className="clinical-count">{medications.length}</span>
          </div>

          <form className="mini-form" onSubmit={handleAddMedication}>
            <div className="doc-field">
              <label htmlFor="med_name">Nombre</label>
              <input
                id="med_name"
                type="text"
                placeholder="Ej. Paracetamol"
                value={medicationForm.name}
                onChange={updateMedication('name')}
                required
              />
            </div>
            <div className="doc-field">
              <label htmlFor="med_dosage">Dosis</label>
              <input
                id="med_dosage"
                type="text"
                placeholder="Ej. 500 mg"
                value={medicationForm.dosage}
                onChange={updateMedication('dosage')}
                required
              />
            </div>
            <div className="doc-field">
              <label htmlFor="med_frequency">Frecuencia</label>
              <input
                id="med_frequency"
                type="text"
                placeholder="Ej. Cada 8 horas"
                value={medicationForm.frequency}
                onChange={updateMedication('frequency')}
                required
              />
            </div>

            {medicationNotice && (
              <div
                className={`inline-notice inline-notice--${medicationNotice.type}`}
              >
                {medicationNotice.message}
              </div>
            )}

            <button
              type="submit"
              className="secondary-button"
              disabled={medicationLoading}
            >
              {medicationLoading ? 'Agregando…' : 'Agregar medicamento'}
            </button>
          </form>

          {medications.length > 0 ? (
            <ul className="current-med-list clinical-list">
              {medications.map((m) => (
                <li key={m.id}>
                  <span className="current-med-name">{m.name}</span>
                  <span className="current-med-detail">
                    {[m.dosage, m.frequency].filter(Boolean).join(' · ')}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="profile-empty">Aún no hay medicamentos registrados.</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default PatientsPage
