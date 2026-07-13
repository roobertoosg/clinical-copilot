import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'
const DOCTOR_NAME = 'Dr. Ricardo Mendoza'

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('es-MX', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function DashboardPage() {
  const navigate = useNavigate()

  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)

  const [recent, setRecent] = useState([])
  const [recentLoading, setRecentLoading] = useState(true)

  const [alerts, setAlerts] = useState([])
  const [alertsLoading, setAlertsLoading] = useState(true)

  useEffect(() => {
    let active = true

    const load = async (path, setData, setLoading) => {
      setLoading(true)
      try {
        const response = await fetch(`${API_BASE}${path}`)
        if (!response.ok) throw new Error(`Error ${response.status}`)
        const data = await response.json()
        if (active) setData(data)
      } catch {
        if (active) setData(null)
      } finally {
        if (active) setLoading(false)
      }
    }

    load('/dashboard/stats', setStats, setStatsLoading)
    load('/dashboard/recent-consultations', (d) => setRecent(d || []), setRecentLoading)
    load('/dashboard/critical-alerts', (d) => setAlerts(d || []), setAlertsLoading)

    return () => {
      active = false
    }
  }, [])

  const statCards = [
    {
      key: 'patients',
      label: 'Pacientes Totales',
      value: stats?.total_patients,
      icon: '☺',
      accent: 'stat-card--blue',
    },
    {
      key: 'today',
      label: 'Consultas Hoy',
      value: stats?.consultations_today,
      icon: '✚',
      accent: 'stat-card--teal',
    },
  ]

  return (
    <div className="dashboard-page">
      {/* ── Encabezado + acciones rápidas ── */}
      <section className="dashboard-hero">
        <div className="dashboard-hero-text">
          <p className="dashboard-hero-eyebrow">Bienvenido de nuevo</p>
          <h1 className="dashboard-hero-title">Hola, {DOCTOR_NAME}</h1>
          <p className="dashboard-hero-subtitle">
            Este es el resumen de tu actividad clínica.
          </p>
        </div>
        <div className="dashboard-actions">
          <button
            type="button"
            className="action-button action-button--primary"
            onClick={() => navigate('/')}
          >
            <span className="action-button-icon" aria-hidden="true">
              ✚
            </span>
            <span className="action-button-text">
              <span className="action-button-title">Iniciar Consulta</span>
              <span className="action-button-desc">Abrir el Workspace clínico</span>
            </span>
          </button>
          <button
            type="button"
            className="action-button action-button--ghost"
            onClick={() => navigate('/pacientes')}
          >
            <span className="action-button-icon" aria-hidden="true">
              ☺
            </span>
            <span className="action-button-text">
              <span className="action-button-title">Registrar Paciente</span>
              <span className="action-button-desc">Alta y gestión de pacientes</span>
            </span>
          </button>
        </div>
      </section>

      {/* ── Tarjetas de resumen ── */}
      <section className="dashboard-stats">
        {statCards.map((card) => (
          <div key={card.key} className={`stat-card ${card.accent}`}>
            <span className="stat-card-icon" aria-hidden="true">
              {card.icon}
            </span>
            <div className="stat-card-body">
              <span className="stat-card-label">{card.label}</span>
              {statsLoading ? (
                <span className="skeleton skeleton-stat" aria-hidden="true" />
              ) : (
                <span className="stat-card-value">{card.value ?? '—'}</span>
              )}
            </div>
          </div>
        ))}
      </section>

      {/* ── Panel principal + lateral ── */}
      <div className="dashboard-grid">
        {/* Consultas recientes */}
        <section className="dashboard-panel">
          <div className="dashboard-panel-head">
            <h2 className="dashboard-panel-title">Consultas Recientes</h2>
            <button
              type="button"
              className="link-button"
              onClick={() => navigate('/consultas')}
            >
              Ver todas →
            </button>
          </div>

          {recentLoading ? (
            <div className="skeleton-list">
              {[0, 1, 2, 3].map((i) => (
                <span key={i} className="skeleton skeleton-row" aria-hidden="true" />
              ))}
            </div>
          ) : recent.length > 0 ? (
            <div className="recent-list">
              {recent.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="recent-item"
                  onClick={() => navigate('/consultas')}
                  title="Ver detalle en Consultas"
                >
                  <span className="recent-item-main">
                    <span className="recent-item-folio">
                      {c.folio || `#${c.id}`}
                    </span>
                    <span className="recent-item-patient">{c.patient_name}</span>
                  </span>
                  <span className="recent-item-side">
                    <span className="recent-item-date">
                      {formatDateTime(c.date)}
                    </span>
                    <span className="recent-item-arrow" aria-hidden="true">
                      →
                    </span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-results">
              <div className="empty-icon" aria-hidden="true" />
              <p>Aún no hay consultas procesadas.</p>
            </div>
          )}
        </section>

        {/* Alertas críticas */}
        <section className="dashboard-panel dashboard-panel--alerts">
          <div className="dashboard-panel-head">
            <h2 className="dashboard-panel-title">
              <span className="alerts-title-icon" aria-hidden="true">
                ⚠️
              </span>
              Alertas Críticas
            </h2>
          </div>

          {alertsLoading ? (
            <div className="skeleton-list">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="skeleton skeleton-row skeleton-row--tall"
                  aria-hidden="true"
                />
              ))}
            </div>
          ) : alerts.length > 0 ? (
            <ul className="critical-alert-list">
              {alerts.map((a) => (
                <li key={a.id} className="critical-alert-item">
                  <div className="critical-alert-head">
                    <span className="critical-alert-patient">
                      {a.patient_name}
                    </span>
                    <span className="critical-alert-badge">
                      {a.severity || 'Alta'}
                    </span>
                  </div>
                  <p className="critical-alert-desc">{a.description}</p>
                  <div className="critical-alert-foot">
                    {a.alert_type && (
                      <span className="critical-alert-type">{a.alert_type}</span>
                    )}
                    <span className="critical-alert-date">
                      {formatDateTime(a.date)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="critical-alert-empty">
              <span className="critical-alert-empty-icon" aria-hidden="true">
                ✓
              </span>
              <p>Sin alertas críticas recientes.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

export default DashboardPage
