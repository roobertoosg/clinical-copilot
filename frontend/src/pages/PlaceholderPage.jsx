function PlaceholderPage({ title, description }) {
  return (
    <div className="placeholder-page">
      <div className="placeholder-card">
        <div className="empty-icon" aria-hidden="true" />
        <h2>{title}</h2>
        <p>{description || 'Esta sección estará disponible próximamente.'}</p>
      </div>
    </div>
  )
}

export default PlaceholderPage
