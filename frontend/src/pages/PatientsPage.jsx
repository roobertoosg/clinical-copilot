import { useCallback, useEffect, useState } from 'react'
import PatientProfile from '../components/PatientProfile'
import { API_BASE } from '../config'

const emptyForm = {
  first_name: '',
  last_name: '',
  date_of_birth: '',
  gender: '',
}

function formatDob(value) {
  if (!value) return 'Fecha no registrada'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('es-MX', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    timeZone: 'UTC',
  })
}

function PatientsPage() {
  // ── Panel izquierdo: búsqueda + lista ──────────────────────
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)

  // ── Panel derecho: formulario de detalle ───────────────────
  const [selectedId, setSelectedId] = useState(null) // null => "Nuevo paciente"
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState(null)
  const [formNotice, setFormNotice] = useState(null)

  // ── Perfil clínico del paciente seleccionado ───────────────
  const [profile, setProfile] = useState(null)
  const [profileLoading, setProfileLoading] = useState(false)

  const updateField = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }))

  const fetchList = useCallback(async (searchText = '') => {
    setSearching(true)
    try {
      const url = searchText.trim()
        ? `${API_BASE}/patients/?search=${encodeURIComponent(searchText.trim())}`
        : `${API_BASE}/patients/`
      const response = await fetch(url)
      if (!response.ok) throw new Error(`Error ${response.status}`)
      setResults(await response.json())
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }, [])

  // Carga inicial + búsqueda con debounce al escribir
  useEffect(() => {
    const timer = setTimeout(() => fetchList(query), 250)
    return () => clearTimeout(timer)
  }, [query, fetchList])

  const loadProfile = useCallback(async (id) => {
    if (!id) {
      setProfile(null)
      return
    }
    setProfileLoading(true)
    try {
      const response = await fetch(
        `${API_BASE}/patients/${id}/clinical-profile`
      )
      if (!response.ok) throw new Error(`Error ${response.status}`)
      setProfile(await response.json())
    } catch {
      setProfile(null)
    } finally {
      setProfileLoading(false)
    }
  }, [])

  const handleNewPatient = () => {
    setSelectedId(null)
    setForm(emptyForm)
    setProfile(null)
    setFormError(null)
    setFormNotice(null)
  }

  const handleSelectPatient = async (id) => {
    setFormError(null)
    setFormNotice(null)
    try {
      const response = await fetch(`${API_BASE}/patients/${id}`)
      if (!response.ok) throw new Error(`Error ${response.status}`)
      const data = await response.json()
      setSelectedId(data.id)
      setForm({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        date_of_birth: data.date_of_birth || '',
        gender: data.gender || '',
      })
      loadProfile(data.id)
    } catch (error) {
      setFormError(`No se pudo cargar el paciente: ${error.message}`)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setFormError(null)
    setFormNotice(null)
    setSaving(true)

    const isEdit = selectedId != null
    const url = isEdit
      ? `${API_BASE}/patients/${selectedId}`
      : `${API_BASE}/patients/`

    try {
      const response = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }
      const data = await response.json()

      setSelectedId(data.id)
      setForm({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        date_of_birth: data.date_of_birth || '',
        gender: data.gender || '',
      })
      setFormNotice(
        isEdit
          ? 'Datos del paciente actualizados correctamente.'
          : `Paciente registrado con ID ${data.id}. Ya puede gestionar sus alergias y medicamentos.`
      )
      loadProfile(data.id)
      fetchList(query)
    } catch (error) {
      setFormError(
        `No se pudo ${isEdit ? 'actualizar' : 'registrar'} el paciente: ${error.message}`
      )
    } finally {
      setSaving(false)
    }
  }

  const isEdit = selectedId != null

  return (
    <div className="patients-page patients-page--wide">
      <div className="page-header">
        <div>
          <h1 className="page-title">Gestión de Pacientes</h1>
          <p className="page-subtitle">
            Busque, registre y edite pacientes de la base de datos clínica.
          </p>
        </div>
      </div>

      <div className="master-detail">
        {/* ── Maestro: búsqueda + lista ── */}
        <aside className="master-panel">
          <button
            type="button"
            className="process-button master-new-btn"
            onClick={handleNewPatient}
          >
            + Nuevo Paciente
          </button>

          <div className="master-search">
            <input
              type="text"
              placeholder="Buscar por nombre o ID…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          <div className="master-list">
            {searching && <p className="profile-empty">Buscando…</p>}
            {!searching && results.length === 0 && (
              <p className="profile-empty">Sin pacientes.</p>
            )}
            {!searching &&
              results.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`master-list-item${
                    p.id === selectedId ? ' master-list-item--active' : ''
                  }`}
                  onClick={() => handleSelectPatient(p.id)}
                >
                  <span className="master-list-name">{p.nombre || '—'}</span>
                  <span className="master-list-meta">
                    ID {p.id} · {formatDob(p.date_of_birth)}
                  </span>
                </button>
              ))}
          </div>
        </aside>

        {/* ── Detalle: formulario + gestión clínica ── */}
        <section className="detail-panel">
          <form className="consultation-doc patients-form" onSubmit={handleSubmit}>
            <div className="doc-header">
              <h2 className="doc-title">
                {isEdit ? 'Editar Paciente' : 'Registro de Paciente Nuevo'}
              </h2>
              <p className="doc-subtitle">
                {isEdit
                  ? `Modifique los datos demográficos (ID ${selectedId}).`
                  : 'Complete los datos básicos del paciente.'}
              </p>
            </div>

            {formError && (
              <div className="form-feedback form-feedback--error">{formError}</div>
            )}
            {formNotice && (
              <div className="form-feedback form-feedback--success">
                {formNotice}
              </div>
            )}

            <div className="field-row">
              <div className="doc-field">
                <label htmlFor="first_name">Nombre(s)</label>
                <input
                  id="first_name"
                  type="text"
                  placeholder="Ej. María"
                  value={form.first_name}
                  onChange={updateField('first_name')}
                  required
                />
              </div>

              <div className="doc-field">
                <label htmlFor="last_name">Apellido(s)</label>
                <input
                  id="last_name"
                  type="text"
                  placeholder="Ej. González"
                  value={form.last_name}
                  onChange={updateField('last_name')}
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
                  value={form.date_of_birth}
                  onChange={updateField('date_of_birth')}
                  required
                />
              </div>

              <div className="doc-field">
                <label htmlFor="gender">Sexo</label>
                <select
                  id="gender"
                  value={form.gender}
                  onChange={updateField('gender')}
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

            <button type="submit" className="process-button" disabled={saving}>
              {saving
                ? 'Guardando…'
                : isEdit
                  ? 'Guardar cambios'
                  : 'Registrar paciente'}
            </button>
          </form>

          {/* Gestión clínica (alergias y medicamentos) del paciente seleccionado */}
          {isEdit ? (
            <PatientProfile
              patientData={profile}
              loading={profileLoading}
              onPatientLookup={loadProfile}
            />
          ) : (
            <aside className="patient-profile patient-profile--empty">
              <div className="empty-icon" aria-hidden="true" />
              <p className="profile-placeholder-text">
                Registre o seleccione un paciente para gestionar sus alergias y
                medicamentos.
              </p>
            </aside>
          )}
        </section>
      </div>
    </div>
  )
}

export default PatientsPage
