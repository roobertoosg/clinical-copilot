import { API_BASE } from '../config'

async function downloadPdfFromUrl(url, filename) {
  const response = await fetch(url)

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Error ${response.status}`)
  }

  const blob = await response.blob()
  const objectUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(objectUrl)
}

/** PDF interno: SOAPE + CIE-11. */
export async function downloadClinicalNotePdf(folio) {
  if (!folio) {
    throw new Error('No hay un folio de consulta disponible para exportar.')
  }
  await downloadPdfFromUrl(
    `${API_BASE}/clinical-ai/consultations/${folio}/export-pdf/nota-clinica`,
    `nota_clinica_${folio}.pdf`
  )
}

/** PDF para paciente/farmacia: receta + resumen. */
export async function downloadPrescriptionPdf(folio) {
  if (!folio) {
    throw new Error('No hay un folio de consulta disponible para exportar.')
  }
  await downloadPdfFromUrl(
    `${API_BASE}/clinical-ai/consultations/${folio}/export-pdf/receta`,
    `receta_${folio}.pdf`
  )
}

/**
 * Descarga ambos PDFs (receta primero, luego nota clínica).
 * Usado al finalizar la consulta.
 */
export async function downloadConsultationPdfs(folio) {
  await downloadPrescriptionPdf(folio)
  await downloadClinicalNotePdf(folio)
}

/** @deprecated Prefer downloadPrescriptionPdf / downloadConsultationPdfs */
export async function downloadConsultationPdf(folio) {
  await downloadPrescriptionPdf(folio)
}
