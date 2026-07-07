const demoPatient = {
  firstName: 'María',
  lastName: 'González',
  age: 42,
  gender: 'Femenino',
  documentId: 'HC-000123',
  allergies: [
    { allergen: 'Penicilina', severity: 'Severa' },
    { allergen: 'Sulfamidas', severity: 'Moderada' },
    { allergen: 'Mariscos', severity: 'Leve' },
  ],
  history: [
    'Hipertensión arterial (2018)',
    'Diabetes mellitus tipo 2 (2020)',
    'Colecistectomía (2015)',
  ],
  medications: [
    { name: 'Metformina', dosage: '850 mg', frequency: 'cada 12 h' },
    { name: 'Losartán', dosage: '50 mg', frequency: 'cada 24 h' },
    { name: 'Ácido acetilsalicílico', dosage: '100 mg', frequency: 'cada 24 h' },
  ],
}

function PatientProfile({ patient = demoPatient }) {
  const initials = `${patient.firstName?.[0] ?? ''}${patient.lastName?.[0] ?? ''}`

  return (
    <aside className="patient-profile">
      <div className="patient-profile-head">
        <div className="patient-avatar" aria-hidden="true">
          {initials}
        </div>
        <div>
          <h2 className="patient-name">
            {patient.firstName} {patient.lastName}
          </h2>
          <p className="patient-meta">
            {patient.age} años · {patient.gender}
          </p>
          <p className="patient-doc">{patient.documentId}</p>
        </div>
      </div>

      <section className="profile-section">
        <h3 className="profile-section-title">Alergias</h3>
        {patient.allergies?.length > 0 ? (
          <div className="allergy-tags">
            {patient.allergies.map((a) => (
              <span key={a.allergen} className="allergy-tag">
                {a.allergen}
                <span className="allergy-tag-severity">{a.severity}</span>
              </span>
            ))}
          </div>
        ) : (
          <p className="profile-empty">Sin alergias registradas</p>
        )}
      </section>

      <section className="profile-section">
        <h3 className="profile-section-title">Antecedentes</h3>
        {patient.history?.length > 0 ? (
          <ul className="history-list">
            {patient.history.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="profile-empty">Sin antecedentes registrados</p>
        )}
      </section>

      <section className="profile-section">
        <h3 className="profile-section-title">Medicamentos actuales</h3>
        {patient.medications?.length > 0 ? (
          <ul className="current-med-list">
            {patient.medications.map((m) => (
              <li key={m.name}>
                <span className="current-med-name">{m.name}</span>
                <span className="current-med-detail">
                  {m.dosage} · {m.frequency}
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
