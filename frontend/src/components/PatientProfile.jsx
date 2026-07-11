function PatientProfile({ patientData, loading }) {
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

  const { nombre, edad, sexo, alergias, medicamentos_actuales } = patientData
  const initials = (nombre || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()

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

      <section className="profile-section">
        <h3 className="profile-section-title">Alergias</h3>
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

      <section className="profile-section">
        <h3 className="profile-section-title">Medicamentos actuales</h3>
        {medicamentos_actuales?.length > 0 ? (
          <ul className="current-med-list">
            {medicamentos_actuales.map((m, index) => (
              <li key={index}>
                <span className="current-med-name">{m.name}</span>
                <span className="current-med-detail">
                  {[m.dosage, m.frequency].filter(Boolean).join(' · ')}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="profile-empty">Sin medicamentos activos</p>
        )}
      </section>
    </aside>
  )
}

export default PatientProfile
