import ClinicalCards from './ClinicalCards'
import ClinicalReviewEditor from './ClinicalReviewEditor'

function AIResults({
  step = 'capture',
  loading = false,
  finalizing = false,
  doctorFinalData = null,
  completedData = null,
  accuracyScore = null,
  onDoctorDataChange,
  onFinalize,
}) {
  const showEmpty = step === 'capture' && !loading && !doctorFinalData
  const folio = completedData?.folio

  return (
    <div className="ai-results">
      <div className="column-header">
        <span className="column-header-accent" aria-hidden="true" />
        <h2 className="section-title">
          {step === 'review'
            ? 'Revisión médica'
            : step === 'completed'
              ? 'Consulta finalizada'
              : 'Resultados de IA'}
        </h2>
        {step === 'completed' && folio && (
          <span className="review-folio-badge" title="Folio persistido">
            {folio}
          </span>
        )}
      </div>

      <div className="ai-results-body">
        {loading && (
          <div className="loading-message">
            <span className="loading-spinner" aria-hidden="true" />
            <p>La IA está generando el borrador clínico...</p>
          </div>
        )}

        {!loading && step === 'review' && doctorFinalData && (
          <ClinicalReviewEditor
            data={doctorFinalData}
            onChange={onDoctorDataChange}
            onFinalize={onFinalize}
            finalizing={finalizing}
          />
        )}

        {!loading && step === 'completed' && completedData && (
          <>
            {typeof accuracyScore === 'number' && (
              <div className="accuracy-banner">
                Precisión IA (similitud SOAPE):{' '}
                <strong>{(accuracyScore * 100).toFixed(1)}%</strong>
              </div>
            )}
            <ClinicalCards data={completedData} />
          </>
        )}

        {showEmpty && (
          <div className="empty-results">
            <div className="empty-icon" aria-hidden="true" />
            <p>
              Complete el formulario y genere el borrador para revisar y editar
              la consulta antes de finalizar.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default AIResults
