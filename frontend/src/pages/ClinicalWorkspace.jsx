import { useState } from 'react'
import PatientProfile from '../components/PatientProfile'
import ConsultationForm from '../components/ConsultationForm'
import AIResults from '../components/AIResults'

function ClinicalWorkspace() {
  const [loading, setLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState(null)
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
        `http://localhost:8000/patients/${id}/clinical-profile`
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

  const handleProcessConsultation = async (payload) => {
    setLoading(true)
    setAiResponse(null)

    try {
      const response = await fetch(
        'http://localhost:8000/clinical-ai/process-consultation',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Error ${response.status}`)
      }

      const data = await response.json()
      setAiResponse(data)
    } catch (error) {
      alert(`Error al procesar la consulta: ${error.message}`)
    } finally {
      setLoading(false)
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
          onProcess={handleProcessConsultation}
          loading={loading}
          onPatientLookup={fetchPatientProfile}
        />
      </section>
      <section className="workspace-right">
        <AIResults aiResponse={aiResponse} loading={loading} />
      </section>
    </div>
  )
}

export default ClinicalWorkspace
