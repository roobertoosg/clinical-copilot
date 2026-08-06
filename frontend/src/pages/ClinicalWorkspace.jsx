import { useState } from 'react'
import PatientProfile from '../components/PatientProfile'
import ConsultationForm from '../components/ConsultationForm'
import AIResults from '../components/AIResults'
import { downloadConsultationPdfs } from '../utils/exportPdf'
import { API_BASE } from '../config'

function cloneClinicalData(data) {
  return JSON.parse(JSON.stringify(data))
}

function ClinicalWorkspace() {
  const [step, setStep] = useState('capture') // capture | review | completed
  const [loading, setLoading] = useState(false)
  const [finalizing, setFinalizing] = useState(false)

  const [aiOriginalData, setAiOriginalData] = useState(null)
  const [doctorFinalData, setDoctorFinalData] = useState(null)
  const [completedData, setCompletedData] = useState(null)
  const [accuracyScore, setAccuracyScore] = useState(null)
  const [capturePayload, setCapturePayload] = useState(null)

  const [patientData, setPatientData] = useState(null)
  const [patientLoading, setPatientLoading] = useState(false)

  const fetchPatientProfile = async (id) => {
    if (!id) {
      setPatientData(null)
      return
    }

    setPatientLoading(true)
    try {
      const response = await fetch(
        `${API_BASE}/patients/${id}/clinical-profile`
      )

      if (!response.ok) {
        setPatientData(null)
        if (response.status !== 404) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `Error ${response.status}`)
        }
        return
      }

      const data = await response.json()
      setPatientData(data)
    } catch (error) {
      setPatientData(null)
      alert(`Error al cargar el perfil del paciente: ${error.message}`)
    } finally {
      setPatientLoading(false)
    }
  }

  /** Fase 1 — genera borrador IA sin persistir. */
  const handleGenerateDraft = async (payload) => {
    setLoading(true)
    setAiOriginalData(null)
    setDoctorFinalData(null)
    setCompletedData(null)
    setAccuracyScore(null)
    setCapturePayload(payload)
    setStep('capture')

    try {
      const response = await fetch(`${API_BASE}/clinical-ai/generate-draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setAiOriginalData(cloneClinicalData(data))
      setDoctorFinalData(cloneClinicalData(data))
      setStep('review')
    } catch (error) {
      alert(`Error al generar el borrador: ${error.message}`)
      setStep('capture')
    } finally {
      setLoading(false)
    }
  }

  /** Fase 3 — persiste versión del médico, métrica de precisión y PDF. */
  const handleFinalizeConsultation = async () => {
    if (!aiOriginalData || !doctorFinalData || !capturePayload) {
      alert('No hay borrador para finalizar.')
      return
    }

    setFinalizing(true)
    try {
      const response = await fetch(
        `${API_BASE}/clinical-ai/finalize-consultation`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            patient_id: capturePayload.patient_id,
            conversation_text: capturePayload.conversation_text || '',
            vital_signs: capturePayload.vital_signs || 'No registrados',
            physical_exam: capturePayload.physical_exam || 'No registrado',
            ai_original_data: aiOriginalData,
            doctor_final_data: doctorFinalData,
          }),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const result = await response.json()
      const consultation = result.consultation || doctorFinalData
      const folio = result.folio || consultation.folio

      setCompletedData({ ...consultation, folio })
      setAccuracyScore(
        typeof result.ai_accuracy_score === 'number'
          ? result.ai_accuracy_score
          : null
      )
      setStep('completed')

      if (folio) {
        await downloadConsultationPdfs(folio)
      }
    } catch (error) {
      alert(`Error al finalizar la consulta: ${error.message}`)
    } finally {
      setFinalizing(false)
    }
  }

  return (
    <div className="workspace-grid">
      <PatientProfile
        patientData={patientData}
        loading={patientLoading}
        onPatientLookup={fetchPatientProfile}
      />
      <section className="workspace-center">
        <ConsultationForm
          onProcess={handleGenerateDraft}
          loading={loading || finalizing}
          onPatientLookup={fetchPatientProfile}
        />
      </section>
      <section className="workspace-right">
        <AIResults
          step={step}
          loading={loading}
          finalizing={finalizing}
          doctorFinalData={doctorFinalData}
          completedData={completedData}
          accuracyScore={accuracyScore}
          onDoctorDataChange={setDoctorFinalData}
          onFinalize={handleFinalizeConsultation}
        />
      </section>
    </div>
  )
}

export default ClinicalWorkspace
