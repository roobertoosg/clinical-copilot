import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

const emptyAllergy = { allergen: '', reaction: '', severity: '' }
const emptyMed = { name: '', dosage: '', frequency: '' }

function PatientProfile({ patientData, loading, onPatientLookup }) {
  const [medications, setMedications] = useState([])
  const [togglingId, setTogglingId] = useState(null)

  const [showAllergyForm, setShowAllergyForm] = useState(false)
  const [allergyForm, setAllergyForm] = useState(emptyAllergy)
  const [savingAllergy, setSavingAllergy] = useState(false)

  const [showMedForm, setShowMedForm] = useState(false)
  const [medForm, setMedForm] = useState(emptyMed)
  const [savingMed, setSavingMed] = useState(false)

  useEffect(() => {
    setMedications(patientData?.medicamentos_actuales ?? [])
  }, [patientData])

  const reload = () => {
    if (patientData) onPatientLookup?.(patientData.id)
  }

  const handleToggleMedication = async (medId) => {
    if (!patientData) return
    setTogglingId(medId)
    try {
      const response = await fetch(
        `${API_BASE}/patients/${patientData.id}/medications/${medId}/toggle-status`,
        { method: 'PATCH' }
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }
      const updated = await response.json()
      setMedications((prev) =>
        prev.map((m) => (m.id === updated.id ? { ...m, is_active: updated.is_active } : m))
      )
    } catch (error) {
      alert(`No se pudo actualizar el medicamento: ${error.message}`)
    } finally {
      setTogglingId(null)
    }
  }

  const handleAddAllergy = async (e) => {
    e.preventDefault()
    setSavingAllergy(true)
    try {
      const response = await fetch(
        `${API_BASE}/patients/${patientData.id}/allergies`,
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
      setAllergyForm(emptyAllergy)
      setShowAllergyForm(false)
      reload()
    } catch (error) {
      alert(`No se pudo agregar la alergia: ${error.message}`)
    } finally {
      setSavingAllergy(false)
    }
  }

  const handleAddMedication = async (e) => {
    e.preventDefault()
    setSavingMed(true)
    try {
      const response = await fetch(
        `${API_BASE}/patients/${patientData.id}/medications`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(medForm),
        }
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }
      setMedForm(emptyMed)
      setShowMedForm(false)
      reload()
    } catch (error) {
      alert(`No se pudo agregar el medicamento: ${error.message}`)
    } finally {
      setSavingMed(false)
    }
  }

  if (loading) {
    return (
      <aside className="patient-profile patient-profile--empty">
        <span className="loading-spinner" aria-hidden="true" />
        <p className="profile-placeholder-text">Cargando perfil del paciente…</p>
      </aside>
    )
  }

  if (!patientData) {
    return (
      <aside className="patient-profile patient-profile--empty">
        <div className="empty-icon" aria-hidden="true" />
        <p className="profile-placeholder-text">
          Ingrese un ID de paciente para cargar su perfil.
        </p>
      </aside>
    )
  }

  const { nombre, edad, sexo, alergias } = patientData
  const initials = (nombre || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()

  const activeMeds = medications.filter((m) => m.is_active)
  const suspendedMeds = medications.filter((m) => !m.is_active)

  return (
    <aside className="patient-profile">
      <div className="patient-profile-head">
        <div className="patient-avatar" aria-hidden="true">
          {initials || '—'}
        </div>
        <div>
          <h2 className="patient-name">{nombre}</h2>
          <p className="patient-meta">
            {edad != null ? `${edad} años` : 'Edad no registrada'}
            {sexo ? ` · ${sexo}` : ''}
          </p>
          <p className="patient-doc">ID: {patientData.id}</p>
        </div>
      </div>

      {/* ── Alergias ── */}
      <section className="profile-section">
        <div className="profile-section-head">
          <h3 className="profile-section-title">Alergias</h3>
          <button
            type="button"
            className="add-inline-btn"
            title="Agregar alergia"
            aria-label="Agregar alergia"
            onClick={() => setShowAllergyForm((v) => !v)}
          >
            {showAllergyForm ? '×' : '+'}
          </button>
        </div>

        {showAllergyForm && (
          <form className="inline-form" onSubmit={handleAddAllergy}>
            <input
              type="text"
              placeholder="Alérgeno (ej. Penicilina)"
              value={allergyForm.allergen}
              onChange={(e) =>
                setAllergyForm((p) => ({ ...p, allergen: e.target.value }))
              }
              required
            />
            <input
              type="text"
              placeholder="Reacción (ej. Erupción)"
              value={allergyForm.reaction}
              onChange={(e) =>
                setAllergyForm((p) => ({ ...p, reaction: e.target.value }))
              }
              required
            />
            <select
              value={allergyForm.severity}
              onChange={(e) =>
                setAllergyForm((p) => ({ ...p, severity: e.target.value }))
              }
              required
            >
              <option value="" disabled>
                Severidad
              </option>
              <option value="Alta">Alta</option>
              <option value="Media">Media</option>
              <option value="Baja">Baja</option>
            </select>
            <button
              type="submit"
              className="secondary-button secondary-button--sm"
              disabled={savingAllergy}
            >
              {savingAllergy ? 'Guardando…' : 'Agregar'}
            </button>
          </form>
        )}

        {alergias?.length > 0 ? (
          <div className="allergy-tags">
            {alergias.map((a, index) => (
              <span key={index} className="allergy-tag">
                {a.allergen}
                {a.severity && (
                  <span className="allergy-tag-severity">{a.severity}</span>
                )}
              </span>
            ))}
          </div>
        ) : (
          <p className="profile-empty">Sin alergias registradas</p>
        )}
      </section>

      {/* ── Medicamentos ── */}
      <section className="profile-section">
        <div className="profile-section-head">
          <h3 className="profile-section-title">Medicamentos actuales</h3>
          <button
            type="button"
            className="add-inline-btn"
            title="Agregar medicamento"
            aria-label="Agregar medicamento"
            onClick={() => setShowMedForm((v) => !v)}
          >
            {showMedForm ? '×' : '+'}
          </button>
        </div>

        {showMedForm && (
          <form className="inline-form" onSubmit={handleAddMedication}>
            <input
              type="text"
              placeholder="Nombre (ej. Paracetamol)"
              value={medForm.name}
              onChange={(e) => setMedForm((p) => ({ ...p, name: e.target.value }))}
              required
            />
            <input
              type="text"
              placeholder="Dosis (ej. 500 mg)"
              value={medForm.dosage}
              onChange={(e) =>
                setMedForm((p) => ({ ...p, dosage: e.target.value }))
              }
              required
            />
            <input
              type="text"
              placeholder="Frecuencia (ej. Cada 8 h)"
              value={medForm.frequency}
              onChange={(e) =>
                setMedForm((p) => ({ ...p, frequency: e.target.value }))
              }
              required
            />
            <button
              type="submit"
              className="secondary-button secondary-button--sm"
              disabled={savingMed}
            >
              {savingMed ? 'Guardando…' : 'Agregar'}
            </button>
          </form>
        )}

        {activeMeds.length > 0 ? (
          <ul className="current-med-list">
            {activeMeds.map((m) => (
              <li key={m.id}>
                <div className="current-med-info">
                  <span className="current-med-name">{m.name}</span>
                  <span className="current-med-detail">
                    {[m.dosage, m.frequency].filter(Boolean).join(' · ')}
                  </span>
                </div>
                <button
                  type="button"
                  className="med-toggle-btn med-toggle-btn--suspend"
                  title="Suspender medicamento"
                  aria-label={`Suspender ${m.name}`}
                  onClick={() => handleToggleMedication(m.id)}
                  disabled={togglingId === m.id}
                >
                  {togglingId === m.id ? '…' : '⏸'}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="profile-empty">Sin medicamentos activos</p>
        )}

        {suspendedMeds.length > 0 && (
          <details className="suspended-meds">
            <summary>
              Suspendidos / Historial
              <span className="suspended-count">{suspendedMeds.length}</span>
            </summary>
            <ul className="current-med-list current-med-list--suspended">
              {suspendedMeds.map((m) => (
                <li key={m.id}>
                  <div className="current-med-info">
                    <span className="current-med-name">{m.name}</span>
                    <span className="current-med-detail">
                      {[m.dosage, m.frequency].filter(Boolean).join(' · ')}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="med-toggle-btn med-toggle-btn--resume"
                    title="Reanudar medicamento"
                    aria-label={`Reanudar ${m.name}`}
                    onClick={() => handleToggleMedication(m.id)}
                    disabled={togglingId === m.id}
                  >
                    {togglingId === m.id ? '…' : '▶'}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>
    </aside>
  )
}

export default PatientProfile
