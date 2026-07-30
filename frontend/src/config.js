/**
 * URL base del backend FastAPI.
 * En local: http://localhost:8000
 * En la VM: define VITE_API_URL en frontend/.env antes de `npm run build`
 *            ej. VITE_API_URL=http://158.23.60.58
 */
export const API_BASE =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') || 'http://localhost:8000'
