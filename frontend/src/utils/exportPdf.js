import { API_BASE } from '../config'

/**
 * Descarga el PDF de una consulta y simula el clic de guardado en el navegador.
 * Recibe el `folio` de la consulta ya persistida.
 */
export async function downloadConsultationPdf(folio) {
  if (!folio) {
    throw new Error('No hay un folio de consulta disponible para exportar.')
  }

  const response = await fetch(
    `${API_BASE}/clinical-ai/consultations/${folio}/export-pdf`
  )

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Error ${response.status}`)
  }

  // Obtenemos el binario como blob y forzamos la descarga vía un <a> temporal.
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `consulta_${folio}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
