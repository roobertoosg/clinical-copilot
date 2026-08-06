export const EMPTY_PATIENT_SUMMARY = {
  diagnostico_simple: '',
  instrucciones_medicinas: '',
  cuidados_casa: '',
  senales_alarma: '',
}

export const PATIENT_SUMMARY_FIELDS = [
  {
    key: 'diagnostico_simple',
    label: 'Qué le diagnosticaron',
    hint: 'En palabras sencillas, sin tecnicismos.',
  },
  {
    key: 'instrucciones_medicinas',
    label: 'Cómo tomar sus medicinas',
    hint: 'Refuerzo breve: completar tratamiento, horarios clave, etc.',
  },
  {
    key: 'cuidados_casa',
    label: 'Cuidados en casa',
    hint: 'Descanso, líquidos, qué evitar…',
  },
  {
    key: 'senales_alarma',
    label: 'Señales de alarma',
    hint: 'Cuándo regresar o ir a urgencias.',
  },
]

/** Normaliza string legado o dict parcial a los 4 campos. */
export function normalizePatientSummary(value) {
  if (value == null) return { ...EMPTY_PATIENT_SUMMARY }
  if (typeof value === 'string') {
    return {
      ...EMPTY_PATIENT_SUMMARY,
      diagnostico_simple: value.trim(),
    }
  }
  if (typeof value === 'object') {
    return {
      ...EMPTY_PATIENT_SUMMARY,
      diagnostico_simple: value.diagnostico_simple || '',
      instrucciones_medicinas: value.instrucciones_medicinas || '',
      cuidados_casa: value.cuidados_casa || '',
      senales_alarma: value.senales_alarma || '',
    }
  }
  return { ...EMPTY_PATIENT_SUMMARY }
}

export function patientSummaryHasContent(value) {
  const summary = normalizePatientSummary(value)
  return Object.values(summary).some((text) => String(text || '').trim())
}
